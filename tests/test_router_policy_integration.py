"""End-to-end policy plumbing: workflow budgets, cost metadata, placeholders."""

from __future__ import annotations

import pytest

from ai_router_core import AICommandLayer, AIRequest, ModelRouter, PromptEngine, SafetyEngine, TaskType, UserContext, UserRole
from execution_controls import ExecutionAuthorizationError


def _ctx(**kwargs) -> UserContext:
    values = dict(
        user_id="u_test", role=UserRole.FOUNDER, project_id="p_test",
        project_stage="mvp", industry="saas", tech_stack=[], past_feedback=[],
        training_progress={}, time_logged_today=0, tasks_completed_week=0,
    )
    values.update(kwargs)
    return UserContext(**values)


def _request(ctx=None, **kwargs) -> AIRequest:
    return AIRequest(task_type=TaskType.CHAT, user_context=ctx or _ctx(), input_data={"message": "hi"}, **kwargs)


def _layer() -> AICommandLayer:
    return AICommandLayer(ModelRouter(), PromptEngine(), SafetyEngine())


async def _ok(_config, _prompt, _request):
    return {"text": "ok", "tokens": 3, "prompt_tokens": 2, "completion_tokens": 1,
            "confidence": 1.0, "duration_ms": 1}


@pytest.mark.asyncio
async def test_response_metadata_records_billing_and_cost_status(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test")
    layer = _layer()
    monkeypatch.setattr(layer, "_call_llm", _ok)
    response = await layer.process_request(_request(requested_model="gpt-5.6-luna", use_cache=False))
    assert response.metadata["model_id"] == "gpt-5.6-luna"
    assert response.metadata["billing_class"] == "paid"
    assert response.metadata["cost_status"] == "estimated"
    assert response.metadata["pricing_version"]
    assert response.metadata["placeholder"] is False


@pytest.mark.asyncio
async def test_placeholder_response_is_explicitly_marked(monkeypatch) -> None:
    monkeypatch.setenv("ALLOW_AI_PLACEHOLDER_RESPONSES", "true")
    monkeypatch.setenv("AI_ROUTER_EXCLUDE_UNCONFIGURED", "false")
    for name in ("OPENAI_API_KEY", "OPENAI_API_KEY_2", "OPENAI_API_KEY_3", "OPENAI_API_KEY_4"):
        monkeypatch.delenv(name, raising=False)
    layer = _layer()
    response = await layer.process_request(_request(requested_model="gpt-5.6-luna", use_cache=False))
    assert response.metadata["placeholder"] is True
    assert response.metadata["cost_status"] in {"estimated", "free", "pending_reconciliation"}


@pytest.mark.asyncio
async def test_workflow_budget_aborts_the_second_sub_request(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test")
    monkeypatch.setenv("AI_WORKFLOW_BUDGET_ENABLED", "true")
    monkeypatch.setenv("AI_WORKFLOW_MAX_CALLS", "1")
    layer = _layer()
    monkeypatch.setattr(layer, "_call_llm", _ok)
    first = await layer.process_request(
        _request(requested_model="gpt-5.6-luna", use_cache=False, workflow_id="wf-x")
    )
    assert first.output == "ok"
    with pytest.raises(ExecutionAuthorizationError, match="workflow call budget exceeded"):
        await layer.process_request(
            _request(requested_model="gpt-5.6-luna", use_cache=False, workflow_id="wf-x")
        )


@pytest.mark.asyncio
async def test_workflow_budget_does_not_block_other_workflows(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test")
    monkeypatch.setenv("AI_WORKFLOW_BUDGET_ENABLED", "true")
    monkeypatch.setenv("AI_WORKFLOW_MAX_CALLS", "1")
    layer = _layer()
    monkeypatch.setattr(layer, "_call_llm", _ok)
    await layer.process_request(_request(requested_model="gpt-5.6-luna", use_cache=False, workflow_id="wf-a"))
    second = await layer.process_request(_request(requested_model="gpt-5.6-luna", use_cache=False, workflow_id="wf-b"))
    assert second.output == "ok"


@pytest.mark.asyncio
async def test_trusted_worker_fan_out_is_scoped_per_user(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test")
    monkeypatch.setenv("AI_TRUSTED_WORKER_EXECUTION", "true")
    monkeypatch.setenv("AI_WORKFLOW_BUDGET_ENABLED", "true")
    monkeypatch.setenv("AI_TRUSTED_WORKER_MAX_CALLS", "1")
    layer = _layer()
    monkeypatch.setattr(layer, "_call_llm", _ok)
    await layer.process_request(_request(requested_model="gpt-5.6-luna", use_cache=False))
    with pytest.raises(ExecutionAuthorizationError):
        await layer.process_request(_request(requested_model="gpt-5.6-luna", use_cache=False))


@pytest.mark.asyncio
async def test_settlement_includes_workflow_cost_status_and_idempotency(monkeypatch) -> None:
    monkeypatch.setenv("BACKEND_USAGE_SETTLEMENT_URL", "https://b.example")
    monkeypatch.setenv("AI_ROUTER_SETTLEMENT_SECRET", "s" * 40)
    monkeypatch.setenv("AI_SETTLEMENT_OUTBOX_ENABLED", "false")
    monkeypatch.delenv("DATABASE_URL", raising=False)
    from usage_settlement_client import UsageSettlementClient

    client = UsageSettlementClient()
    captured = {}
    headers = {}

    async def fake_post(path, body):
        captured["path"] = path
        captured["body"] = body
        headers.update(client._headers(body))
        return {"ok": True}

    monkeypatch.setattr(client, "_post", fake_post)
    await client.settle(
        request_id="r1", user_id="u", workspace_id="w", task_type="chat", provider="openai",
        model="m", status="completed", prompt_tokens=1, completion_tokens=1, total_tokens=2,
        provider_cost_usd=0.01, latency_ms=5, attempt_count=1, cache_hit=False,
        grant_id="g", reservation_id="res", metadata={}, workflow_id="wf",
        cost_status="estimated", pricing_version="v1",
    )
    assert captured["body"]["workflow_id"] == "wf"
    assert captured["body"]["cost_status"] == "estimated"
    assert captured["body"]["pricing_version"] == "v1"
    assert headers["Idempotency-Key"] == "r1"
