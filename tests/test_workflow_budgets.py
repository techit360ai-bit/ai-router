"""Cumulative workflow budgets bound multi-agent / trusted-worker fan-out."""

from __future__ import annotations

import pytest

from execution_controls import ExecutionAuthorizationError, WorkflowBudget


def _budget(monkeypatch, **env) -> WorkflowBudget:
    monkeypatch.setenv("AI_WORKFLOW_BUDGET_ENABLED", "true")
    for key, value in env.items():
        monkeypatch.setenv(key, str(value))
    return WorkflowBudget()


def test_workflow_budget_rejects_when_cost_ceiling_is_crossed(monkeypatch) -> None:
    budget = _budget(monkeypatch, AI_WORKFLOW_MAX_COST_USD=1.0)
    reservation = budget.reserve(workflow_id="wf", estimated_cost_usd=0.6)
    with pytest.raises(ExecutionAuthorizationError, match="workflow spend budget exceeded"):
        budget.reserve(workflow_id="wf", estimated_cost_usd=0.5)
    budget.settle(reservation, 0.0)
    # Releasing the failed reservation frees the budget again.
    budget.reserve(workflow_id="wf", estimated_cost_usd=0.5)


def test_workflow_budget_rejects_when_call_ceiling_is_crossed(monkeypatch) -> None:
    budget = _budget(monkeypatch, AI_WORKFLOW_MAX_COST_USD=0, AI_WORKFLOW_MAX_CALLS=2)
    budget.reserve(workflow_id="wf", estimated_cost_usd=0)
    budget.reserve(workflow_id="wf", estimated_cost_usd=0)
    with pytest.raises(ExecutionAuthorizationError, match="workflow call budget exceeded"):
        budget.reserve(workflow_id="wf", estimated_cost_usd=0)


def test_workflow_budget_without_a_workflow_id_is_a_no_op(monkeypatch) -> None:
    budget = _budget(monkeypatch, AI_WORKFLOW_MAX_COST_USD=0.01)
    assert budget.reserve(workflow_id=None, estimated_cost_usd=100) is None


def test_workflow_budget_is_isolated_per_workflow(monkeypatch) -> None:
    budget = _budget(monkeypatch, AI_WORKFLOW_MAX_COST_USD=1.0)
    budget.reserve(workflow_id="a", estimated_cost_usd=0.9)
    budget.reserve(workflow_id="b", estimated_cost_usd=0.9)


def test_grant_ceiling_overrides_the_default(monkeypatch) -> None:
    budget = _budget(monkeypatch, AI_WORKFLOW_MAX_COST_USD=100.0)
    with pytest.raises(ExecutionAuthorizationError):
        budget.reserve(workflow_id="wf", estimated_cost_usd=5.0, max_cost_usd=1.0)


def test_settle_reconciles_estimate_to_actual(monkeypatch) -> None:
    budget = _budget(monkeypatch, AI_WORKFLOW_MAX_COST_USD=1.0)
    reservation = budget.reserve(workflow_id="wf", estimated_cost_usd=0.9)
    budget.settle(reservation, 0.1)
    snapshot = budget.snapshot("wf")
    assert snapshot["cost"] == pytest.approx(0.1)
    assert snapshot["calls"] == 1


def test_budget_can_be_disabled(monkeypatch) -> None:
    monkeypatch.setenv("AI_WORKFLOW_BUDGET_ENABLED", "false")
    budget = WorkflowBudget()
    assert budget.reserve(workflow_id="wf", estimated_cost_usd=1000) is None
