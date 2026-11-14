"""Request-scoped execution grants.

Regressions covered:
* One backend grant now authorizes every LLM execution of the HTTP request it
  was issued for (multi-agent pipelines used to fail from the second agent on),
  while a replayed token (a new grant object) is still rejected.
* Each extra execution settles under "<request_id>:<n>" so the backend records
  it against the same reservation instead of rejecting a payload conflict.
"""

from __future__ import annotations

import pytest

from ai_router_core import AICommandLayer, AIRequest, ModelRouter, PromptEngine, SafetyEngine, TaskType, UserContext, UserRole
from execution_controls import ExecutionAuthorizationError, ExecutionGrant


def _ctx(**kwargs) -> UserContext:
    values = dict(
        user_id="u_test", role=UserRole.FOUNDER, project_id="p_test",
        project_stage="mvp", industry="saas", tech_stack=[], past_feedback=[],
        training_progress={}, time_logged_today=0, tasks_completed_week=0,
    )
    values.update(kwargs)
    return UserContext(**values)


def _request(task=TaskType.CHAT, ctx=None, **kwargs) -> AIRequest:
    return AIRequest(task_type=task, user_context=ctx or _ctx(), input_data={"message": "hello"}, use_cache=False, **kwargs)


def _grant(**overrides) -> ExecutionGrant:
    values = dict(subject="u_test", workspace_id="w1", request_id="gw_req", task_type=None, grant_id="gw_req", reservation_id="gw_req", claims={"exp": 9999999999})
    values.update(overrides)
    return ExecutionGrant(**values)


async def _ok(_config, _prompt, _request):
    return {"text": "ok", "tokens": 3, "prompt_tokens": 2, "completion_tokens": 1, "confidence": 1.0, "duration_ms": 1}


@pytest.fixture
def layer(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test")
    command_layer = AICommandLayer(ModelRouter(), PromptEngine(), SafetyEngine())
    monkeypatch.setattr(command_layer, "_call_llm", _ok)
    settled = []

    async def capture(**facts):
        settled.append(facts)
        return {"ok": True}

    monkeypatch.setattr(command_layer.settlement, "settle", capture)
    command_layer.settled = settled
    return command_layer


@pytest.mark.asyncio
async def test_one_grant_covers_every_execution_of_its_request(layer) -> None:
    grant = _grant()
    ctx = _ctx(execution_grant=grant, workspace_id="w1")
    for task in (TaskType.CHAT, TaskType.SUMMARY, TaskType.CHAT):
        await layer.process_request(_request(task, ctx))
    assert [facts["request_id"] for facts in layer.settled] == ["gw_req", "gw_req:2", "gw_req:3"]
    assert {facts["reservation_id"] for facts in layer.settled} == {"gw_req"}


@pytest.mark.asyncio
async def test_a_replayed_grant_token_is_still_rejected(layer) -> None:
    await layer.process_request(_request(TaskType.CHAT, _ctx(execution_grant=_grant(), workspace_id="w1")))
    replay = _grant()  # same token verified again in another HTTP request
    with pytest.raises(ExecutionAuthorizationError):
        await layer.process_request(_request(TaskType.CHAT, _ctx(execution_grant=replay, workspace_id="w1")))
    # A failed replay check never unlocks the remaining executions.
    with pytest.raises(ExecutionAuthorizationError):
        await layer.process_request(_request(TaskType.CHAT, _ctx(execution_grant=replay, workspace_id="w1")))


@pytest.mark.asyncio
async def test_executions_per_grant_are_capped(layer, monkeypatch) -> None:
    monkeypatch.setenv("AI_MAX_EXECUTIONS_PER_GRANT", "2")
    ctx = _ctx(execution_grant=_grant(request_id="capped", grant_id="capped", reservation_id="capped"), workspace_id="w1")
    await layer.process_request(_request(TaskType.CHAT, ctx))
    await layer.process_request(_request(TaskType.CHAT, ctx))
    with pytest.raises(ExecutionAuthorizationError):
        await layer.process_request(_request(TaskType.CHAT, ctx))
