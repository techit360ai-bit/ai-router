from __future__ import annotations

import pytest

from execution_telemetry import ExecutionTelemetryRecorder
from live_domain_repository import LiveDomainDatabaseUnavailable, LiveDomainRepository
from runtime_config import EXPECTED_ALEMBIC_HEAD, RuntimeConfigError, database_engine_options, is_postgres_url, migration_head_check, require_postgres_url
from usage_settlement_client import UsageSettlementClient


def test_sqlite_database_urls_are_not_supported_by_runtime_outbox(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "sqlite:////tmp/forbidden.db")
    monkeypatch.setenv("BACKEND_USAGE_SETTLEMENT_URL", "https://backend.example/settle")
    monkeypatch.setenv("AI_ROUTER_SETTLEMENT_SECRET", "test-secret")
    client = UsageSettlementClient()
    with pytest.raises(RuntimeError, match="PostgreSQL"):
        client.outbox._initialize()


def test_live_domain_requires_explicit_test_seam_without_postgres(monkeypatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("ENVIRONMENT", "development")
    with pytest.raises(LiveDomainDatabaseUnavailable, match="PostgreSQL"):
        LiveDomainRepository()


def test_postgres_url_contract() -> None:
    assert is_postgres_url("postgresql://user:pass@host/db")
    assert is_postgres_url("postgres://user:pass@host/db")
    assert not is_postgres_url("sqlite:///tmp/db")


def test_live_domain_rejects_sqlite_database_url(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "sqlite:////tmp/forbidden.db")
    with pytest.raises(LiveDomainDatabaseUnavailable, match="postgres"):
        LiveDomainRepository()


def test_execution_telemetry_rejects_sqlite_database_url(monkeypatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "sqlite:////tmp/forbidden.db")
    with pytest.raises(RuntimeError, match="postgres"):
        ExecutionTelemetryRecorder()


def test_shared_runtime_database_contract_rejects_sqlite() -> None:
    with pytest.raises(RuntimeError, match="postgres"):
        require_postgres_url("sqlite:////tmp/forbidden.db")


def test_database_engine_options_reject_sqlite() -> None:
    with pytest.raises(RuntimeConfigError, match="postgres"):
        database_engine_options("sqlite:////tmp/forbidden.db")


def test_readiness_migration_head_check_fails_closed() -> None:
    assert migration_head_check(EXPECTED_ALEMBIC_HEAD).ok
    mismatch = migration_head_check("outdated-revision")
    assert not mismatch.ok
    assert "outdated-revision" in mismatch.detail
