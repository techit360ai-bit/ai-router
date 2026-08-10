"""Execution-only retry, fallback, validation, telemetry, cache, and grants."""

from __future__ import annotations

import os
from types import SimpleNamespace

import pytest

from ai_router_core import AICommandLayer, AIRequest, ModelRouter, PromptEngine, SafetyEngine, TaskType, UserContext, UserRole
from execution_controls import ExecutionAuthorizationError, ExecutionGrant, ResponseCache
from provider_adapters import ProviderRateLimitError


def _ctx(**kwargs) -> UserContext:
    values = dict(
        user_id="u_test", role=UserRole.FOUNDER, project_id="p_test",
        project_stage="mvp", industry="saas", tech_stack=[], past_feedback=[],
        training_progress={}, time_logged_today=0, tasks_completed_week=0,
    )
    values.update(kwargs)
    return UserContext(**values)


def _request(task=TaskType.CHAT, ctx=None, **kwargs) -> AIRequest:
    return AIRequest(task_type=task, user_context=ctx or _ctx(), input_data={"message": "hello"}, **kwargs)


@pytest.mark.asyncio
async def test_429_gets_one_retry_and_every_attempt_is_recorded(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test")
    layer = AICommandLayer(ModelRouter(), PromptEngine(), SafetyEngine())
    calls = 0

    async def fake_call(_config, _prompt, _request):
        nonlocal calls
        calls += 1
        if calls == 1:
            raise ProviderRateLimitError("429")
        return {"text": "ok", "tokens": 3, "prompt_tokens": 2, "completion_tokens": 1,
                "confidence": 1.0, "duration_ms": 1}

    monkeypatch.setattr(layer, "_call_llm", fake_call)
    response = await layer.process_request(_request(requested_model="gpt-5.6-luna", use_cache=False))
    attempts = [event for event in layer.execution_log if event["event"] == "provider_attempt"]
    assert calls == 2
    assert [event["status"] for event in attempts] == ["failed", "success"]
    assert response.tokens_used == 3


@pytest.mark.asyncio
async def test_invalid_structured_output_falls_back(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    layer = AICommandLayer(ModelRouter(), PromptEngine(), SafetyEngine())
    calls = 0

    async def fake_call(_config, _prompt, _request):
        nonlocal calls
        calls += 1
        text = "not-json" if calls == 1 else '{"ok": true}'
        return {"text": text, "tokens": 2, "prompt_tokens": 1, "completion_tokens": 1,
                "confidence": 1.0, "duration_ms": 1}

    monkeypatch.setattr(layer, "_call_llm", fake_call)
    response = await layer.process_request(_request(
        task=TaskType.CHAT, require_structured_output=True,
        output_schema={"type": "object", "required": ["ok"]}, use_cache=False,
    ))
    assert response.output == '{"ok": true}'
    assert calls >= 2


def test_cache_keys_are_tenant_isolated() -> None:
    payload = {"prompt": "same"}
    assert ResponseCache.key(user_id="a", workspace_id=None, task_type="chat", payload=payload) != ResponseCache.key(
        user_id="b", workspace_id=None, task_type="chat", payload=payload
    )
    assert ResponseCache.key(user_id="a", workspace_id="w1", task_type="chat", payload=payload) != ResponseCache.key(
        user_id="a", workspace_id="w2", task_type="chat", payload=payload
    )


@pytest.mark.asyncio
async def test_execution_grant_task_mismatch_and_replay(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test")
    grant = ExecutionGrant(
        subject="u_test", workspace_id="w", request_id="r1", task_type="chat",
        grant_id="g1", claims={"exp": 9999999999},
    )
    layer = AICommandLayer(ModelRouter(), PromptEngine(), SafetyEngine())
    with pytest.raises(ExecutionAuthorizationError):
        await layer.process_request(_request(TaskType.SUMMARY, _ctx(execution_grant=grant)))

    async def fake_call(_config, _prompt, _request):
        return {"text": "ok", "tokens": 1, "prompt_tokens": 1, "completion_tokens": 0,
                "confidence": 1.0, "duration_ms": 1}

    monkeypatch.setattr(layer, "_call_llm", fake_call)
    await layer.process_request(_request(TaskType.CHAT, _ctx(execution_grant=grant), use_cache=False))
    with pytest.raises(ExecutionAuthorizationError):
        await layer.process_request(_request(TaskType.CHAT, _ctx(execution_grant=grant), use_cache=False))
