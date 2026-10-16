"""Billing-class policy: free vs paid is decided per model, enforced by the grant."""

from __future__ import annotations

import pytest
from jose import jwt

from ai_router_core import AIRequest, ModelRouter, TaskType, UserContext, UserRole
from execution_controls import ExecutionAuthorizationError, ExecutionGrant, ExecutionGrantVerifier


def _ctx(grant=None) -> UserContext:
    return UserContext(
        user_id="u", role=UserRole.FOUNDER, project_id="p", project_stage="mvp",
        industry="saas", tech_stack=[], past_feedback=[], training_progress={},
        time_logged_today=0, tasks_completed_week=0, execution_grant=grant,
    )


def _req(task: TaskType, grant=None, **kwargs) -> AIRequest:
    return AIRequest(task_type=task, user_context=_ctx(grant), input_data={}, **kwargs)


def _grant(task_type: str, **overrides) -> ExecutionGrant:
    payload = dict(subject="u", workspace_id=None, request_id="r-1", task_type=task_type)
    payload.update(overrides)
    return ExecutionGrant(**payload)


def test_openrouter_free_and_paid_are_classified_per_model() -> None:
    models = ModelRouter().registry.models
    assert models["openrouter-free"].billing_class == "free"
    assert models["openrouter-llama-free"].billing_class == "free"
    assert models["openrouter-claude-sonnet"].billing_class == "paid"


def test_free_tier_grant_restricts_chain_to_free_models(monkeypatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "test")
    chain = ModelRouter().select_chain(
        _req(TaskType.TRAINING_GENERATION, _grant("training_generation", allowed_billing_classes=("free",)))
    )
    assert [item.id for item in chain] == ["openrouter-llama-free"]
    assert all(item.billing_class == "free" for item in chain)


def test_free_tier_grant_cannot_escalate_to_a_paid_model(monkeypatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "test")
    # Only a paid model satisfies this task policy, so a free-only grant must
    # deny rather than silently fall through to the paid model.
    with pytest.raises(ExecutionAuthorizationError):
        ModelRouter().select_chain(
            _req(TaskType.MARKET_INTELLIGENCE, _grant("market_intelligence", allowed_billing_classes=("free",)))
        )


def test_paid_grant_authorizes_the_paid_model(monkeypatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "test")
    chain = ModelRouter().select_chain(
        _req(TaskType.MARKET_INTELLIGENCE, _grant("market_intelligence", allowed_billing_classes=("paid",)))
    )
    assert chain
    assert all(item.billing_class == "paid" for item in chain)


def test_grant_data_handling_excludes_non_compliant_models(monkeypatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "test")
    with pytest.raises(ExecutionAuthorizationError):
        ModelRouter().select_chain(
            _req(TaskType.TRAINING_GENERATION, _grant("training_generation", required_data_handling="no_training"))
        )


def test_verifier_parses_billing_and_workflow_claims(monkeypatch) -> None:
    for key in ("ENVIRONMENT", "AI_EXECUTION_GRANT_ALGORITHM", "AI_EXECUTION_GRANT_SECRET",
                "AI_EXECUTION_GRANT_PUBLIC_KEY", "JWT_PUBLIC_KEY", "JWT_SECRET"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("AI_EXECUTION_GRANT_SECRET", "dev-grant-secret")
    verifier = ExecutionGrantVerifier()
    token = jwt.encode(
        {
            "sub": "user-1", "request_id": "req-1", "task_type": "training_generation",
            "iss": "techit-backend", "aud": "techit-ai-router",
            "allowed_billing_classes": ["free"], "workflow_id": "wf-1",
            "max_workflow_cost_usd": 2.5, "required_data_handling": "no_training",
        },
        "dev-grant-secret", algorithm="HS256",
    )
    grant = verifier.verify(token)
    assert grant.allowed_billing_classes == ("free",)
    assert grant.workflow_id == "wf-1"
    assert grant.max_workflow_cost_usd == 2.5
    assert grant.required_data_handling == "no_training"
    assert grant.permits_billing_class("free") is True
    assert grant.permits_billing_class("paid") is False


def test_verifier_accepts_a_single_billing_class_claim(monkeypatch) -> None:
    for key in ("ENVIRONMENT", "AI_EXECUTION_GRANT_ALGORITHM", "AI_EXECUTION_GRANT_SECRET",
                "AI_EXECUTION_GRANT_PUBLIC_KEY", "JWT_PUBLIC_KEY", "JWT_SECRET"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("AI_EXECUTION_GRANT_SECRET", "dev-grant-secret")
    token = jwt.encode(
        {"sub": "u", "request_id": "r", "billing_class": "free", "iss": "techit-backend", "aud": "techit-ai-router"},
        "dev-grant-secret", algorithm="HS256",
    )
    assert ExecutionGrantVerifier().verify(token).allowed_billing_classes == ("free",)
