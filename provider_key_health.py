"""Live provider credential validation for readiness.

The static runtime check only rejects placeholder-shaped *values* by pattern, so
a key that is present but wrong (expired, revoked, truncated, or belonging to a
deleted project) passes ``/ready`` while every live AI call fails with 401. This
module performs a cheap authenticated probe against each configured provider,
caches the verdict for a short TTL, and exposes it as a readiness signal.

Transient failures (timeout, DNS, 5xx) are deliberately treated as *unknown*
rather than *invalid*: readiness must not flap on a probe glitch, but a genuine
401/403 is a hard, actionable failure.
"""

from __future__ import annotations

import json
import os
import threading
import time
import urllib.error
import urllib.request
from typing import Any, Dict

PROVIDER_KEY_ENVS: Dict[str, list[str]] = {
    "openai": ["OPENAI_API_KEY", "OPENAI_API_KEY_2", "OPENAI_API_KEY_3", "OPENAI_API_KEY_4"],
    "anthropic": ["ANTHROPIC_API_KEY", "ANTHROPIC_API_KEY_2", "ANTHROPIC_API_KEY_3", "ANTHROPIC_API_KEY_4"],
}

PROBE_URLS: Dict[str, str] = {
    "openai": "https://api.openai.com/v1/models",
    "anthropic": "https://api.anthropic.com/v1/models",
}

CACHE_TTL_SECONDS = max(30, int(os.getenv("AI_PROVIDER_KEY_CHECK_TTL_SECONDS", "300")))
TIMEOUT_SECONDS = max(2, int(os.getenv("AI_PROVIDER_KEY_CHECK_TIMEOUT_SECONDS", "6")))

_cache: Dict[str, Any] = {"checked_at": 0.0, "providers": {}}
_lock = threading.Lock()


def _enabled() -> bool:
    return os.getenv("AI_PROVIDER_KEY_CHECK", "live").strip().lower() not in {"0", "false", "no", "off", "disabled"}


def _headers(provider: str, key: str) -> Dict[str, str]:
    if provider == "anthropic":
        return {"x-api-key": key, "anthropic-version": "2023-06-01"}
    return {"Authorization": f"Bearer {key}"}


def _probe_status(provider: str, key: str) -> int:
    request = urllib.request.Request(PROBE_URLS[provider], headers=_headers(provider, key), method="GET")
    try:
        with urllib.request.urlopen(request, timeout=TIMEOUT_SECONDS) as response:
            return int(response.status)
    except urllib.error.HTTPError as exc:
        return int(exc.code)
    except Exception:  # noqa: BLE001 - network/DNS/TLS: unknown, not invalid
        return 0


def _validate_provider(provider: str) -> Dict[str, Any]:
    keys = [os.environ.get(name, "").strip() for name in PROVIDER_KEY_ENVS[provider]]
    keys = [key for key in keys if key]
    if not keys:
        return {"configured": 0, "valid": 0, "invalid": 0, "ok": False, "detail": f"no {provider} API key configured"}
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


def provider_key_health(force: bool = False) -> Dict[str, Dict[str, Any]]:
    """Return per-provider credential validity, cached for a short TTL."""
    if not _enabled():
        return {}
    now = time.time()
    with _lock:
        if not force and _cache["providers"] and (now - _cache["checked_at"]) < CACHE_TTL_SECONDS:
            return _cache["providers"]
    providers = {name: _validate_provider(name) for name in PROVIDER_KEY_ENVS}
    with _lock:
        _cache["checked_at"] = now
        _cache["providers"] = providers
    return providers
