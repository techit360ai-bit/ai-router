#!/usr/bin/env python3
"""Validate the ai-router production deployment environment contract."""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
MANIFEST_PATH = ROOT / "docs" / "deployment-manifest.json"
REQUIRED_SERVICES = {"ai-router-api", "ai-router-worker", "ai-router-scheduler", "postgres-pgvector", "redis"}
PROD_ENVS = {"production", "staging"}


def fail(message: str) -> None:
    raise ValueError(message)


def require_value(name: str) -> str:
    value = os.getenv(name)
    if value is None or value == "":
        fail(f"{name} is required")
    return value


def parse_env_example(path: Path) -> set[str]:
    keys: set[str] = set()
    for raw_line in path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        match = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)=", line)
        if match:
            keys.add(match.group(1))
    return keys


def require_url(name: str, schemes: set[str]) -> str:
    value = require_value(name)
    parsed = urlparse(value)
    if parsed.scheme not in schemes:
        fail(f"{name} must use one of: {', '.join(sorted(schemes))}")
    if environment() in PROD_ENVS and parsed.hostname in {"localhost", "127.0.0.1", "0.0.0.0"}:
        fail(f"{name} cannot point at localhost in production/staging")
    return value


def environment() -> str:
    return os.getenv("ENVIRONMENT", "production").strip().lower()


def validate_manifest() -> None:
    manifest = json.loads(MANIFEST_PATH.read_text())
    if manifest.get("version") != 1:
        fail("deployment manifest version must be 1")
    services = manifest.get("services")
    if not isinstance(services, list):
        fail("deployment manifest must list services")
    service_names = {service.get("name") for service in services}
    missing = REQUIRED_SERVICES - service_names
    if missing:
        fail(f"deployment manifest is missing services: {', '.join(sorted(missing))}")

    for service in services:
        name = service.get("name")
        if not name:
            fail("deployment manifest service is missing name")
        required_env = service.get("requiredEnv", [])
        env_file = service.get("envFile")
        if required_env and env_file:
            keys = parse_env_example(ROOT / env_file)
            for key in required_env:
                if key not in keys:
                    fail(f"{env_file} is missing {key} required by {name}")
        if name in {"ai-router-api", "postgres-pgvector", "redis"} and "healthCheck" not in service:
            fail(f"{name} must declare a healthCheck")


def validate_auth() -> None:
    env = environment()
    if env != "production":
        fail("ENVIRONMENT must be production for this contract")
    if os.getenv("ALLOW_DEMO_AUTH", "").lower() not in {"false", "0", "no"}:
        fail("ALLOW_DEMO_AUTH must be false in production")
    if os.getenv("JWT_ALGORITHM", "HS256") != "HS256":
        fail("JWT_ALGORITHM must be HS256 to match BACKEND-issued tokens")
    secret = require_value("JWT_SECRET")
    if len(secret) < 32:
        fail("JWT_SECRET must be at least 32 characters")
    if re.search(r"change|replace|secret|test-secret", secret, re.IGNORECASE):
        fail("JWT_SECRET must not be a placeholder or weak demo value")


def validate_datastores() -> None:
    require_value("POSTGRES_PASSWORD")
    require_url("DATABASE_URL", {"postgresql", "postgres"})
    redis_url = require_url("REDIS_URL", {"redis", "rediss"})
    celery = require_url("CELERY_BROKER", {"redis", "rediss"})
    if celery != redis_url:
        fail("CELERY_BROKER must match REDIS_URL unless the manifest is updated for a separate broker")


def validate_urls() -> None:
    origins = [origin.strip() for origin in require_value("ALLOWED_ORIGINS").split(",") if origin.strip()]
    if not origins:
        fail("ALLOWED_ORIGINS must include at least one origin")
    for origin in origins:
        if origin == "*":
            fail("ALLOWED_ORIGINS cannot contain * in production")
        require_url_value("ALLOWED_ORIGINS", origin, {"https"})

    require_url("MCP_BASE_URL", {"https"})
    timeout = require_value("MCP_TIMEOUT")
    try:
        timeout_value = float(timeout)
    except ValueError as exc:
        raise ValueError("MCP_TIMEOUT must be numeric") from exc
    if timeout_value <= 0 or timeout_value > 60:
        fail("MCP_TIMEOUT must be > 0 and <= 60 seconds")


def require_url_value(name: str, value: str, schemes: set[str]) -> None:
    parsed = urlparse(value)
    if parsed.scheme not in schemes:
        fail(f"{name} value {value} must use one of: {', '.join(sorted(schemes))}")
    if environment() in PROD_ENVS and parsed.hostname in {"localhost", "127.0.0.1", "0.0.0.0"}:
        fail(f"{name} value {value} cannot point at localhost in production/staging")


def validate_integrations() -> None:
    for name in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "STRIPE_SECRET_KEY", "STRIPE_WEBHOOK_SECRET"):
        value = require_value(name)
        if "replace" in value.lower() or "your_key_here" in value.lower():
            fail(f"{name} must not be a placeholder")


def main() -> int:
    try:
        validate_manifest()
        validate_auth()
        validate_datastores()
        validate_urls()
        validate_integrations()
    except Exception as exc:  # noqa: BLE001
        print(str(exc), file=sys.stderr)
        return 1

    print("ai-router deployment env contract OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
