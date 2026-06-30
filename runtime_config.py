"""Runtime config checks shared by startup, readiness, and tests."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping
from urllib.parse import urlparse


PROD_ENVS = {"production", "staging"}
LOCAL_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0"}


@dataclass(frozen=True)
class RuntimeCheck:
    name: str
    ok: bool
    detail: str = "ok"


class RuntimeConfigError(RuntimeError):
    pass


def environment(env: Mapping[str, str] | None = None) -> str:
    values = env or os.environ
    return values.get("ENVIRONMENT", "development").strip().lower()


def bool_env(value: str | None, *, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _is_placeholder(value: str) -> bool:
    return any(token in value.lower() for token in ("replace", "your_key_here", "test-secret"))


def _check_url(name: str, value: str | None, schemes: set[str], env_name: str) -> RuntimeCheck:
    if not value:
        return RuntimeCheck(name, False, f"{name} is required")
    parsed = urlparse(value)
    if parsed.scheme not in schemes:
        return RuntimeCheck(name, False, f"{name} must use one of: {', '.join(sorted(schemes))}")
    if env_name in PROD_ENVS and parsed.hostname in LOCAL_HOSTS:
        return RuntimeCheck(name, False, f"{name} cannot point at localhost in production/staging")
    return RuntimeCheck(name, True)


def runtime_checks(env: Mapping[str, str] | None = None) -> list[RuntimeCheck]:
    values = env or os.environ
    env_name = environment(values)
    checks: list[RuntimeCheck] = []

    allow_demo = bool_env(values.get("ALLOW_DEMO_AUTH"), default=True)
    checks.append(RuntimeCheck(
        "auth.demo_disabled",
        not (env_name in PROD_ENVS and allow_demo),
        "ALLOW_DEMO_AUTH must be false in production/staging",
    ))

    secret = values.get("JWT_SECRET") or values.get("SECRET_KEY") or ""
    checks.append(RuntimeCheck(
        "auth.jwt_secret",
        bool(secret) and len(secret) >= 32 and not _is_placeholder(secret),
        "JWT_SECRET must be set, strong, and non-placeholder",
    ))

    checks.append(RuntimeCheck(
        "auth.jwt_algorithm",
        values.get("JWT_ALGORITHM", "HS256") == "HS256",
        "JWT_ALGORITHM must be HS256",
    ))

    checks.append(_check_url("database.url", values.get("DATABASE_URL"), {"postgres", "postgresql"}, env_name))
    checks.append(_check_url("redis.url", values.get("REDIS_URL"), {"redis", "rediss"}, env_name))
    checks.append(_check_url("celery.broker", values.get("CELERY_BROKER") or values.get("REDIS_URL"), {"redis", "rediss"}, env_name))
    checks.append(_check_url("mcp.base_url", values.get("MCP_BASE_URL"), {"https"}, env_name))

    if env_name in PROD_ENVS:
        for name, env_key in (
            ("provider.openai", "OPENAI_API_KEY"),
            ("provider.anthropic", "ANTHROPIC_API_KEY"),
            ("billing.stripe_secret", "STRIPE_SECRET_KEY"),
            ("billing.stripe_webhook", "STRIPE_WEBHOOK_SECRET"),
        ):
            value = values.get(env_key, "")
            checks.append(RuntimeCheck(
                name,
                bool(value) and not _is_placeholder(value),
                f"{env_key} is required and must not be a placeholder",
            ))

    return checks


def assert_runtime_ready(env: Mapping[str, str] | None = None) -> None:
    failed = [check for check in runtime_checks(env) if not check.ok]
    if failed:
        details = "; ".join(f"{check.name}: {check.detail}" for check in failed)
        raise RuntimeConfigError(details)
