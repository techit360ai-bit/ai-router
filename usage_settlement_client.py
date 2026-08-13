"""Authenticated Router -> backend usage settlement facts client.

This module deliberately does not calculate customer pricing, plan access or
credit balances. It signs execution facts and lets the backend settle them.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import os
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional


class UsageSettlementClient:
    def __init__(self) -> None:
        self.base_url = os.getenv("BACKEND_USAGE_SETTLEMENT_URL", "").rstrip("/")
        self.secret = os.getenv("AI_ROUTER_SETTLEMENT_SECRET", "")
        self.service_id = os.getenv("AI_ROUTER_SERVICE_ID", "ai-router")
        self.timeout = float(os.getenv("AI_ROUTER_SETTLEMENT_TIMEOUT_SECONDS", "5"))
        self.enabled = bool(self.base_url and self.secret)
        self.errors: list[str] = []
        self.outbox = UsageSettlementOutbox(self)

    @staticmethod
    def _encode(body: Dict[str, Any]) -> str:
        return json.dumps(body, separators=(",", ":"), ensure_ascii=False)

    def _headers(self, body: Dict[str, Any]) -> Dict[str, str]:
        timestamp = str(int(time.time()))
        encoded = self._encode(body)
        signature = hmac.new(self.secret.encode(), f"{timestamp}.{encoded}".encode(), hashlib.sha256).hexdigest()
        return {
            "Content-Type": "application/json",
            "X-TechIT-Service-Id": self.service_id,
            "X-TechIT-Timestamp": timestamp,
            "X-TechIT-Signature": signature,
        }

    async def _post(self, path: str, body: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not self.enabled:
            return None
        try:
            import httpx
            for attempt in range(3):
                try:
                    async with httpx.AsyncClient(timeout=self.timeout) as client:
                        response = await client.post(
                            f"{self.base_url}{path}",
                            content=self._encode(body).encode("utf-8"),
                            headers=self._headers(body),
                        )
                    if response.status_code < 500:
                        payload = response.json() if response.content else {}
                        if response.status_code >= 400:
                            # A 4xx is a permanent contract/security failure,
                            # not a transient delivery success. Keep it pending
                            # for operator repair but do not hot-loop retries.
                            self.errors.append(f"settlement rejected ({response.status_code}): {payload}"[:500])
                            return None
                        return payload
                except Exception as exc:  # noqa: BLE001 - settlement must not break AI execution
                    self.errors.append(str(exc)[:500])
                    if attempt == 2:
                        return None
                    await asyncio.sleep(0.25 * (2 ** attempt))
        except Exception as exc:  # noqa: BLE001
            self.errors.append(str(exc)[:500])
        return None

    async def settle(self, *, request_id: str, user_id: str, workspace_id: Optional[str], task_type: str,
                     provider: str, model: str, status: str, prompt_tokens: int,
                     completion_tokens: int, total_tokens: int, provider_cost_usd: Optional[float],
                     latency_ms: int, attempt_count: int, cache_hit: bool,
                     grant_id: Optional[str], reservation_id: Optional[str], metadata: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        body = {
            "request_id": request_id, "user_id": user_id, "workspace_id": workspace_id,
            "task_type": task_type, "provider": provider, "model": model, "status": status,
            "prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens,
            "total_tokens": total_tokens, "provider_cost_usd": provider_cost_usd,
            "latency_ms": latency_ms, "attempt_count": attempt_count, "cache_hit": cache_hit,
            "grant_id": grant_id, "reservation_id": reservation_id, "metadata": metadata,
        }
        if self.outbox.enabled:
            queued = await self.outbox.enqueue(body)
            if queued:
                delivered = await self.outbox.flush(limit=10)
                return {"ok": True, "queued": True, "delivered": delivered}
        return await self._post("/settle", body)

    async def start(self) -> None:
        await self.outbox.start()

    async def close(self) -> None:
        await self.outbox.stop()


class UsageSettlementOutbox:
    """Durable Router-owned transport queue containing execution facts only.

    The outbox deliberately has no balance, plan, price, credit, subscription,
    or margin fields. A process restart cannot lose a completed execution while
    the backend is temporarily unavailable.
    """

    def __init__(self, client: UsageSettlementClient) -> None:
        self.client = client
        self.database_url = os.getenv("DATABASE_URL", "").strip()
        self.enabled = client.enabled and bool(self.database_url) and os.getenv(
            "AI_SETTLEMENT_OUTBOX_ENABLED", "true"
        ).lower() not in {"0", "false", "no"}
        self.interval = max(1.0, float(os.getenv("AI_SETTLEMENT_OUTBOX_FLUSH_SECONDS", "10")))
        self._engine: Optional[Any] = None
        self._table: Optional[Any] = None
        self._worker: Optional[asyncio.Task[Any]] = None
        self.errors: list[str] = []

    def _initialize(self) -> None:
        if self._engine is not None:
            return
        from sqlalchemy import Column, DateTime, Integer, MetaData, String, Table, Text, create_engine

        metadata = MetaData()
        self._table = Table(
            "usage_settlement_outbox", metadata,
            Column("id", String(64), primary_key=True),
            Column("request_id", String(128), nullable=False, unique=True),
            Column("payload", Text, nullable=False),
            Column("attempts", Integer, nullable=False, default=0),
            Column("last_error", Text),
            Column("created_at", DateTime(timezone=True), nullable=False),
            Column("updated_at", DateTime(timezone=True), nullable=False),
            Column("delivered_at", DateTime(timezone=True)),
        )
        engine_options: Dict[str, Any] = {"pool_pre_ping": True}
        if self.database_url.startswith("sqlite"):
            engine_options["connect_args"] = {"check_same_thread": False}
        self._engine = create_engine(self.database_url, **engine_options)
        if os.getenv("AI_SETTLEMENT_OUTBOX_AUTO_CREATE", "false").lower() in {"1", "true", "yes"}:
            metadata.create_all(self._engine, tables=[self._table])

    async def enqueue(self, body: Dict[str, Any]) -> bool:
        if not self.enabled:
            return False
        try:
            # This transaction is intentionally tiny. Keeping it synchronous
            # also avoids orphaned default-executor threads during worker
            # shutdown and test lifecycles.
            return self._enqueue_sync(body)
        except Exception as exc:  # noqa: BLE001 - fallback direct delivery remains available
            self.errors.append(str(exc)[:500])
            return False

    def _enqueue_sync(self, body: Dict[str, Any]) -> bool:
        from sqlalchemy import select
        from sqlalchemy.exc import IntegrityError

        self._initialize()
        assert self._engine is not None and self._table is not None
        request_id = str(body.get("request_id") or "")
        if not request_id:
            raise ValueError("settlement outbox requires request_id")
        now = datetime.now(timezone.utc)
        with self._engine.begin() as connection:
            existing = connection.execute(
                select(self._table.c.payload).where(self._table.c.request_id == request_id)
            ).scalar_one_or_none()
            payload = self.client._encode(body)
            if existing is not None:
                if existing != payload:
                    raise ValueError("settlement outbox request_id payload conflict")
                return True
            try:
                connection.execute(self._table.insert().values(
                    id=request_id, request_id=request_id, payload=payload, attempts=0,
                    created_at=now, updated_at=now,
                ))
            except IntegrityError:
                return True
        return True

    async def flush(self, limit: int = 100) -> int:
        if not self.enabled:
            return 0
        try:
            rows = self._pending_sync(limit)
        except Exception as exc:  # noqa: BLE001
            self.errors.append(str(exc)[:500])
            return 0
        delivered = 0
        for row in rows:
            payload = json.loads(row["payload"])
            result = await self.client._post("/settle", payload)
            error = None if result is not None else (self.client.errors[-1] if self.client.errors else "delivery_failed")
            try:
                self._record_attempt_sync(row["request_id"], error)
            except Exception as exc:  # noqa: BLE001
                self.errors.append(str(exc)[:500])
            if result is not None:
                delivered += 1
        return delivered

    def _pending_sync(self, limit: int) -> list[Dict[str, Any]]:
        from sqlalchemy import select

        self._initialize()
        assert self._engine is not None and self._table is not None
        statement = select(
            self._table.c.request_id, self._table.c.payload
        ).where(self._table.c.delivered_at.is_(None)).order_by(self._table.c.created_at).limit(max(1, limit))
        with self._engine.connect() as connection:
            return [dict(row._mapping) for row in connection.execute(statement)]

    def _record_attempt_sync(self, request_id: str, error: Optional[str]) -> None:
        self._initialize()
        assert self._engine is not None and self._table is not None
        now = datetime.now(timezone.utc)
        values: Dict[str, Any] = {
            "attempts": self._table.c.attempts + 1,
            "last_error": error,
            "updated_at": now,
        }
        if error is None:
            values["delivered_at"] = now
        with self._engine.begin() as connection:
            connection.execute(
                self._table.update().where(self._table.c.request_id == request_id).values(**values)
            )

    async def start(self) -> None:
        if not self.enabled or self._worker is not None:
            return
        self._worker = asyncio.create_task(self._run(), name="usage-settlement-outbox")

    async def _run(self) -> None:
        while True:
            await self.flush()
            await asyncio.sleep(self.interval)

    async def stop(self) -> None:
        if self._worker is None:
            return
        self._worker.cancel()
        try:
            await self._worker
        except asyncio.CancelledError:
            pass
        self._worker = None
