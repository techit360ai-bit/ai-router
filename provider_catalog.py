"""Catalog-driven provider activation and bounded auto-canary leases.

The catalog declares which environment signature identifies a provider. It never
infers a provider from the shape of a secret. A complete signature enables the
provider for discovery; discovered models remain inert until they receive a
bounded ``auto_canary`` lease and are merged into a runtime registry overlay.
"""

from __future__ import annotations

import copy
import json
import os
import re
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence


ROOT = Path(__file__).resolve().parent
DEFAULT_CATALOG_PATH = ROOT / "config" / "provider_catalog.json"
DEFAULT_RUNTIME_PATH = ROOT / "runtime" / "provider_runtime.json"

_LOCK = threading.RLock()
_TERMINAL_LEASE_STATUSES = {"revoked", "rejected"}
_INACTIVE_LEASE_STATUSES = {"disabled", "revoked", "rejected", "missing"}
_POLICY_SETTING_KEYS = {
    "auto_canary_traffic_percent",
    "auto_model_daily_spend_cap_usd",
    "auto_model_max_output_tokens",
    "auto_model_promotion_min_calls",
    "auto_model_promotion_hours",
    "auto_model_max_error_rate",
    "auto_model_max_price_drift",
    "conservative_input_cost_per_million",
    "conservative_output_cost_per_million",
}


def _truthy(value: Any) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def _enabled(value: Any, default: bool = True) -> bool:
    text = str(value or "").strip().lower()
    if not text:
        return default
    return text not in {"0", "false", "no", "off", "disabled"}


def _catalog_path() -> Path:
    return Path(os.getenv("AI_PROVIDER_CATALOG_PATH", str(DEFAULT_CATALOG_PATH)))


def runtime_path() -> Path:
    return Path(os.getenv("AI_PROVIDER_RUNTIME_PATH", str(DEFAULT_RUNTIME_PATH)))


def _read_json(path: Path, fallback: Dict[str, Any]) -> Dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else fallback
    except (OSError, ValueError):
        return fallback


def catalog() -> Dict[str, Any]:
    return _read_json(_catalog_path(), {"providers": [], "defaults": {}})


def defaults() -> Dict[str, Any]:
    value = catalog().get("defaults")
    return value if isinstance(value, dict) else {}


def effective_defaults() -> Dict[str, Any]:
    """Catalog defaults plus the bounded runtime overrides an admin may set."""
    merged = dict(defaults())
    overrides = runtime_snapshot().get("policy", {}).get("settings")
    if isinstance(overrides, Mapping):
        for key in _POLICY_SETTING_KEYS:
            if key in overrides:
                merged[key] = overrides[key]
    return merged


def _safe_error(value: Any, env: Optional[Mapping[str, str]] = None) -> str:
    """Keep error details useful without echoing configured credential values."""
    text = str(value or "")
    values = _env_values(env)
    for name, secret in values.items():
        if not secret or len(str(secret)) < 6:
            continue
        if any(token in str(name).lower() for token in ("key", "secret", "token", "password")):
            text = text.replace(str(secret), "[redacted]")
    return text[:500]


def _empty_runtime() -> Dict[str, Any]:
    return {
        "schema_version": 1,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "policy": {"auto_provision_enabled": True, "version": 1, "settings": {}},
        "providers": {},
        "model_leases": {},
    }


def runtime_snapshot() -> Dict[str, Any]:
    state = _read_json(runtime_path(), _empty_runtime())
    state.setdefault("schema_version", 1)
    state.setdefault("policy", {})
    state.setdefault("providers", {})
    state.setdefault("model_leases", {})
    state["policy"].setdefault("auto_provision_enabled", True)
    state["policy"].setdefault("version", 1)
    state["policy"].setdefault("settings", {})
    return state


def _write_runtime(state: Mapping[str, Any]) -> None:
    path = runtime_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = copy.deepcopy(dict(state))
    payload["updated_at"] = datetime.now(timezone.utc).isoformat()
    temporary = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
    temporary.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    temporary.replace(path)


def auto_provision_enabled(env: Optional[Mapping[str, str]] = None) -> bool:
    values = env or os.environ
    if not _enabled(values.get("AI_PROVIDER_AUTO_CONFIG", "true")):
        return False
    if not _enabled(values.get("AI_AUTO_PROVIDER_DISCOVERY", "true")):
        return False
    with _LOCK:
        return runtime_snapshot()["policy"].get("auto_provision_enabled", True) is not False


def _env_values(env: Optional[Mapping[str, str]] = None) -> Mapping[str, str]:
    return env if env is not None else os.environ


def _provider_template(provider_id: str) -> Optional[Dict[str, Any]]:
    return next((row for row in catalog().get("providers", []) if row.get("id") == provider_id), None)


def _aws_credentials_available() -> Optional[bool]:
    """Whether boto3 can resolve credentials from its normal chain.

    Bedrock is not key-only. Operators may provide static environment keys, a
    shared profile, or workload identity. Readiness therefore checks the AWS
    credential chain rather than requiring two specific environment names.
    """
    try:
        import boto3  # type: ignore
    except ImportError:
        return None
    try:
        return boto3.Session().get_credentials() is not None
    except Exception:  # noqa: BLE001 - unknown must not crash discovery
        return False


def _activation(provider: Mapping[str, Any], env: Optional[Mapping[str, str]] = None) -> Dict[str, Any]:
    values = _env_values(env)
    required = [str(item) for item in provider.get("required_env", []) if item]
    present = [name for name in required if str(values.get(name, "")).strip()]
    missing = [name for name in required if name not in present]
    enabled_env = str(provider.get("enabled_env") or "")
    explicitly_disabled = bool(enabled_env and str(values.get(enabled_env, "")).strip() and not _truthy(values.get(enabled_env)))
    missing_credentials: List[str] = []
    if str(provider.get("credential_mode") or "") == "aws_chain":
        available = _aws_credentials_available()
        if available is True:
            present.append("AWS_CREDENTIAL_CHAIN")
        else:
            missing_credentials.append("AWS_CREDENTIAL_CHAIN")
    complete = not missing and not missing_credentials
    return {
        "detected": bool(present),
        "configured": complete,
        "explicitly_disabled": explicitly_disabled,
        "present_env": present,
        "missing_env": missing,
        "missing_credentials": missing_credentials,
    }


def _provider_base_url(provider: Mapping[str, Any], env: Optional[Mapping[str, str]] = None) -> str:
    """Resolve a provider base URL from its declared environment signature."""
    values = _env_values(env)
    provider_id = str(provider.get("id") or "")
    env_name = str(provider.get("base_url_env") or "")
    base = str(values.get(env_name, "")) if env_name else ""
    base = base or str(provider.get("base_url") or "")
    base = os.path.expandvars(base).strip().rstrip("/")
    if "${" in base:
        base = ""
    if provider_id == "google_vertex":
        project = str(values.get("GOOGLE_CLOUD_PROJECT", "")).strip()
        region = str(values.get("GOOGLE_VERTEX_REGION", "")).strip() or str(provider.get("region") or "global")
        if project and region:
            version = str(values.get("GOOGLE_VERTEX_API_VERSION", "v1")).strip() or "v1"
            base = f"https://{region}-aiplatform.googleapis.com/{version}/projects/{project}/locations/{region}/endpoints/openapi"
    return base


def _safe_number(value: Any) -> Optional[float]:
    if value in (None, ""):
        return None
    try:
        return max(0.0, float(value))
    except (TypeError, ValueError):
        return None


def sanitize_model_id(value: str) -> str:
    text = str(value or "").strip()
    text = re.sub(r"[^A-Za-z0-9._:-]+", "-", text)
    return text.strip("-")[:180] or "model"


def lease_id_for(provider_id: str, upstream_model: str) -> str:
    return f"auto:{sanitize_model_id(provider_id)}:{sanitize_model_id(upstream_model)}"


def _curated_price(provider: Mapping[str, Any], upstream_model: str) -> Optional[Dict[str, float]]:
    prices = provider.get("curated_prices")
    if not isinstance(prices, Mapping):
        return None
    lower = str(upstream_model or "").lower()
    for prefix, value in sorted(prices.items(), key=lambda item: len(str(item[0])), reverse=True):
        if lower.startswith(str(prefix).lower()) or str(prefix).lower() in lower:
            if isinstance(value, Mapping):
                input_cost = _safe_number(value.get("input"))
                output_cost = _safe_number(value.get("output"))
                if input_cost is not None and output_cost is not None:
                    return {"input": input_cost, "output": output_cost}
    return None


def resolve_price(provider: Mapping[str, Any], upstream_model: str, row: Mapping[str, Any]) -> Dict[str, Any]:
    feed_input = _safe_number(row.get("input_cost_per_million"))
    feed_output = _safe_number(row.get("output_cost_per_million"))
    if feed_input is not None and feed_output is not None:
        return {
            "input_cost_per_million": feed_input,
            "output_cost_per_million": feed_output,
            "pricing_source": str(row.get("pricing_source") or "provider_feed"),
            "pending_reconciliation": False,
        }
    curated = _curated_price(provider, upstream_model)
    if curated:
        return {
            "input_cost_per_million": curated["input"],
            "output_cost_per_million": curated["output"],
            "pricing_source": "curated_table",
            "pending_reconciliation": True,
        }
    fallback = defaults()
    return {
        "input_cost_per_million": max(0.0, float(fallback.get("conservative_input_cost_per_million", 10))),
        "output_cost_per_million": max(0.0, float(fallback.get("conservative_output_cost_per_million", 30))),
        "pricing_source": "conservative_default",
        "pending_reconciliation": True,
    }


def _model_spec(provider: Mapping[str, Any], row: Mapping[str, Any], now: str) -> Dict[str, Any]:
    upstream = str(row.get("upstream_model") or row.get("id") or "").strip()
    lease_id = lease_id_for(str(provider.get("id")), upstream)
    price = resolve_price(provider, upstream, row)
    config = effective_defaults()
    input_cost = float(price["input_cost_per_million"])
    output_cost = float(price["output_cost_per_million"])
    capabilities = [str(item) for item in row.get("capabilities", ["text"]) if str(item).strip()]
    if "text" not in capabilities:
        capabilities.insert(0, "text")
    return {
        "lease_id": lease_id,
        "model_id": lease_id,
        "provider_id": str(provider.get("id")),
        "upstream_model": upstream,
        "enabled": True,
        "user_selectable": False,
        "quality_tier": str(row.get("quality_tier") or "uncertified"),
        "quality_score": float(row.get("quality_score", 60)),
        "latency_score": float(row.get("latency_score", 60)),
        "context_window": int(row.get("context_window", 128_000)),
        "max_output_tokens": min(int(row.get("max_output_tokens", 8192)), int(config.get("auto_model_max_output_tokens", 2048))),
        "capabilities": capabilities,
        "input_cost_per_million": input_cost,
        "output_cost_per_million": output_cost,
        "billing_class": "free" if price["pricing_source"] == "provider_feed" and input_cost == 0.0 and output_cost == 0.0 else "paid",
        "approval_status": "auto_canary",
        "pricing_source": price["pricing_source"],
        "pricing_version": f"catalog:{catalog().get('version', 'unversioned')}",
        "pending_reconciliation": price["pending_reconciliation"],
        "traffic_percent": float(config.get("auto_canary_traffic_percent", 1)),
        "daily_spend_cap_usd": float(config.get("auto_model_daily_spend_cap_usd", 5)),
        "spend_today_usd": 0.0,
        "spend_date": datetime.now(timezone.utc).date().isoformat(),
        "calls": 0,
        "errors": 0,
        "discovered_at": now,
        "updated_at": now,
        "status": "active",
        "version": 1,
        "promotion_eligible": False,
        "last_action": "discovered",
        "last_action_reason": "provider discovery",
    }


def apply_registry_overlay(document: Mapping[str, Any], env: Optional[Mapping[str, str]] = None) -> Dict[str, Any]:
    """Return a registry document extended with detected providers and leases."""
    output = copy.deepcopy(dict(document))
    auto_enabled = auto_provision_enabled(env)
    providers: List[Dict[str, Any]] = list(output.get("providers") or [])
    by_id = {str(row.get("id")): row for row in providers if isinstance(row, dict)}
    state = runtime_snapshot()
    approved_provider_ids = {
        str(lease.get("provider_id"))
        for lease in state.get("model_leases", {}).values()
        if lease.get("status") == "approved"
    }
    for template in catalog().get("providers", []):
        activation = _activation(template, env)
        provider_id = str(template.get("id") or "")
        if not provider_id or activation["explicitly_disabled"]:
            continue
        if not activation["configured"] and not (provider_id in by_id and provider_id in approved_provider_ids):
            continue
        if not auto_enabled and provider_id not in approved_provider_ids:
            continue
        row = by_id.get(provider_id)
        if row is None:
            base_url = _provider_base_url(template, env)
            row = {
                "id": provider_id,
                "adapter": template.get("adapter"),
                "api_key_env": (template.get("api_key_envs") or [""])[0],
                "api_key_envs": template.get("api_key_envs") or [],
                "base_url": base_url,
                "base_url_env": template.get("base_url_env", ""),
                "region": template.get("region", "global"),
                "region_env": template.get("region_env", ""),
                "auth": template.get("auth", ""),
            }
            providers.append(row)
            by_id[provider_id] = row
        row["enabled"] = True
        row["enabled_env"] = ""
        row["_catalog_detected"] = True

    for lease in state.get("model_leases", {}).values():
        status = str(lease.get("status") or "active")
        if status in _INACTIVE_LEASE_STATUSES:
            continue
        if status != "approved" and not auto_enabled:
            continue
        approval = "approved" if status == "approved" else "auto_canary"
        promoted = status == "approved"
        providers_present = str(lease.get("provider_id")) in by_id
        if not providers_present:
            continue
        model_row = {
            "id": lease["model_id"],
            "provider": lease["provider_id"],
            "upstream_model": lease.get("upstream_model") or lease.get("model_id"),
            "enabled": True,
            "user_selectable": promoted,
            "quality_tier": lease.get("quality_tier", "uncertified"),
            "quality_score": lease.get("quality_score", 60),
            "latency_score": lease.get("latency_score", 60),
            "context_window": lease.get("context_window", 128_000),
            "max_output_tokens": lease.get("max_output_tokens", 2048),
            "capabilities": lease.get("capabilities", ["text"]),
            "input_cost_per_million": lease.get("input_cost_per_million"),
            "output_cost_per_million": lease.get("output_cost_per_million"),
            "billing_class": lease.get("billing_class", "paid"),
            "approval_status": approval,
            "pricing_version": lease.get("pricing_version", ""),
            "pricing_source": lease.get("pricing_source", "conservative_default"),
            "pending_reconciliation": bool(lease.get("pending_reconciliation")),
            "lease_id": lease["lease_id"],
            "traffic_percent": float(lease.get("traffic_percent") or 0) if not promoted else 0.0,
            "daily_spend_cap_usd": lease.get("daily_spend_cap_usd"),
            "tags": ["auto_canary" if not promoted else "promoted"],
        }
        output.setdefault("models", [])
        replaced = False
        for index, existing in enumerate(output["models"]):
            if str(existing.get("id")) == model_row["id"]:
                output["models"][index] = model_row
                replaced = True
                break
        if not replaced:
            output["models"].append(model_row)
    output["providers"] = providers
    output["_provider_catalog"] = {
        "version": catalog().get("version", "unversioned"),
        "applied": True,
    }
    return output


def _static_registry_document() -> Dict[str, Any]:
    path = Path(os.getenv("MODEL_REGISTRY_PATH", str(ROOT / "config" / "model_registry.json")))
    return _read_json(path, {"providers": [], "models": []})


def promotion_eligible(lease: Mapping[str, Any]) -> bool:
    config = effective_defaults()
    calls = int(lease.get("calls") or 0)
    errors = int(lease.get("errors") or 0)
    min_calls = int(config.get("auto_model_promotion_min_calls", 20))
    if calls < min_calls:
        return False
    error_rate = errors / max(1, calls)
    if error_rate > float(config.get("auto_model_max_error_rate", 0.05)):
        return False
    try:
        observed_hours = (datetime.now(timezone.utc) - datetime.fromisoformat(str(lease.get("discovered_at", "")).replace("Z", "+00:00"))).total_seconds() / 3600
    except ValueError:
        observed_hours = 0
    return observed_hours >= float(config.get("auto_model_promotion_hours", 24))


def lease_snapshot() -> Dict[str, Any]:
    state = runtime_snapshot()
    leases = []
    for lease in state.get("model_leases", {}).values():
        row = dict(lease)
        row["promotion_eligible"] = bool(row.get("promotion_eligible")) or promotion_eligible(row)
        leases.append(row)
    leases.sort(key=lambda row: (str(row.get("provider_id")), str(row.get("upstream_model"))))
    return {
        "updatedAt": state.get("updated_at"),
        "policy": state.get("policy", {}),
        "providers": state.get("providers", {}),
        "leases": leases,
    }


def _bounded_policy_settings(values: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    output: Dict[str, Any] = {}
    for key in _POLICY_SETTING_KEYS:
        if key not in (values or {}):
            continue
        value = _safe_number(values[key])
        if value is None:
            continue
        if key == "auto_model_max_output_tokens":
            output[key] = max(1, min(131_072, int(value)))
        elif key == "auto_model_promotion_min_calls":
            output[key] = max(1, int(value))
        elif key == "auto_model_promotion_hours":
            output[key] = max(0.0, min(24 * 365, value))
        elif key in {"auto_model_max_error_rate"}:
            output[key] = max(0.0, min(1.0, value))
        elif key in {"auto_model_max_price_drift"}:
            output[key] = max(0.0, min(10.0, value))
        elif key == "auto_canary_traffic_percent":
            output[key] = max(0.0, min(100.0, value))
        else:
            output[key] = value
    return output


def set_auto_provision(
    enabled: bool,
    actor: str = "system",
    reason: str = "",
    *,
    expected_version: Optional[int] = None,
    settings: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    if not str(reason or "").strip():
        return {"ok": False, "status": 400, "error": "policy_reason_required"}
    with _LOCK:
        state = runtime_snapshot()
        current_version = int(state["policy"].get("version") or 1)
        if expected_version is not None and int(expected_version) != current_version:
            return {
                "ok": False,
                "status": 409,
                "error": "stale_policy_version",
                "policy": state["policy"],
            }
        before = copy.deepcopy(state["policy"])
        state["policy"]["auto_provision_enabled"] = bool(enabled)
        state["policy"]["settings"] = {
            **dict(state["policy"].get("settings") or {}),
            **_bounded_policy_settings(settings),
        }
        state["policy"]["version"] = current_version + 1
        state["policy"]["updated_at"] = datetime.now(timezone.utc).isoformat()
        state["policy"]["updated_by"] = actor
        state["policy"]["reason"] = reason[:500]
        state["policy"]["before"] = before
        _write_runtime(state)
        return {"ok": True, "policy": state["policy"]}


def update_model_lease(
    provider_id: str,
    model_id: str,
    action: str,
    *,
    reason: str = "",
    input_cost_per_million: Optional[float] = None,
    output_cost_per_million: Optional[float] = None,
    actor: str = "system",
    override: bool = False,
    expected_version: Optional[int] = None,
) -> Dict[str, Any]:
    action = str(action or "").strip().lower()
    if action not in {"promote", "disable", "revoke", "reprice", "reject"}:
        return {"ok": False, "status": 400, "error": "invalid_lease_action"}
    if not str(reason or "").strip():
        return {"ok": False, "status": 400, "error": "lease_action_reason_required"}
    with _LOCK:
        state = runtime_snapshot()
        lease = state.get("model_leases", {}).get(str(model_id))
        if not lease or (provider_id and lease.get("provider_id") != provider_id):
            return {"ok": False, "status": 404, "error": "model_lease_not_found"}
        before = copy.deepcopy(lease)
        current_version = int(lease.get("version") or 1)
        if expected_version is not None and int(expected_version) != current_version:
            return {
                "ok": False,
                "status": 409,
                "error": "stale_lease_version",
                "lease": lease,
            }
        now = datetime.now(timezone.utc).isoformat()
        if action == "reprice":
            input_value = _safe_number(input_cost_per_million)
            output_value = _safe_number(output_cost_per_million)
            if input_value is None or output_value is None:
                return {"ok": False, "status": 400, "error": "valid_non_negative_prices_required"}
            lease["input_cost_per_million"] = input_value
            lease["output_cost_per_million"] = output_value
            lease["pricing_source"] = "manual_override"
            lease["pending_reconciliation"] = False
            # Free classification is a provider-feed fact, never an operator
            # price override. A zero manual price still bills as paid/zero-cost.
            lease["billing_class"] = "paid"
        elif action == "promote":
            if not promotion_eligible(lease) and not override:
                return {"ok": False, "status": 409, "error": "promotion_criteria_not_met", "lease": lease}
            if lease.get("pending_reconciliation") and lease.get("pricing_source") == "conservative_default" and not override:
                return {"ok": False, "status": 409, "error": "pricing_reconciliation_required", "lease": lease}
            lease["status"] = "approved"
            lease["traffic_percent"] = 0.0
            lease["user_selectable"] = True
        elif action == "disable":
            lease["status"] = "disabled"
            lease["traffic_percent"] = 0.0
        elif action == "revoke":
            lease["status"] = "revoked"
            lease["traffic_percent"] = 0.0
        elif action == "reject":
            lease["status"] = "rejected"
            lease["traffic_percent"] = 0.0
        lease["last_action"] = action
        lease["last_action_reason"] = str(reason)[:500]
        lease["updated_at"] = now
        lease["updated_by"] = actor
        lease["version"] = current_version + 1
        lease["last_action_before"] = {key: before.get(key) for key in ("status", "traffic_percent", "input_cost_per_million", "output_cost_per_million", "pricing_source")}
        _write_runtime(state)
        return {"ok": True, "lease": lease}


def provider_status(
    *,
    credential_reports: Optional[Mapping[str, Mapping[str, Any]]] = None,
    env: Optional[Mapping[str, str]] = None,
) -> Dict[str, Any]:
    values = _env_values(env)
    reports = credential_reports or {}
    state = runtime_snapshot()
    leases_by_provider: Dict[str, List[Dict[str, Any]]] = {}
    for lease in state.get("model_leases", {}).values():
        leases_by_provider.setdefault(str(lease.get("provider_id")), []).append(lease)
    output = []
    for template in catalog().get("providers", []):
        provider_id = str(template.get("id") or "")
        activation = _activation(template, values)
        report = reports.get(provider_id) or {}
        runtime_provider = state.get("providers", {}).get(provider_id) or {}
        leases = leases_by_provider.get(provider_id, [])
        approved = len([row for row in leases if row.get("status") == "approved"])
        canary = len([row for row in leases if row.get("status") == "active"])
        discovered = len(leases)
        credential_ok = report.get("ok") if report else None
        discovery_error = runtime_provider.get("last_discovery_error")
        status = "not_detected"
        if activation["explicitly_disabled"]:
            status = "disabled"
        elif activation["detected"] and not activation["configured"]:
            status = "misconfigured"
        elif activation["configured"]:
            if credential_ok is False:
                status = "degraded"
            elif discovery_error:
                status = "degraded"
            else:
                status = "ready"
        output.append({
            "id": provider_id,
            "adapter": template.get("adapter"),
            "auth": template.get("auth"),
            "status": status,
            "detected": activation["detected"],
            "configured": activation["configured"],
            "present_env": activation["present_env"],
            "missing_env": activation["missing_env"],
            "missing_credentials": activation.get("missing_credentials", []),
            "credential_ok": credential_ok,
            "credential_detail": _safe_error(report.get("detail"), values),
            "discovery_ok": bool(runtime_provider.get("last_discovery_at")) and not discovery_error,
            "last_checked_at": runtime_provider.get("last_checked_at"),
            "last_discovered_at": runtime_provider.get("last_discovery_at"),
            "last_discovery_error": discovery_error,
            "models": {"discovered": discovered, "auto_canary": canary, "approved": approved},
        })
    return {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "catalogVersion": catalog().get("version", "unversioned"),
        "policy": state.get("policy", {}),
        "providers": output,
        "leases": lease_snapshot()["leases"],
        "runtimeUpdatedAt": state.get("updated_at"),
    }


async def refresh_provider_catalog(
    *,
    provider_ids: Optional[Sequence[str]] = None,
    env: Optional[Mapping[str, str]] = None,
    clients: Optional[Mapping[str, Any]] = None,
) -> Dict[str, Any]:
    if not auto_provision_enabled(env):
        return {"ok": True, "skipped": True, "reason": "auto_provision_disabled", **lease_snapshot()}
    from model_registry import ModelRegistry
    from model_discovery import discover

    values = _env_values(env)
    registry = ModelRegistry()
    if provider_ids:
        wanted = {str(item) for item in provider_ids}
        registry.providers = {key: value for key, value in registry.providers.items() if key in wanted}
    document = await discover(registry, env=values, clients=clients)
    now = datetime.now(timezone.utc).isoformat()
    with _LOCK:
        state = runtime_snapshot()
        leases = state.setdefault("model_leases", {})
        seen: Dict[str, set[str]] = {}
        for row in document.get("discovered_models", []):
            provider_id = str(row.get("provider") or "")
            template = _provider_template(provider_id)
            if not template:
                continue
            upstream = str(row.get("upstream_model") or row.get("id") or "")
            lease_id = lease_id_for(provider_id, upstream)
            seen.setdefault(provider_id, set()).add(lease_id)
            existing = leases.get(lease_id)
            if existing and existing.get("status") in _TERMINAL_LEASE_STATUSES:
                continue
            if existing and existing.get("status") == "disabled":
                continue
            if existing:
                if existing.get("pricing_source") != "manual_override":
                    price = resolve_price(template, upstream, row)
                    existing.update(price)
                existing["last_seen_at"] = now
                existing["updated_at"] = now
                continue
            lease = _model_spec(template, row, now)
            lease["last_seen_at"] = now
            leases[lease_id] = lease
        for provider_id, ids in seen.items():
            for lease_id, lease in leases.items():
                if lease.get("provider_id") == provider_id and lease_id not in ids and lease.get("status") == "active":
                    lease["status"] = "missing"
                    lease["traffic_percent"] = 0.0
                    lease["updated_at"] = now
        errors = {
            str(row.get("provider")): _safe_error(row.get("error"), values)
            for row in document.get("errors", [])
        }
        for template in catalog().get("providers", []):
            provider_id = str(template.get("id") or "")
            if provider_ids and provider_id not in {str(item) for item in provider_ids}:
                continue
            activation = _activation(template, values)
            row = state.setdefault("providers", {}).setdefault(provider_id, {})
            row.update({
                "configured": activation["configured"],
                "present_env": activation["present_env"],
                "missing_env": activation["missing_env"],
                "last_checked_at": now,
            })
            if provider_id in seen or (activation["configured"] and provider_id not in errors):
                row["last_discovery_at"] = now
                row.pop("last_discovery_error", None)
            if provider_id in errors:
                row["last_discovery_error"] = errors[provider_id]
        _write_runtime(state)
    safe_errors = [
        {"provider": row.get("provider"), "error": _safe_error(row.get("error"), values)}
        for row in document.get("errors", [])
    ]
    return {
        "ok": True,
        "discovered": len(document.get("discovered_models", [])),
        "errors": safe_errors,
        **lease_snapshot(),
    }


@dataclass(frozen=True)
class LeaseReservation:
    lease_id: str
    reserved_usd: float


class LeaseBudget:
    """Per-lease daily spend ceiling used by the execution path."""

    def reserve(self, lease_id: str, estimated_cost_usd: float) -> LeaseReservation:
        estimated = max(0.0, float(estimated_cost_usd or 0.0))
        with _LOCK:
            state = runtime_snapshot()
            lease = state.get("model_leases", {}).get(str(lease_id))
            if not lease or lease.get("status") != "active":
                from execution_controls import ExecutionAuthorizationError
                raise ExecutionAuthorizationError(f"auto-canary lease is not active: {lease_id}")
            today = datetime.now(timezone.utc).date().isoformat()
            if lease.get("spend_date") != today:
                lease["spend_date"] = today
                lease["spend_today_usd"] = 0.0
            cap = float(lease.get("daily_spend_cap_usd") or 0.0)
            projected = float(lease.get("spend_today_usd") or 0.0) + estimated
            if cap > 0 and projected > cap:
                from execution_controls import ExecutionAuthorizationError
                raise ExecutionAuthorizationError(f"auto-canary daily spend cap exceeded: {lease_id}")
            lease["spend_today_usd"] = round(projected, 8)
            lease["calls"] = int(lease.get("calls") or 0) + 1
            lease["updated_at"] = datetime.now(timezone.utc).isoformat()
            _write_runtime(state)
            return LeaseReservation(str(lease_id), estimated)

    def settle(self, reservation: Optional[LeaseReservation], actual_cost_usd: float = 0.0, *, success: bool = True) -> None:
        if reservation is None:
            return
        with _LOCK:
            state = runtime_snapshot()
            lease = state.get("model_leases", {}).get(reservation.lease_id)
            if not lease:
                return
            spend = float(lease.get("spend_today_usd") or 0.0) - reservation.reserved_usd + max(0.0, float(actual_cost_usd or 0.0))
            lease["spend_today_usd"] = round(max(0.0, spend), 8)
            if not success:
                lease["errors"] = int(lease.get("errors") or 0) + 1
            lease["updated_at"] = datetime.now(timezone.utc).isoformat()
            _write_runtime(state)


lease_budget = LeaseBudget()
