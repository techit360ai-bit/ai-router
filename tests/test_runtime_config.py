"""
Runtime readiness contract tests. Standalone:
    python3 tests/test_runtime_config.py
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from runtime_config import PROD_ENVS, RuntimeConfigError, assert_runtime_ready, runtime_checks  # noqa: E402


BASE_PROD_ENV = {
    "ENVIRONMENT": "production",
    "ALLOW_DEMO_AUTH": "false",
    "JWT_ALGORITHM": "HS256",
    "JWT_SECRET": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
    "DATABASE_URL": "postgresql://techit:secret@postgres.example:5432/techit_db",
    "REDIS_URL": "rediss://redis.example:6379",
    "CELERY_BROKER": "rediss://redis.example:6379",
    "MCP_BASE_URL": "https://api.techit.example/api/mcp",
    "OPENAI_API_KEY": "sk-live-openai",
    "ANTHROPIC_API_KEY": "sk-ant-live",
    "STRIPE_SECRET_KEY": "sk_live_real",
    "STRIPE_WEBHOOK_SECRET": "whsec_real",
}


def _failed_names(env: dict[str, str]) -> set[str]:
    return {check.name for check in runtime_checks(env) if not check.ok}


def test_valid_production_runtime_passes() -> None:
    assert _failed_names(BASE_PROD_ENV) == set()
    assert_runtime_ready(BASE_PROD_ENV)
    assert "production" in PROD_ENVS
    assert "staging" in PROD_ENVS


def test_production_demo_auth_fails_closed() -> None:
    env = {**BASE_PROD_ENV, "ALLOW_DEMO_AUTH": "true"}
    assert "auth.demo_disabled" in _failed_names(env)
    try:
        assert_runtime_ready(env)
    except RuntimeConfigError as exc:
        assert "ALLOW_DEMO_AUTH" in str(exc)
    else:
        raise AssertionError("assert_runtime_ready should fail when production demo auth is enabled")


def test_production_requires_provider_and_billing_keys() -> None:
    env = {
        **BASE_PROD_ENV,
        "OPENAI_API_KEY": "sk-replace-me",
        "ANTHROPIC_API_KEY": "",
        "STRIPE_WEBHOOK_SECRET": "whsec_replace_me",
    }
    failed = _failed_names(env)
    assert "provider.openai" in failed
    assert "provider.anthropic" in failed
    assert "billing.stripe_webhook" in failed


def test_production_rejects_local_dependency_urls() -> None:
    env = {
        **BASE_PROD_ENV,
        "DATABASE_URL": "postgresql://techit:secret@localhost:5432/techit_db",
        "REDIS_URL": "redis://127.0.0.1:6379",
        "CELERY_BROKER": "redis://127.0.0.1:6379",
    }
    failed = _failed_names(env)
    assert "database.url" in failed
    assert "redis.url" in failed
    assert "celery.broker" in failed


def test_development_allows_demo_auth_and_missing_provider_keys() -> None:
    env = {
        "ENVIRONMENT": "development",
        "ALLOW_DEMO_AUTH": "true",
        "JWT_SECRET": "dev-secret-key-that-is-long-enough-for-tests",
        "DATABASE_URL": "postgresql://techit:password@localhost:5432/techit_db",
        "REDIS_URL": "redis://localhost:6379",
        "MCP_BASE_URL": "https://api.techit.example/api/mcp",
    }
    assert _failed_names(env) == set()


def main() -> int:
    tests = [
        test_valid_production_runtime_passes,
        test_production_demo_auth_fails_closed,
        test_production_requires_provider_and_billing_keys,
        test_production_rejects_local_dependency_urls,
        test_development_allows_demo_auth_and_missing_provider_keys,
    ]
    for test in tests:
        try:
            test()
            print(f"  ok  {test.__name__}")
        except Exception as exc:  # noqa: BLE001
            print(f"  FAIL {test.__name__}: {type(exc).__name__}: {exc}")
            return 1
    print(f"\n{len(tests)} passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
