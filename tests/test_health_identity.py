"""Build identity + actionable config failure detail for probes."""

from __future__ import annotations

import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("SECRET_KEY", "unit-test-secret-value-that-is-long-enough")
os.environ.setdefault("ENVIRONMENT", "development")

import main as main_module  # noqa: E402
from runtime_config import _check_url  # noqa: E402


def test_health_reports_build_identity():
    body = asyncio.run(main_module.health())
    assert body["status"] == "healthy"
    for key in ("service", "version", "sha", "builtAt", "environment"):
        assert key in body
    assert body["service"] == "ai-router"


def test_version_matches_health_identity():
    health = asyncio.run(main_module.health())
    version = asyncio.run(main_module.version())
    for key in ("service", "version", "sha", "builtAt", "environment"):
        assert version[key] == health[key]


def test_check_url_reports_scheme_only():
    check = _check_url("mcp.base_url", "http://backend.techitnetwork.com/api/mcp", {"https"}, "production")
    assert check.ok is False
    assert "got scheme 'http'" in check.detail
    # Never echo the full URL; /ready can be public and URLs may embed credentials.
    assert "backend.techitnetwork.com" not in check.detail


def test_check_url_accepts_https():
    check = _check_url("mcp.base_url", "https://backend.techitnetwork.com/api/mcp", {"https"}, "production")
    assert check.ok is True


def test_partial_provider_configuration_is_reported_without_failing_by_default(monkeypatch):
    providers = [{
        "id": "azure_openai",
        "detected": True,
        "configured": False,
        "missing_env": ["AZURE_OPENAI_BASE_URL"],
        "missing_credentials": [],
    }]
    monkeypatch.delenv("AI_STRICT_PROVIDER_READINESS", raising=False)
    checks = main_module._provider_configuration_checks(
        providers,
        main_module._strict_provider_readiness_enabled(),
    )
    assert checks[0].ok is True
    assert "AZURE_OPENAI_BASE_URL" in checks[0].detail


def test_strict_provider_readiness_fails_on_partial_configuration(monkeypatch):
    monkeypatch.setenv("AI_STRICT_PROVIDER_READINESS", "true")
    checks = main_module._provider_configuration_checks(
        [{"id": "azure_openai", "detected": True, "configured": False, "missing_env": ["AZURE_OPENAI_BASE_URL"]}],
        main_module._strict_provider_readiness_enabled(),
    )
    assert checks[0].ok is False
