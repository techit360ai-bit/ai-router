"""Circuit breaker and infrastructure rate-limit contracts."""

import pytest

import execution_controls
from execution_controls import (
    ExecutionAuthorizationError,
    ExecutionRateLimiter,
    ProviderSpendBudget,
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


def test_dynamic_provider_spend_budget_scales_from_base(monkeypatch) -> None:
    monkeypatch.setenv("AI_PROVIDER_SPEND_BASE_USD_PER_MINUTE", "100")
    monkeypatch.setenv("AI_PROVIDER_SPEND_BASE_DEMAND_UNITS", "10")
    monkeypatch.setenv("AI_PROVIDER_SPEND_MAX_USD_PER_MINUTE", "0")
    budget = ProviderSpendBudget()
    assert budget.budget_for(10) == 100
    assert budget.budget_for(100) == 1000
    assert budget.budget_for(1_000_000) == 10_000_000


def test_dynamic_provider_spend_budget_releases_failed_reservation(monkeypatch) -> None:
    monkeypatch.setenv("AI_PROVIDER_SPEND_BASE_USD_PER_MINUTE", "100")
    monkeypatch.setenv("AI_PROVIDER_SPEND_BASE_DEMAND_UNITS", "10")
    budget = ProviderSpendBudget()
    reservation = budget.reserve(provider="openai", estimated_cost_usd=80, user_id="u1", demand_units=10)
    budget.settle(reservation, 0)
    second = budget.reserve(provider="openai", estimated_cost_usd=100, user_id="u2", demand_units=10)
    budget.settle(second, 100)


def test_dynamic_provider_spend_budget_rejects_over_budget(monkeypatch) -> None:
    monkeypatch.setenv("AI_PROVIDER_SPEND_BASE_USD_PER_MINUTE", "100")
    monkeypatch.setenv("AI_PROVIDER_SPEND_BASE_DEMAND_UNITS", "10")
    budget = ProviderSpendBudget()
    reservation = budget.reserve(provider="openai", estimated_cost_usd=60, user_id="u1", demand_units=10)
    with pytest.raises(ExecutionAuthorizationError):
        budget.reserve(provider="openai", estimated_cost_usd=41, user_id="u2", demand_units=10)
    budget.settle(reservation, 60)
