"""Circuit breaker and infrastructure rate-limit contracts."""

import pytest

import execution_controls
from execution_controls import (
    ExecutionAuthorizationError,
    ExecutionRateLimiter,
    ProviderCircuitBreaker,
)


def test_private_api_responses_are_not_cacheable() -> None:
    """WS-10: this service returns user-specific JSON, so a browser or shared
    cache must never be able to replay a response to a later, less-privileged
    reader. The header is applied centrally; public routes override it."""
    import asyncio

    from starlette.requests import Request
    from starlette.responses import Response

    import main

    async def call_next(_request: Request) -> Response:
        return Response()

    request = Request({"type": "http", "method": "GET", "path": "/health", "headers": []})
    response = asyncio.run(main.security_headers(request, call_next))
    assert response.headers["cache-control"] == "private, no-store"
    assert response.headers["x-content-type-options"] == "nosniff"


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
