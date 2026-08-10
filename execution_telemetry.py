"""Durable provider-attempt telemetry for the execution-only Router."""

from __future__ import annotations

import asyncio
import os
from typing import Any, Mapping, Optional


class ExecutionTelemetryRecorder:
    """Persist attempt records when DATABASE_URL is configured.

    The in-memory command-layer log is always populated first. Persistence is
    best-effort so a monitoring outage does not turn into an AI outage.
    """

    def __init__(self) -> None:
        self.enabled = os.getenv("AI_EXECUTION_TELEMETRY_ENABLED", "true").lower() not in {
            "0", "false", "no"
        }
        self.database_url = os.getenv("DATABASE_URL", "")
        self._engine: Optional[Any] = None
        self.errors: list[str] = []

    async def record_attempt(self, event: Mapping[str, Any]) -> None:
        if not self.enabled or not self.database_url:
            return
        try:
            await asyncio.to_thread(self._record_sync, dict(event))
        except Exception as exc:  # noqa: BLE001 - telemetry must not break execution
            self.errors.append(str(exc)[:500])

    def _record_sync(self, event: dict[str, Any]) -> None:
        from sqlalchemy import create_engine, text

        if self._engine is None:
            self._engine = create_engine(self.database_url, pool_pre_ping=True)
        statement = text("""
            INSERT INTO ai_usage_ledger (
                request_id, user_id, workspace_id, provider, model, task_type,
                tokens_used, prompt_tokens, completion_tokens, provider_cost_usd,
                latency_ms, status, attempt_number, error_type, error_message,
                cache_hit, ip_protected, metadata, created_at
            ) VALUES (
                :request_id, :user_id, :workspace_id, :provider, :model, :task_type,
                :total_tokens, :prompt_tokens, :completion_tokens, :provider_cost_usd,
                :latency_ms, :status, :attempt, :error_type, :error_message,
                :cache_hit, :ip_protected, CAST(:metadata AS JSONB), NOW()
            )
        """)
        import json
        params = {
            **event,
            "total_tokens": int(event.get("total_tokens") or 0),
            "prompt_tokens": int(event.get("prompt_tokens") or 0),
            "completion_tokens": int(event.get("completion_tokens") or 0),
            "provider_cost_usd": event.get("provider_cost_usd"),
            "error_message": event.get("error"),
            "cache_hit": bool(event.get("cache_hit", False)),
            "ip_protected": bool(event.get("ip_protected", False)),
            "metadata": json.dumps(event.get("metadata") or {}),
        }
        with self._engine.begin() as connection:
            connection.execute(statement, params)
