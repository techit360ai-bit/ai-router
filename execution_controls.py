"""Execution-only authorization, caching, rate limiting, and provider health.

These controls protect AI infrastructure. They do not implement subscriptions,
payments, credits, plans, or customer paywalls.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import threading
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, Iterable, Mapping, Optional


class ExecutionAuthorizationError(PermissionError):
    pass


@dataclass(frozen=True)
class ExecutionGrant:
    subject: str
    workspace_id: Optional[str]
    request_id: str
    task_type: Optional[str]
    execution_profile: str = "balanced"
    allowed_model_ids: tuple[str, ...] = ()
    max_input_tokens: Optional[int] = None
    max_output_tokens: Optional[int] = None
    max_provider_cost_usd: Optional[float] = None
    grant_id: Optional[str] = None
    reservation_id: Optional[str] = None
    claims: Dict[str, Any] = field(default_factory=dict)


class ExecutionGrantVerifier:
    """Verify short-lived backend grants without interpreting billing state."""

    def __init__(self, secret: Optional[str] = None) -> None:
        self.secret = secret or os.getenv("AI_EXECUTION_GRANT_SECRET") or os.getenv("JWT_SECRET")
        self.algorithm = os.getenv("AI_EXECUTION_GRANT_ALGORITHM", "HS256")
        self.issuer = os.getenv("AI_EXECUTION_GRANT_ISSUER", "techit-backend")
        self.audience = os.getenv("AI_EXECUTION_GRANT_AUDIENCE", "techit-ai-router")

    def verify(self, token: str) -> ExecutionGrant:
        if not token:
            raise ExecutionAuthorizationError("AI execution grant is required")
        if not self.secret:
            raise ExecutionAuthorizationError("AI execution grant verification is not configured")
        try:
            from jose import JWTError, jwt
            claims = jwt.decode(
                token,
                self.secret,
                algorithms=[self.algorithm],
                issuer=self.issuer,
                audience=self.audience,
            )
        except JWTError as exc:
            raise ExecutionAuthorizationError("Invalid or expired AI execution grant") from exc

        subject = str(claims.get("sub") or "")
        request_id = str(claims.get("request_id") or claims.get("jti") or "")
        if not subject or not request_id:
            raise ExecutionAuthorizationError("Execution grant requires sub and request_id")
        return ExecutionGrant(
            subject=subject,
            workspace_id=claims.get("workspace_id") or claims.get("workspaceId"),
            request_id=request_id,
            task_type=claims.get("task_type"),
            execution_profile=str(claims.get("execution_profile") or "balanced"),
            allowed_model_ids=tuple(str(item) for item in claims.get("allowed_model_ids", [])),
            max_input_tokens=_optional_int(claims.get("max_input_tokens")),
            max_output_tokens=_optional_int(claims.get("max_output_tokens")),
            max_provider_cost_usd=_optional_float(claims.get("max_provider_cost_usd")),
            grant_id=claims.get("jti"),
            reservation_id=claims.get("reservation_id") or claims.get("reservationId"),
            claims=dict(claims),
        )

    @staticmethod
    def validate_request(grant: ExecutionGrant, *, user_id: str, task_type: str) -> None:
        if grant.subject != user_id:
            raise ExecutionAuthorizationError("Execution grant subject does not match authenticated user")
        if grant.task_type and grant.task_type != task_type:
            raise ExecutionAuthorizationError("Execution grant does not authorize this task type")


class ExecutionGrantReplayGuard:
    """Consume one-time grant identifiers using Redis or process-local state."""

    def __init__(self) -> None:
        self._redis = _redis_client()
        self._seen: Dict[str, float] = {}
        self._lock = threading.Lock()

    def consume(self, grant: ExecutionGrant) -> None:
        if os.getenv("AI_EXECUTION_GRANT_REPLAY_PROTECTION", "true").lower() in {"0", "false", "no"}:
            return
        key = grant.grant_id or grant.request_id
        if not key:
            raise ExecutionAuthorizationError("Execution grant lacks a replay-protection identifier")
        now = time.time()
        expires_at = float(grant.claims.get("exp") or (now + 300))
        ttl = max(1, int(expires_at - now))
        redis_key = f"techit:ai:grant:{key}"
        if self._redis is not None:
            accepted = self._redis.set(redis_key, "1", nx=True, ex=ttl)
            if not accepted:
                raise ExecutionAuthorizationError("Execution grant has already been used")
            return
        with self._lock:
            self._seen = {item: expiry for item, expiry in self._seen.items() if expiry > now}
            if key in self._seen:
                raise ExecutionAuthorizationError("Execution grant has already been used")
            self._seen[key] = expires_at


def _optional_int(value: Any) -> Optional[int]:
    return None if value in (None, "") else int(value)


def _optional_float(value: Any) -> Optional[float]:
    return None if value in (None, "") else float(value)


class ExecutionRateLimiter:
    """Protective fixed-window user/workspace limiter with optional Redis state."""

    def __init__(self) -> None:
        self.user_limit = max(1, int(os.getenv("AI_USER_REQUESTS_PER_MINUTE", "60")))
        self.workspace_limit = max(1, int(os.getenv("AI_WORKSPACE_REQUESTS_PER_MINUTE", "300")))
        self._events: Dict[str, Deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()
        self._redis = _redis_client()

    async def check(self, user_id: str, workspace_id: Optional[str]) -> None:
        if os.getenv("AI_RATE_LIMIT_ENABLED", "true").lower() in {"0", "false", "no"}:
            return
        if self._redis is None:
            self._check_sync(f"user:{user_id}", self.user_limit)
        else:
            await asyncio.to_thread(self._check_sync, f"user:{user_id}", self.user_limit)
        if workspace_id:
            if self._redis is None:
                self._check_sync(f"workspace:{workspace_id}", self.workspace_limit)
            else:
                await asyncio.to_thread(
                    self._check_sync,
                    f"workspace:{workspace_id}",
                    self.workspace_limit,
                )

    def _check_sync(self, key: str, limit: int) -> None:
        if self._redis is not None:
            bucket = int(time.time() // 60)
            redis_key = f"techit:ai:rate:{key}:{bucket}"
            current = int(self._redis.incr(redis_key))
            if current == 1:
                self._redis.expire(redis_key, 65)
            if current > limit:
                raise ExecutionAuthorizationError(f"AI execution rate limit exceeded for {key}")
            return

        cutoff = time.monotonic() - 60
        with self._lock:
            events = self._events[key]
            while events and events[0] < cutoff:
                events.popleft()
            if len(events) >= limit:
                raise ExecutionAuthorizationError(f"AI execution rate limit exceeded for {key}")
            events.append(time.monotonic())


class ProviderCircuitBreaker:
    """Provider/model circuit breaker with Redis sharing when configured."""

    def __init__(self) -> None:
        self.failure_threshold = max(1, int(os.getenv("AI_CIRCUIT_FAILURE_THRESHOLD", "3")))
        self.cooldown_seconds = max(1, int(os.getenv("AI_CIRCUIT_COOLDOWN_SECONDS", "60")))
        self._state: Dict[str, Dict[str, float]] = defaultdict(dict)
        self._lock = threading.Lock()
        self._redis = _redis_client()

    def is_available(self, key: str) -> bool:
        now = time.time()
        if self._redis is not None:
            opened = self._redis.get(f"techit:ai:circuit:{key}:opened")
            return not opened or now >= float(opened)
        with self._lock:
            opened_until = float(self._state[key].get("opened_until", 0))
            return now >= opened_until

    def record_success(self, key: str) -> None:
        if self._redis is not None:
            self._redis.delete(f"techit:ai:circuit:{key}:failures")
            self._redis.delete(f"techit:ai:circuit:{key}:opened")
            return
        with self._lock:
            self._state.pop(key, None)

    def record_failure(self, key: str) -> None:
        if self._redis is not None:
            failure_key = f"techit:ai:circuit:{key}:failures"
            failures = int(self._redis.incr(failure_key))
            self._redis.expire(failure_key, self.cooldown_seconds * 2)
            if failures >= self.failure_threshold:
                opened_until = time.time() + self.cooldown_seconds
                self._redis.setex(
                    f"techit:ai:circuit:{key}:opened",
                    self.cooldown_seconds,
                    str(opened_until),
                )
            return
        with self._lock:
            failures = int(self._state[key].get("failures", 0)) + 1
            self._state[key]["failures"] = failures
            if failures >= self.failure_threshold:
                self._state[key]["opened_until"] = time.time() + self.cooldown_seconds


class ResponseCache:
    """Tenant-scoped cache. IP-protected requests remain uncached by caller policy."""

    def __init__(self) -> None:
        self._memory: Dict[str, tuple[float, Dict[str, Any]]] = {}
        self._lock = threading.Lock()
        self._redis = _redis_client()

    @staticmethod
    def key(*, user_id: str, workspace_id: Optional[str], task_type: str,
            payload: Mapping[str, Any]) -> str:
        canonical = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))
        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        tenant = f"workspace:{workspace_id}" if workspace_id else f"user:{user_id}"
        return f"techit:ai:cache:{tenant}:{task_type}:{digest}"

    async def get(self, key: str) -> Optional[Dict[str, Any]]:
        if self._redis is None:
            return self._get_sync(key)
        return await asyncio.to_thread(self._get_sync, key)

    def _get_sync(self, key: str) -> Optional[Dict[str, Any]]:
        if self._redis is not None:
            raw = self._redis.get(key)
            return json.loads(raw) if raw else None
        with self._lock:
            row = self._memory.get(key)
            if not row:
                return None
            expires_at, value = row
            if expires_at <= time.time():
                self._memory.pop(key, None)
                return None
            return dict(value)

    async def set(self, key: str, value: Mapping[str, Any], ttl_seconds: int) -> None:
        if ttl_seconds <= 0:
            return
        if self._redis is None:
            self._set_sync(key, dict(value), ttl_seconds)
        else:
            await asyncio.to_thread(self._set_sync, key, dict(value), ttl_seconds)

    def _set_sync(self, key: str, value: Dict[str, Any], ttl_seconds: int) -> None:
        if self._redis is not None:
            self._redis.setex(key, ttl_seconds, json.dumps(value, default=str))
            return
        with self._lock:
            self._memory[key] = (time.time() + ttl_seconds, value)


def _redis_client():
    if os.getenv("AI_SHARED_STATE_ENABLED", "false").lower() not in {"1", "true", "yes"}:
        return None
    redis_url = os.getenv("REDIS_URL")
    if not redis_url:
        return None
    try:
        import redis
        client = redis.Redis.from_url(redis_url, decode_responses=True, socket_timeout=1)
        client.ping()
        return client
    except Exception:
        return None
