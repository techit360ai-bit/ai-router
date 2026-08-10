"""Configuration-driven routing contracts."""

from __future__ import annotations

import os

import pytest

from ai_router_core import AIRequest, ModelRouter, TaskType, UserContext, UserRole
from model_registry import RegistryError


def _ctx() -> UserContext:
    return UserContext(
        user_id="u_test", role=UserRole.FOUNDER, project_id="p_test",
        project_stage="mvp", industry="saas", tech_stack=[], past_feedback=[],
        training_progress={}, time_logged_today=0, tasks_completed_week=0,
    )


def _req(task: TaskType, **kwargs) -> AIRequest:
    return AIRequest(task_type=task, user_context=_ctx(), input_data={}, **kwargs)


def test_registry_covers_every_task() -> None:
    router = ModelRouter()
    assert set(router.registry.task_policies) == {task.value for task in TaskType}
    for task in TaskType:
        assert router.select_chain(_req(task))


def test_modern_models_are_registered() -> None:
    models = ModelRouter().registry.models
    for model_id in (
        "gpt-5.6-sol", "gpt-5.6-terra", "gpt-5.6-luna", "gpt-5.5",
        "gpt-5.4", "gpt-5.3-codex", "claude-fable-5", "claude-opus-5",
        "claude-sonnet-5", "kimi-k2.5", "mistral-large-latest", "codestral-latest",
    ):
        assert model_id in models


def test_user_can_select_eligible_model() -> None:
    router = ModelRouter()
    selected = router.select_chain(_req(TaskType.CODE_REVIEW, requested_model="gpt-5.3-codex"))
    assert [item.id for item in selected] == ["gpt-5.3-codex"]


def test_non_selectable_or_ineligible_model_is_rejected() -> None:
    router = ModelRouter()
    with pytest.raises(RegistryError):
        router.select_chain(_req(TaskType.CHAT, requested_model="openrouter-llama-free"))
    with pytest.raises(RegistryError):
        router.select_chain(_req(TaskType.EMBEDDINGS, requested_model="gpt-5.6-sol"))


def test_embeddings_have_cohere_then_openai_fallback(monkeypatch) -> None:
    monkeypatch.setenv("COHERE_API_KEY", "test")
    monkeypatch.setenv("OPENAI_API_KEY", "test")
    router = ModelRouter()
    chain = router.select_chain(_req(TaskType.EMBEDDINGS))
    assert [item.id for item in chain] == [
        "cohere-embed-english-v3", "openai-text-embedding-3-large"
    ]


def test_quality_floor_never_silently_downgrades() -> None:
    router = ModelRouter()
    request = _req(TaskType.UNICORN_ANALYSIS)
    floor = router.policy_for(request).minimum_quality_score
    assert all(item.quality_score >= floor for item in router.select_chain(request))


def test_profitability_and_quality_profiles_rank_differently() -> None:
    os.environ["OPENAI_API_KEY"] = "test"
    try:
        router = ModelRouter()
        quality = router.select_chain(_req(TaskType.MARKET_INTELLIGENCE, execution_profile="quality"))[0]
        economy = router.select_chain(_req(TaskType.MARKET_INTELLIGENCE, execution_profile="profitability"))[0]
        assert quality.id != economy.id
        assert quality.quality_score >= economy.quality_score
    finally:
        os.environ.pop("OPENAI_API_KEY", None)
