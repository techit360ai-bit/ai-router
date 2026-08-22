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


def read_positive_int(
    env: Mapping[str, str] | None,
    name: str,
    default: int,
    cap: int,
) -> int:
    values = env or os.environ
    try:
        value = int(values.get(name, str(default)))
    except ValueError:
        return default
    return min(max(value, 1), cap)


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

    allowed_origins = [item.strip() for item in values.get("ALLOWED_ORIGINS", "").split(",") if item.strip()]
    if env_name in PROD_ENVS:
        secure_origins = bool(allowed_origins) and all(
            origin != "*" and urlparse(origin).scheme == "https" and urlparse(origin).hostname not in LOCAL_HOSTS
            for origin in allowed_origins
        )
        checks.append(RuntimeCheck(
            "http.cors_origins",
            secure_origins,
            "ALLOWED_ORIGINS must list only non-local https origins in production/staging",
        ))

    if env_name in PROD_ENVS:
        checks.append(RuntimeCheck(
            "auth.jwt_issuer",
            bool(values.get("JWT_ISSUER")),
            "JWT_ISSUER is required in production/staging",
        ))
        checks.append(RuntimeCheck(
            "auth.jwt_audience",
            bool(values.get("JWT_AUDIENCE")),
            "JWT_AUDIENCE is required in production/staging",
        ))

    checks.append(_check_url("database.url", values.get("DATABASE_URL"), {"postgres", "postgresql"}, env_name))
    checks.append(_check_url("redis.url", values.get("REDIS_URL"), {"redis", "rediss"}, env_name))
    checks.append(_check_url("celery.broker", values.get("CELERY_BROKER") or values.get("REDIS_URL"), {"redis", "rediss"}, env_name))
    checks.append(_check_url("mcp.base_url", values.get("MCP_BASE_URL"), {"https"}, env_name))

    if env_name in PROD_ENVS:
        for name, env_key in (
            ("provider.openai", "OPENAI_API_KEY"),
            ("provider.anthropic", "ANTHROPIC_API_KEY"),
        ):
            value = values.get(env_key, "")
            checks.append(RuntimeCheck(
                name,
                bool(value) and not _is_placeholder(value),
                f"{env_key} is required and must not be a placeholder",
            ))

        if bool_env(values.get("REQUIRE_AI_EXECUTION_GRANT"), default=False):
            grant_secret = values.get("AI_EXECUTION_GRANT_SECRET") or secret
            checks.append(RuntimeCheck(
                "execution_grant.secret",
                bool(grant_secret) and len(grant_secret) >= 32 and not _is_placeholder(grant_secret),
                "AI_EXECUTION_GRANT_SECRET or JWT_SECRET must securely verify execution grants",
            ))

        checks.append(_check_url(
            "settlement.backend_url",
            values.get("BACKEND_USAGE_SETTLEMENT_URL"),
            {"https"},
            env_name,
        ))
        settlement_secret = values.get("AI_ROUTER_SETTLEMENT_SECRET", "")
        checks.append(RuntimeCheck(
            "settlement.hmac_secret",
            len(settlement_secret) >= 32 and not _is_placeholder(settlement_secret),
            "AI_ROUTER_SETTLEMENT_SECRET must be set, strong, and non-placeholder",
        ))
        admin_telemetry_secret = values.get("ADMIN_AI_ROUTER_TELEMETRY_SECRET", "")
        checks.append(RuntimeCheck(
            "admin_telemetry.hmac_secret",
            len(admin_telemetry_secret) >= 32 and not _is_placeholder(admin_telemetry_secret),
            "ADMIN_AI_ROUTER_TELEMETRY_SECRET must be set, strong, and non-placeholder",
        ))
        checks.append(RuntimeCheck(
            "execution_grant.required",
            bool_env(values.get("REQUIRE_AI_EXECUTION_GRANT"), default=False),
            "REQUIRE_AI_EXECUTION_GRANT must be true in production/staging",
        ))
        storage_key = values.get("AWS_ACCESS_KEY_ID", "")
        storage_secret = values.get("AWS_SECRET_ACCESS_KEY", "")
        checks.append(RuntimeCheck(
            "storage.private_config",
            bool(storage_key and storage_secret)
            and storage_key != "test-access-key"
            and storage_secret != "test-secret-key",
            "Production file storage credentials must be configured and non-placeholder",
        ))
        checks.append(RuntimeCheck(
            "storage.bucket",
            bool(values.get("AWS_S3_BUCKET")) and not _is_placeholder(values.get("AWS_S3_BUCKET", "")),
            "AWS_S3_BUCKET is required and must be non-placeholder",
        ))
        storage_endpoint = values.get("AWS_S3_ENDPOINT", "").strip()
        if storage_endpoint:
            checks.append(_check_url("storage.endpoint", storage_endpoint, {"https"}, env_name))

    return checks


def assert_runtime_ready(env: Mapping[str, str] | None = None) -> None:
    failed = [check for check in runtime_checks(env) if not check.ok]
    if failed:
        details = "; ".join(f"{check.name}: {check.detail}" for check in failed)
        raise RuntimeConfigError(details)


def database_engine_options(database_url: str, env: Mapping[str, str] | None = None) -> dict[str, object]:
    """Build bounded SQLAlchemy options for production readiness probes.

    The readiness endpoint must fail quickly when Postgres is unreachable. These
    defaults keep a bad database connection from holding /ready open for tens of
    seconds while still allowing operators to loosen the timeout temporarily.
    """
    values = env or os.environ
    connect_timeout = read_positive_int(values, "DATABASE_CONNECT_TIMEOUT_SECONDS", 5, 60)
    options: dict[str, object] = {
        "pool_pre_ping": True,
        "pool_size": 5,
        "max_overflow": 5,
        "pool_timeout": read_positive_int(values, "DATABASE_POOL_TIMEOUT_SECONDS", 5, 60),
    }
    if urlparse(database_url).scheme.startswith("postgres"):
        options["connect_args"] = {"connect_timeout": connect_timeout}
    return options
