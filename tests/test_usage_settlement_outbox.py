"""Durable Router-to-backend settlement delivery tests."""

from __future__ import annotations

import json

import pytest
from sqlalchemy import create_engine, text

from usage_settlement_client import UsageSettlementClient


@pytest.mark.asyncio
async def test_outbox_survives_client_restart_and_replays(monkeypatch, tmp_path) -> None:
    database_url = f"sqlite:///{tmp_path / 'settlement.db'}"
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("BACKEND_USAGE_SETTLEMENT_URL", "https://backend.example/internal/usage-settlement")
    monkeypatch.setenv("AI_ROUTER_SETTLEMENT_SECRET", "test-secret")
    monkeypatch.setenv("AI_SETTLEMENT_OUTBOX_AUTO_CREATE", "true")

    first = UsageSettlementClient()

    async def unavailable(_path, _body):
        return None

    monkeypatch.setattr(first, "_post", unavailable)
    result = await first.settle(
        request_id="request-1", user_id="user-1", workspace_id="workspace-1",
        task_type="chat", provider="openai", model="gpt-test", status="completed",
        prompt_tokens=3, completion_tokens=2, total_tokens=5, provider_cost_usd=0.01,
        latency_ms=25, attempt_count=1, cache_hit=False, grant_id="request-1",
        reservation_id="request-1", metadata={"execution_profile": "balanced"},
    )
    assert result == {"ok": True, "queued": True, "delivered": 0}

    with create_engine(database_url).connect() as connection:
        pending = connection.execute(text(
            "SELECT request_id, payload, delivered_at FROM usage_settlement_outbox"
        )).mappings().one()
    assert pending["request_id"] == "request-1"
    assert json.loads(pending["payload"])["provider_cost_usd"] == 0.01
    assert pending["delivered_at"] is None

    second = UsageSettlementClient()
    delivered_payloads = []

    async def available(path, body):
        delivered_payloads.append((path, body))
        return {"ok": True}

    monkeypatch.setattr(second, "_post", available)
    assert await second.outbox.flush() == 1
    assert delivered_payloads[0][0] == "/settle"
    assert delivered_payloads[0][1]["request_id"] == "request-1"

    with create_engine(database_url).connect() as connection:
        delivered_at = connection.execute(text(
            "SELECT delivered_at FROM usage_settlement_outbox WHERE request_id = 'request-1'"
        )).scalar_one()
    assert delivered_at is not None
