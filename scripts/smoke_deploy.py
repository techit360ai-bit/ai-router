#!/usr/bin/env python3
"""Post-deploy smoke probes for ai-router and its authenticated boundary."""

from __future__ import annotations

import os
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen


def env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except ValueError:
        return default


TIMEOUT = env_int("SMOKE_TIMEOUT_SECONDS", 10)

CHECKS = [
    {"name": "ai-router-health", "base": "AI_ROUTER_BASE_URL", "path": "/health", "statuses": {200}},
    {
        "name": "dashboard-auth-boundary",
        "base": "AI_ROUTER_BASE_URL",
        "path": "/api/v1/dashboard/intelligence",
        "statuses": {401},
    },
]

if os.getenv("SMOKE_BEARER_TOKEN"):
    CHECKS.append(
        {
            "name": "dashboard-authenticated",
            "base": "AI_ROUTER_BASE_URL",
            "path": "/api/v1/dashboard/intelligence",
            "statuses": {200},
            "token": os.environ["SMOKE_BEARER_TOKEN"],
        }
    )


def probe(check: dict[str, object]) -> None:
    base_name = str(check["base"])
    base = os.getenv(base_name)
    if not base:
        print(f"skip {check['name']}: {base_name} unset")
        return

    url = urljoin(base.rstrip("/") + "/", str(check["path"]).lstrip("/"))
    headers = {}
    if check.get("token"):
        headers["Authorization"] = f"Bearer {check['token']}"

    request = Request(url, headers=headers)
    expected = check["statuses"]
    try:
        with urlopen(request, timeout=TIMEOUT) as response:  # noqa: S310 - operator-provided URL.
            status = response.status
    except HTTPError as exc:
        status = exc.code
    except URLError as exc:
        raise RuntimeError(f"{url} failed: {exc}") from exc

    if status not in expected:
        expected_str = "/".join(str(code) for code in sorted(expected))
        raise RuntimeError(f"{url} returned {status}; expected {expected_str}")
    print(f"ok {check['name']} {status}")


def main() -> int:
    try:
        for check in CHECKS:
            probe(check)
    except Exception as exc:  # noqa: BLE001
        print(str(exc), file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
