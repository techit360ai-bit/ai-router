"""Live provider credential validation for readiness.

The static runtime check only rejects placeholder-shaped *values* by pattern, so
a key that is present but wrong (expired, revoked, truncated, or belonging to a
deleted project) passes ``/ready`` while every live AI call fails with 401. This
module performs a cheap authenticated probe against each provider, caches the
verdict for a short TTL, and exposes it as a readiness signal.

Providers are sourced from the model registry, so every provider the router can
route to is validated -- not just OpenAI and Anthropic. OpenAI and Anthropic are
mandatory (readiness fails when their keys are missing or rejected); every other
provider is optional and is probed only when a key is present, so an operator who
only configures one provider never sees readiness flap on the others.

Transient failures (timeout, DNS, 5xx) are deliberately treated as *unknown*
rather than *invalid*: readiness must not flap on a probe glitch, but a genuine
401/403 is a hard, actionable failure.
"""

from __future__ import annotations

import os
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Dict, List, Mapping, Sequence

# Mandatory providers: absent or invalid credentials fail readiness.
DEFAULT_REQUIRED_PROVIDERS = ("openai", "anthropic")

# Probe endpoints for providers whose adapter does not publish a base_url we can
# derive an OpenAI-compatible ``/models`` path from. OpenAI-compatible providers
# (openrouter, moonshot, mistral, agentrouter, custom) derive ``<base>/models``.
_DEFAULT_PROBE_URLS: Dict[str, str] = {
    "openai": "https://api.openai.com/v1/models",
    "anthropic": "https://api.anthropic.com/v1/models",
    "google": "https://generativelanguage.googleapis.com/v1beta/models",
    "cohere": "https://api.cohere.com/v1/models",
}

# Fallback specs used when the registry cannot be loaded (e.g. a bare test
# environment) so mandatory provider validation never silently disappears.
_FALLBACK_SPECS: Dict[str, Dict[str, Any]] = {
    "openai": {
        "envs": ["OPENAI_API_KEY", "OPENAI_API_KEY_2", "OPENAI_API_KEY_3", "OPENAI_API_KEY_4"],
        "url": _DEFAULT_PROBE_URLS["openai"],
        "auth": "bearer",
    },
    "anthropic": {
        "envs": ["ANTHROPIC_API_KEY", "ANTHROPIC_API_KEY_2", "ANTHROPIC_API_KEY_3", "ANTHROPIC_API_KEY_4"],
        "url": _DEFAULT_PROBE_URLS["anthropic"],
        "auth": "anthropic",
    },
}

CACHE_TTL_SECONDS = max(30, int(os.getenv("AI_PROVIDER_KEY_CHECK_TTL_SECONDS", "300")))
TIMEOUT_SECONDS = max(2, int(os.getenv("AI_PROVIDER_KEY_CHECK_TIMEOUT_SECONDS", "6")))

_cache: Dict[str, Any] = {"checked_at": 0.0, "providers": {}}
_lock = threading.Lock()
# Specs for the providers currently being probed, so ``_probe_status`` can stay
# a two-argument function (existing tests monkeypatch it as ``(provider, key)``).
_active_specs: Dict[str, Dict[str, Any]] = {}


def _enabled() -> bool:
    return os.getenv("AI_PROVIDER_KEY_CHECK", "live").strip().lower() not in {"0", "false", "no", "off", "disabled"}


def _required_providers() -> set[str]:
    raw = os.getenv("AI_REQUIRED_PROVIDERS", ",".join(DEFAULT_REQUIRED_PROVIDERS))
    return {item.strip().lower() for item in raw.split(",") if item.strip()}


def _truthy(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _auth_kind(adapter: str) -> str:
    if adapter == "anthropic_messages":
        return "anthropic"
    if adapter == "gemini_generate":
        return "query"
    if adapter == "bedrock_converse":
        return "sigv4"
    if adapter == "bedrock_bearer":
        return "bearer"
    return "bearer"


def _probe_url_from_base(base_url: str) -> str:
    base = base_url.rstrip("/")
    for suffix in ("/chat/completions", "/responses"):
        if base.endswith(suffix):
            base = base[: -len(suffix)]
    return f"{base}/models" if base else ""


def _azure_probe_url(base_url: str) -> str:
    """Azure OpenAI exposes its model list at the resource level.

    ``https://{res}.openai.azure.com/openai/deployments/{d}/chat/completions?api-version=...``
    is probed as ``https://{res}.openai.azure.com/openai/models?api-version=...`` with
    the ``api-key`` header.
    """
    path, _, query = (base_url or "").partition("?")
    path = path.rstrip("/")
    for suffix in ("/chat/completions", "/completions", "/responses"):
        if path.endswith(suffix):
            path = path[: -len(suffix)]
    marker = "/openai/deployments/"
    path = path.split(marker)[0] + "/openai/models" if marker in path else f"{path}/models"
    return f"{path}?{query}" if query else path


def _provider_specs() -> Dict[str, Dict[str, Any]]:
    """Return per-provider probe specs sourced from the model registry."""
    specs: Dict[str, Dict[str, Any]] = {name: dict(spec) for name, spec in _FALLBACK_SPECS.items()}
    try:
        from model_registry import ModelRegistry

        registry = ModelRegistry()
    except Exception:  # noqa: BLE001 - registry unavailable: keep fallback specs
        return specs

    for provider_id, definition in registry.providers.items():
        envs = [name for name in list(definition.api_key_envs) or [definition.api_key_env] if name]
        base_url = definition.base_url
        if definition.base_url_env:
            base_url = os.getenv(definition.base_url_env, "") or base_url
        base_url = os.path.expandvars(base_url or "")
        if "${" in base_url:
            base_url = ""
        auth = definition.resolved_auth
        region = (os.getenv(definition.region_env, "") if definition.region_env else "") or definition.region or "us-east-1"
        if auth == "sigv4":
            # SigV4 providers carry no static key; the control-plane endpoint is
            # only used to describe the provider, never probed with a bearer key.
            url = f"https://bedrock.{region}.amazonaws.com" if provider_id == "bedrock" else f"https://bedrock-runtime.{region}.amazonaws.com"
        elif auth == "azure":
            # Azure OpenAI verifies with the api-key header, and its model list
            # lives at the resource root (with api-version), not under the
            # deployment path.
            url = _azure_probe_url(base_url)
        else:
            url = _DEFAULT_PROBE_URLS.get(provider_id) or _probe_url_from_base(base_url)
        specs[provider_id] = {
            "envs": envs or list(_FALLBACK_SPECS.get(provider_id, {}).get("envs", [])),
            "url": url,
            "auth": auth or _auth_kind(definition.adapter),
            "region": region,
            "enabled": definition.enabled,
            "enabled_env": definition.enabled_env,
        }
    return specs


def _provider_active(spec: Mapping[str, Any]) -> bool:
    if spec.get("enabled") is False:
        return False
    enabled_env = spec.get("enabled_env")
    if enabled_env and not _truthy(os.getenv(str(enabled_env))):
        return False
    return True


def _probe_status(provider: str, key: str) -> int:
    spec = _active_specs.get(provider) or _FALLBACK_SPECS.get(provider) or {}
    url = str(spec.get("url") or "")
    if not url:
        return 0
    auth = str(spec.get("auth") or "bearer")
    headers: Dict[str, str] = {}
    if auth == "query":
        url = f"{url}?key={urllib.parse.quote(key)}"
    elif auth == "anthropic":
        headers = {"x-api-key": key, "anthropic-version": "2023-06-01"}
    elif auth == "azure":
        headers = {"api-key": key}
    else:
        headers = {"Authorization": f"Bearer {key}"}
    request = urllib.request.Request(url, headers=headers, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            return int(response.status)
    except urllib.error.HTTPError as exc:
        return int(exc.code)
    except Exception:  # noqa: BLE001 - network/DNS/TLS: unknown, not invalid
        return 0


def _validate_provider(provider: str, keys: Sequence[str]) -> Dict[str, Any]:
    valid = invalid = unknown = 0
    for key in keys:
        status = _probe_status(provider, key)
        if status in (200, 204):
            valid += 1
        elif status in (401, 403):
            invalid += 1
        else:
            # Transient/unverifiable: neither proven valid nor invalid. It must
            # not fail readiness, so count it as usable.
            unknown += 1
    return {
        "configured": len(keys),
        "valid": valid,
        "invalid": invalid,
        "unknown": unknown,
        "ok": (valid + unknown) > 0,
        "detail": f"configured={len(keys)} valid={valid} invalid={invalid} unknown={unknown}",
    }


def _unconfigured(provider: str, required: bool) -> Dict[str, Any]:
    return {
        "configured": 0,
        "valid": 0,
        "invalid": 0,
        "unknown": 0,
        "ok": False,
        "required": required,
        "detail": f"no {provider} API key configured",
    }


def _aws_credential_status() -> int:
    """1 = AWS credentials resolvable, 0 = not resolvable, -1 = boto3 missing.

    SigV4 providers authenticate with the AWS credential chain (env, profile,
    instance/task role), not a static API key, so readiness checks for the chain
    itself without making a network call.
    """
    try:
        import boto3  # type: ignore
    except ImportError:
        return -1
    try:
        return 1 if boto3.Session().get_credentials() is not None else 0
    except Exception:  # noqa: BLE001 - unknown credential state must not crash readiness
        return 0


def _bedrock_live_probe_enabled() -> bool:
    return _truthy(os.getenv("AI_BEDROCK_LIVE_PROBE"))


def _probe_bedrock_live(region: str) -> int:
    """Live SigV4 probe via the Bedrock control plane.

    200 = credentials usable, 401 = rejected/expired, 0 = unknown/transient,
    -1 = boto3 missing. Requires ``bedrock:ListFoundationModels``.
    """
    try:
        import boto3  # type: ignore
        from botocore.config import Config  # type: ignore
    except ImportError:
        return -1
    try:
        if boto3.Session().get_credentials() is None:
            return 401
        client = boto3.client(
            "bedrock",
            region_name=region or None,
            config=Config(connect_timeout=TIMEOUT_SECONDS, read_timeout=TIMEOUT_SECONDS, retries={"max_attempts": 1}),
        )
        client.list_foundation_models()
        return 200
    except Exception as exc:  # noqa: BLE001 - classify, never crash readiness
        response = getattr(exc, "response", None) or {}
        code = str((response.get("Error") or {}).get("Code") or "")
        http_status = int((response.get("ResponseMetadata") or {}).get("HTTPStatusCode") or 0)
        if http_status in (401, 403) or code in {
            "AccessDeniedException", "AccessDenied", "UnrecognizedClientException",
            "InvalidSignatureException", "SignatureDoesNotMatch", "ExpiredTokenException",
            "InvalidClientTokenId", "AuthFailure",
        }:
            return 401
        return 0


def _credential_chain_report(provider: str, region: str = "", live: bool = False) -> Dict[str, Any]:
    """Readiness for SigV4 providers (AWS Bedrock), which carry no static key."""
    status = _aws_credential_status()
    if status == -1:
        return {
            "configured": 0, "valid": 0, "invalid": 0, "unknown": 1, "ok": False,
            "detail": f"{provider} requires boto3 for SigV4 authentication",
        }
    if status == 0:
        return {
            "configured": 0, "valid": 0, "invalid": 1, "unknown": 0, "ok": False,
            "detail": f"no AWS credentials in the default chain for {provider}",
        }
    if live:
        probe = _probe_bedrock_live(region)
        if probe == 200:
            return {
                "configured": 1, "valid": 1, "invalid": 0, "unknown": 0, "ok": True,
                "detail": f"{provider} SigV4 credentials accepted by the Bedrock control plane",
            }
        if probe == 401:
            return {
                "configured": 1, "valid": 0, "invalid": 1, "unknown": 0, "ok": False,
                "detail": f"{provider} SigV4 credentials rejected by AWS",
            }
        return {
            "configured": 1, "valid": 0, "invalid": 0, "unknown": 1, "ok": True,
            "detail": f"{provider} SigV4 credentials present; control-plane probe inconclusive",
        }
    return {
        "configured": 1, "valid": 1, "invalid": 0, "unknown": 0, "ok": True,
        "detail": f"{provider} uses the AWS credential chain (resolved)",
    }


def provider_key_health(force: bool = False) -> Dict[str, Dict[str, Any]]:
    """Return per-provider credential validity, cached for a short TTL.

    Mandatory providers (OpenAI, Anthropic by default) always appear; optional
    providers appear only when a key is configured for them.
    """
    if not _enabled():
        return {}
    now = time.time()
    with _lock:
        if not force and _cache["providers"] and (now - _cache["checked_at"]) < CACHE_TTL_SECONDS:
            return _cache["providers"]

    specs = _provider_specs()
    required = _required_providers()
    with _lock:
        _active_specs.clear()
        _active_specs.update(specs)

    providers: Dict[str, Dict[str, Any]] = {}
    for name, spec in specs.items():
        is_required = name in required
        if not _provider_active(spec):
            continue
        if spec.get("auth") == "sigv4":
            report = _credential_chain_report(
                name,
                region=str(spec.get("region") or ""),
                live=_bedrock_live_probe_enabled(),
            )
            report["required"] = is_required
            providers[name] = report
            continue
        keys = [os.environ.get(str(env_name), "").strip() for env_name in spec.get("envs", [])]
        keys = [key for key in keys if key]
        if not keys:
            if is_required:
                providers[name] = _unconfigured(name, True)
            continue
        report = _validate_provider(name, keys)
        report["required"] = is_required
        providers[name] = report

    # A mandatory provider missing from the registry specs must still fail closed.
    for name in required:
        if name not in providers:
            providers[name] = _unconfigured(name, True)

    with _lock:
        _cache["checked_at"] = now
        _cache["providers"] = providers
    return providers
