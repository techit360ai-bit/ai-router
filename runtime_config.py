"""Runtime config checks shared by startup, readiness, and tests."""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping
from urllib.parse import urlparse


PROD_ENVS = {"production", "staging"}
LOCAL_HOSTS = {"localhost", "127.0.0.1", "0.0.0.0"}
AI_ROUTER_MODES = {"deterministic", "hybrid", "llm"}
EXPECTED_ALEMBIC_HEAD = "d5e6f7a8b9c0"


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


def ai_router_mode(env: Mapping[str, str] | None = None) -> str:
    values = env or os.environ
    mode = values.get("AI_ROUTER_MODE", "llm").strip().lower()
    return mode if mode in AI_ROUTER_MODES else "invalid"


def _is_placeholder(value: str) -> bool:
    return any(token in value.lower() for token in ("replace", "your_key_here", "test-secret"))


def _check_url(name: str, value: str | None, schemes: set[str], env_name: str) -> RuntimeCheck:
    if not value:
        return RuntimeCheck(name, False, f"{name} is required")
    parsed = urlparse(value)
    if parsed.scheme not in schemes:
        # Report only the scheme, never the full value: URLs such as
        # DATABASE_URL can embed credentials and /ready may be public.
        return RuntimeCheck(
            name,
            False,
            f"{name} must use one of: {', '.join(sorted(schemes))} (got scheme '{parsed.scheme or 'none'}')",
        )
    if env_name in PROD_ENVS and parsed.hostname in LOCAL_HOSTS:
        return RuntimeCheck(name, False, f"{name} cannot point at localhost in production/staging")
    return RuntimeCheck(name, True)


def runtime_checks(env: Mapping[str, str] | None = None) -> list[RuntimeCheck]:
    values = env or os.environ
    env_name = environment(values)
    checks: list[RuntimeCheck] = []

    mode = ai_router_mode(values)
    checks.append(RuntimeCheck(
        "ai.mode",
        mode in AI_ROUTER_MODES,
        "AI_ROUTER_MODE must be deterministic, hybrid, or llm",
    ))

    allow_demo = bool_env(values.get("ALLOW_DEMO_AUTH"), default=True)
    checks.append(RuntimeCheck(
        "auth.demo_disabled",
        not (env_name in PROD_ENVS and allow_demo),
        "ALLOW_DEMO_AUTH must be false in production/staging",
    ))

    secret = values.get("JWT_SECRET") or values.get("SECRET_KEY") or ""
    public_key = values.get("JWT_PUBLIC_KEY") or ""
    algorithm = (values.get("JWT_ALGORITHM") or "HS256").strip().upper()

    # The platform backend mints RS256 tokens in production/staging (HS256 is
    # forbidden there by jwtKeyService.js), while dev/test uses HS256. Verify
    # whichever algorithm the issuer actually uses instead of hard-coding HS256.
    if algorithm in {"RS256", "RS384", "RS512"}:
        checks.append(RuntimeCheck(
            "auth.jwt_public_key",
            bool(public_key) and not _is_placeholder(public_key),
            "JWT_PUBLIC_KEY is required and must not be a placeholder when JWT_ALGORITHM uses RSA",
        ))
    else:
        checks.append(RuntimeCheck(
            "auth.jwt_secret",
            bool(secret) and len(secret) >= 32 and not _is_placeholder(secret),
            "JWT_SECRET must be set, strong, and non-placeholder",
        ))

    checks.append(RuntimeCheck(
        "auth.jwt_algorithm",
        algorithm in {"HS256", "HS384", "HS512", "RS256", "RS384", "RS512"},
        "JWT_ALGORITHM must be a supported HSnnn or RSnnn algorithm",
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

    if env_name in PROD_ENVS and mode == "llm":
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

        if bool_env(values.get("AGENTROUTER_ENABLED"), default=False):
            agentrouter_key = values.get("AGENTROUTER_API_KEY", "")
            checks.append(RuntimeCheck(
                "provider.agentrouter",
                bool(agentrouter_key) and not _is_placeholder(agentrouter_key),
                "AGENTROUTER_API_KEY is required when AgentRouter is enabled",
            ))
            checks.append(_check_url(
                "provider.agentrouter_base_url",
                values.get("AGENTROUTER_BASE_URL") or "https://agentrouter.org/v1",
                {"https"},
                env_name,
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
        # Placeholder completions are a local-dev convenience. They must never be
        # reachable in production/staging, where output is treated as real.
        checks.append(RuntimeCheck(
            "ai.placeholder_responses_disabled",
            not bool_env(values.get("ALLOW_AI_PLACEHOLDER_RESPONSES"), default=False),
            "ALLOW_AI_PLACEHOLDER_RESPONSES must be false in production/staging",
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
    require_postgres_url(database_url)
    values = env or os.environ
    connect_timeout = read_positive_int(values, "DATABASE_CONNECT_TIMEOUT_SECONDS", 5, 60)
    options: dict[str, object] = {
        "pool_pre_ping": True,
        # Keep the whole platform under the shared RDS max_connections budget.
        # The AI router runs several SQLAlchemy engines per process and the
        # uvicorn + celery processes together previously held ~60 of the 81
        # connections, which starved the backend with "remaining connection
        # slots are reserved for roles with privileges of the rds_reserved
        # role". Override per deployment if more headroom is ever needed.
        "pool_size": read_positive_int(values, "DATABASE_POOL_SIZE", 2, 20),
        "max_overflow": read_positive_int(values, "DATABASE_MAX_OVERFLOW", 2, 20),
        "pool_timeout": read_positive_int(values, "DATABASE_POOL_TIMEOUT_SECONDS", 5, 60),
    }
    options["connect_args"] = {"connect_timeout": connect_timeout}
    return options


def is_postgres_url(database_url: str | None) -> bool:
    """Return whether a database URL targets the supported PostgreSQL authority."""
    return bool(database_url) and urlparse(str(database_url)).scheme in {"postgres", "postgresql"}


def require_postgres_url(database_url: str | None, setting: str = "DATABASE_URL") -> str:
    """Return a validated PostgreSQL URL or fail closed."""
    value = str(database_url or "").strip()
    if not value:
        raise RuntimeConfigError(f"{setting} is required")
    if not is_postgres_url(value):
        raise RuntimeConfigError(f"{setting} must use postgres:// or postgresql://")
    return value


def migration_head_check(actual_head: str | None) -> RuntimeCheck:
    """Return the readiness result for the deployed PostgreSQL schema revision."""
    return RuntimeCheck(
        "database.migration_head",
        actual_head == EXPECTED_ALEMBIC_HEAD,
        f"expected={EXPECTED_ALEMBIC_HEAD}; actual={actual_head or 'none'}",
    )
