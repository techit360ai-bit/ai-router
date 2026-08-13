"""Circuit breaker and infrastructure rate-limit contracts."""

import pytest

import execution_controls
from execution_controls import (
    ExecutionAuthorizationError,
    ExecutionRateLimiter,
    ProviderCircuitBreaker,
)


def test_circuit_breaker_opens_and_recovers(monkeypatch) -> None:
    monkeypatch.setenv("AI_CIRCUIT_FAILURE_THRESHOLD", "2")
    monkeypatch.setenv("AI_CIRCUIT_COOLDOWN_SECONDS", "10")
    now = [1_000.0]
    monkeypatch.setattr(execution_controls.time, "time", lambda: now[0])
    breaker = ProviderCircuitBreaker()
    breaker.record_failure("provider:model")
    assert breaker.is_available("provider:model")
    breaker.record_failure("provider:model")
    assert not breaker.is_available("provider:model")
    now[0] += 11
    assert breaker.is_available("provider:model")
    breaker.record_success("provider:model")
    assert breaker.is_available("provider:model")


@pytest.mark.asyncio
async def test_user_and_workspace_rate_limits(monkeypatch) -> None:
    monkeypatch.setenv("AI_USER_REQUESTS_PER_MINUTE", "1")
    monkeypatch.setenv("AI_WORKSPACE_REQUESTS_PER_MINUTE", "1")
    limiter = ExecutionRateLimiter()
    await limiter.check("user-a", "workspace-a")
    with pytest.raises(ExecutionAuthorizationError):
        await limiter.check("user-a", "workspace-a")
