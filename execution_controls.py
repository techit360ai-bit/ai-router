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
from pathlib import Path
from typing import Any, Deque, Dict, Iterable, Mapping, Optional


def _configured_spend_defaults() -> tuple[float, int]:
    """Read spend defaults from the versioned SLO profile, not source code."""
    profile_path = os.getenv("SCALABILITY_SLO_PATH") or str(Path(__file__).resolve().parent / "config" / "scalability_slos.json")
    try:
        profile = json.loads(Path(profile_path).read_text(encoding="utf-8"))
        defaults = profile.get("capacity_defaults") or {}
        return float(defaults.get("provider_spend_base_usd_per_minute", 0)), max(
            1, int(defaults.get("provider_spend_base_demand_units", 1))
        )
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return 0.0, 1


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


@dataclass(frozen=True)
class SpendReservation:
    """A short-lived provider spend reservation for one execution attempt."""

    key: str
    provider: str
    minute: int
    reserved_usd: float


class ProviderSpendBudget:
    """Dynamic per-minute provider spend guard.

    The budget starts at ``AI_PROVIDER_SPEND_BASE_USD_PER_MINUTE`` for
    ``AI_PROVIDER_SPEND_BASE_DEMAND_UNITS`` users/calls and scales linearly
    with observed demand. Redis is used when shared state is enabled; the
    process-local path remains useful for development and single instances.
    """

    def __init__(self) -> None:
        configured_budget, configured_units = _configured_spend_defaults()
        self.base_budget_usd = max(0.0, float(os.getenv("AI_PROVIDER_SPEND_BASE_USD_PER_MINUTE", str(configured_budget))))
        self.base_demand_units = max(1, int(os.getenv("AI_PROVIDER_SPEND_BASE_DEMAND_UNITS", str(configured_units))))
        self.growth_multiplier = max(0.0, float(os.getenv("AI_PROVIDER_SPEND_GROWTH_MULTIPLIER", "1")))
        configured_cap = float(os.getenv("AI_PROVIDER_SPEND_MAX_USD_PER_MINUTE", "0"))
        self.max_budget_usd = configured_cap if configured_cap > 0 else None
        self.enabled = os.getenv("AI_PROVIDER_SPEND_GUARD_ENABLED", "true").lower() not in {"0", "false", "no"}
        self._redis = _redis_client()
        self._local_spend: Dict[str, float] = defaultdict(float)
        self._local_calls: Dict[int, int] = defaultdict(int)
        self._local_users: Dict[int, set[str]] = defaultdict(set)
        self._lock = threading.Lock()

    def budget_for(self, demand_units: int) -> float:
        demand = max(self.base_demand_units, int(demand_units or 0))
        budget = self.base_budget_usd * (demand / self.base_demand_units) * self.growth_multiplier
        if self.max_budget_usd is not None:
            budget = min(budget, self.max_budget_usd)
        return round(max(0.0, budget), 8)

    def _demand(self, minute: int, user_id: str, explicit_units: Optional[int]) -> int:
        if self._redis is not None:
            calls_key = f"techit:ai:demand:calls:{minute}"
            users_key = f"techit:ai:demand:users:{minute}"
            self._redis.incr(calls_key)
            self._redis.expire(calls_key, 120)
            self._redis.sadd(users_key, user_id or "anonymous")
            self._redis.expire(users_key, 120)
            calls = int(self._redis.get(f"techit:ai:demand:calls:{minute}") or 0)
            users = int(self._redis.scard(f"techit:ai:demand:users:{minute}") or 0)
            return max(self.base_demand_units, calls, users, int(explicit_units or 0))
        with self._lock:
            self._local_calls[minute] += 1
            self._local_users[minute].add(user_id or "anonymous")
            return max(self.base_demand_units, self._local_calls[minute], len(self._local_users[minute]), int(explicit_units or 0))

    def reserve(
        self,
        *,
        provider: str,
        estimated_cost_usd: float,
        user_id: str,
        demand_units: Optional[int] = None,
    ) -> SpendReservation:
        minute = int(time.time() // 60)
        key = f"techit:ai:spend:{provider}:{minute}"
        estimated = max(0.0, float(estimated_cost_usd or 0.0))
        demand = self._demand(minute, user_id, demand_units)
        budget = self.budget_for(demand)
        if self.enabled and estimated > 0:
            if self._redis is not None:
                current = float(self._redis.incrbyfloat(key, estimated))
                self._redis.expire(key, 120)
                if current > budget:
                    self._redis.incrbyfloat(key, -estimated)
                    try:
                        from hardening_metrics import METRICS
                        METRICS.increment("provider_spend_reservation_rejected", provider)
                    except Exception:
                        pass
                    raise ExecutionAuthorizationError(
                        f"provider spend budget exceeded for {provider}: {current:.6f} > {budget:.6f} USD/min"
                    )
            else:
                with self._lock:
                    current = self._local_spend[key] + estimated
                    if current > budget:
                        try:
                            from hardening_metrics import METRICS
                            METRICS.increment("provider_spend_reservation_rejected", provider)
                        except Exception:
                            pass
                        raise ExecutionAuthorizationError(
                            f"provider spend budget exceeded for {provider}: {current:.6f} > {budget:.6f} USD/min"
                        )
                    self._local_spend[key] = current
        return SpendReservation(key=key, provider=provider, minute=minute, reserved_usd=estimated)

    def settle(self, reservation: Optional[SpendReservation], actual_cost_usd: float = 0.0) -> None:
        if reservation is None or not self.enabled or reservation.reserved_usd <= 0:
            return
        delta = float(actual_cost_usd or 0.0) - reservation.reserved_usd
        if self._redis is not None:
            self._redis.incrbyfloat(reservation.key, delta)
            return
        with self._lock:
            self._local_spend[reservation.key] = max(0.0, self._local_spend[reservation.key] + delta)


class ProviderCredentialPool:
    """Least-loaded provider key selection with cooldown and quarantine state."""

    def __init__(self) -> None:
        self.cooldown_seconds = max(1, int(os.getenv("AI_PROVIDER_KEY_COOLDOWN_SECONDS", "60")))
        self.max_in_flight = max(0, int(os.getenv("AI_PROVIDER_KEY_MAX_IN_FLIGHT", "0")))
        self._state: Dict[str, Dict[str, float]] = defaultdict(dict)
        self._lock = threading.Lock()
        self._redis = _redis_client()

    @staticmethod
    def _redis_key(provider: str, key_env: str) -> str:
        return f"techit:ai:credential:{provider}:{key_env}"

    def acquire(self, provider: str, key_envs: Iterable[str]) -> Optional[str]:
        candidates = [str(item) for item in key_envs if item and os.environ.get(str(item))]
        if not candidates:
            return None
        now = time.time()
        if self._redis is not None:
            lock = self._redis.lock(f"techit:ai:credential-lock:{provider}", timeout=2, blocking_timeout=1)
            acquired = lock.acquire()
            if not acquired:
                raise ExecutionAuthorizationError(f"provider credential coordination unavailable for {provider}")
            try:
                healthy = []
                for item in candidates:
                    state = self._redis.hgetall(self._redis_key(provider, item))
                    cooldown = float(state.get("cooldown_until", 0) or 0)
                    in_flight = int(state.get("in_flight", 0) or 0)
                    if cooldown <= now and not state.get("quarantined") and (self.max_in_flight <= 0 or in_flight < self.max_in_flight):
                        healthy.append((item, in_flight))
                if not healthy:
                    raise ExecutionAuthorizationError(f"all configured credentials are unavailable for {provider}")
                selected = min(healthy, key=lambda item: item[1])[0]
                redis_key = self._redis_key(provider, selected)
                self._redis.hincrby(redis_key, "in_flight", 1)
                self._redis.expire(redis_key, self.cooldown_seconds * 2)
                return selected
            finally:
                lock.release()
        with self._lock:
            healthy = [item for item in candidates if float(self._state[f"{provider}:{item}"].get("cooldown_until", 0)) <= now and not self._state[f"{provider}:{item}"].get("quarantined") and (self.max_in_flight <= 0 or self._state[f"{provider}:{item}"].get("in_flight", 0) < self.max_in_flight)]
            if not healthy:
                raise ExecutionAuthorizationError(f"all configured credentials are unavailable for {provider}")
            selected = min(healthy, key=lambda item: self._state[f"{provider}:{item}"].get("in_flight", 0))
            state = self._state[f"{provider}:{selected}"]
            state["in_flight"] = state.get("in_flight", 0) + 1
            try:
                from hardening_metrics import METRICS
                METRICS.increment("provider_credential_acquires", provider)
            except Exception:
                pass
            return selected

    def release(self, provider: str, key_env: Optional[str], error: Optional[Exception] = None) -> None:
        if not key_env:
            return
        if self._redis is not None:
            redis_key = self._redis_key(provider, key_env)
            current = max(0, int(self._redis.hincrby(redis_key, "in_flight", -1)))
            self._redis.hset(redis_key, "in_flight", current)
            if error.__class__.__name__ == "ProviderRateLimitError":
                self._redis.hset(redis_key, "cooldown_until", time.time() + self.cooldown_seconds)
            elif error.__class__.__name__ == "ProviderAuthError":
                self._redis.hset(redis_key, "quarantined", 1)
            self._redis.expire(redis_key, self.cooldown_seconds * 2)
            return
        with self._lock:
            state = self._state[f"{provider}:{key_env}"]
            state["in_flight"] = max(0, state.get("in_flight", 0) - 1)
            if error.__class__.__name__ == "ProviderRateLimitError":
                state["cooldown_until"] = time.time() + self.cooldown_seconds
                try:
                    from hardening_metrics import METRICS
                    METRICS.increment("provider_credential_cooldowns", provider)
                except Exception:
                    pass
            elif error.__class__.__name__ == "ProviderAuthError":
                state["quarantined"] = 1
                try:
                    from hardening_metrics import METRICS
                    METRICS.increment("provider_credential_quarantines", provider)
                except Exception:
                    pass

    def status(self) -> Dict[str, Dict[str, float]]:
        if self._redis is not None:
            return {key: {str(name): float(value) for name, value in self._redis.hgetall(key).items()} for key in self._redis.scan_iter("techit:ai:credential:*") if not key.endswith("-lock")}
        with self._lock:
            return {key: dict(value) for key, value in self._state.items()}


class AdmissionLease:
    def __init__(self, controller: "AIAdmissionController") -> None:
        self._controller = controller
        self._released = False

    def release(self) -> None:
        if not self._released:
            self._released = True
            self._controller.release()


class AIAdmissionController:
    """Bound total in-flight AI work before provider calls are attempted."""

    def __init__(self) -> None:
        self.max_in_flight = max(0, int(os.getenv("AI_MAX_IN_FLIGHT", "0")))
        self.max_queue = max(0, int(os.getenv("AI_MAX_QUEUE", "0")))
        self._in_flight = 0
        self._queued = 0
        self._condition = asyncio.Condition()

    async def acquire(self) -> AdmissionLease:
        if self.max_in_flight <= 0:
            return AdmissionLease(self)
        async with self._condition:
            if self._in_flight >= self.max_in_flight and self._queued >= self.max_queue:
                raise ExecutionAuthorizationError("AI admission capacity exhausted")
            if self._in_flight >= self.max_in_flight:
                self._queued += 1
                try:
                    await self._condition.wait_for(lambda: self._in_flight < self.max_in_flight)
                finally:
                    self._queued = max(0, self._queued - 1)
            self._in_flight += 1
            return AdmissionLease(self)

    def release(self) -> None:
        if self.max_in_flight <= 0:
            return
        async def notify() -> None:
            async with self._condition:
                self._in_flight = max(0, self._in_flight - 1)
                self._condition.notify(1)
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(notify())
        except RuntimeError:
            self._in_flight = max(0, self._in_flight - 1)

    def snapshot(self) -> Dict[str, int]:
        return {"max_in_flight": self.max_in_flight, "max_queue": self.max_queue, "in_flight": self._in_flight, "queued": self._queued}


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
