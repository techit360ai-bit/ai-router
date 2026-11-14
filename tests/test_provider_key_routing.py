"""Credential-aware routing.

Providers whose credentials are known to be rejected are removed before the
attempt chain is cut to max_attempts. 16 task types failed in production
because every attempt went to OpenAI/Anthropic keys that were invalid, while
Bedrock and OpenRouter were healthy.
"""

from __future__ import annotations

import time

import pytest

import provider_key_health as pkh
from ai_router_core import AICommandLayer, AIRequest, ModelRouter, PromptEngine, SafetyEngine, TaskType, UserContext, UserRole


def _ctx(**kwargs) -> UserContext:
    values = dict(
        user_id="u_test", role=UserRole.FOUNDER, project_id="p_test",
        project_stage="mvp", industry="saas", tech_stack=[], past_feedback=[],
        training_progress={}, time_logged_today=0, tasks_completed_week=0,
    )
    values.update(kwargs)
    return UserContext(**values)


@pytest.fixture
def production_like_providers(monkeypatch):
    for name, value in {
        "OPENAI_API_KEY": "sk-openai", "ANTHROPIC_API_KEY": "sk-ant", "OPENROUTER_API_KEY": "sk-or",
        "BEDROCK_ENABLED": "true", "BEDROCK_REGION": "us-east-1",
        "AWS_ACCESS_KEY_ID": "AKIAEXAMPLE", "AWS_SECRET_ACCESS_KEY": "example",
    }.items():
        monkeypatch.setenv(name, value)
    monkeypatch.setattr(pkh, "_cache", {"checked_at": 0.0, "providers": {}})


def _quarantine(command_layer, provider, env):
    command_layer.credential_pool._state[f"{provider}:{env}"]["quarantined"] = 1


def test_chain_routes_around_quarantined_provider_keys(production_like_providers) -> None:
    command_layer = AICommandLayer(ModelRouter(), PromptEngine(), SafetyEngine())
    request = AIRequest(task_type=TaskType("risk_analysis"), user_context=_ctx(), input_data={"prompt": "Analyse"})
    before = command_layer.model_router.select_chain(request)
    assert {config.provider for config in before} <= {"openai", "anthropic"}  # the production failure mode
    _quarantine(command_layer, "openai", "OPENAI_API_KEY")
    _quarantine(command_layer, "anthropic", "ANTHROPIC_API_KEY")
    after = command_layer.model_router.select_chain(request)
    assert after, "healthy providers must remain eligible"
    assert not {config.provider for config in after} & {"openai", "anthropic"}


def test_chain_honours_live_credential_probe_verdicts(production_like_providers, monkeypatch) -> None:
    command_layer = AICommandLayer(ModelRouter(), PromptEngine(), SafetyEngine())
    monkeypatch.setattr(pkh, "_cache", {"checked_at": time.time(), "providers": {
        "openai": {"configured": 1, "valid": 0, "invalid": 1, "unknown": 0},
        "anthropic": {"configured": 1, "valid": 0, "invalid": 1, "unknown": 0},
    }})
    chain = command_layer.model_router.select_chain(AIRequest(task_type=TaskType("investor_readiness"), user_context=_ctx(), input_data={"prompt": "Plan"}))
    assert chain and not {config.provider for config in chain} & {"openai", "anthropic"}


def test_long_context_tasks_have_no_healthy_alternative(production_like_providers) -> None:
    # Documented limitation, not a routing bug: these task policies require the
    # long_context capability, which only OpenAI/Anthropic models carry, so they
    # need valid OpenAI or Anthropic credentials.
    command_layer = AICommandLayer(ModelRouter(), PromptEngine(), SafetyEngine())
    _quarantine(command_layer, "openai", "OPENAI_API_KEY")
    _quarantine(command_layer, "anthropic", "ANTHROPIC_API_KEY")
    chain = command_layer.model_router.select_chain(AIRequest(task_type=TaskType("market_intelligence"), user_context=_ctx(), input_data={"prompt": "Analyse"}))
    assert chain and {config.provider for config in chain} <= {"openai", "anthropic"}


def test_full_chain_is_kept_when_nothing_usable_remains(monkeypatch) -> None:
    for name in ("ANTHROPIC_API_KEY", "OPENROUTER_API_KEY", "BEDROCK_ENABLED", "GEMINI_API_KEY", "MISTRAL_API_KEY", "MOONSHOT_API_KEY", "COHERE_API_KEY", "AGENTROUTER_API_KEY"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("OPENAI_API_KEY", "sk-openai")
    monkeypatch.setattr(pkh, "_cache", {"checked_at": 0.0, "providers": {}})
    command_layer = AICommandLayer(ModelRouter(), PromptEngine(), SafetyEngine())
    _quarantine(command_layer, "openai", "OPENAI_API_KEY")
    chain = command_layer.model_router.select_chain(AIRequest(task_type=TaskType.CHAT, user_context=_ctx(), input_data={"message": "hi"}))
    # Nothing usable: keep the ranked chain so the caller gets the real provider error.
    assert chain


def test_cached_verdicts_ignore_stale_and_inconclusive_probes(monkeypatch) -> None:
    monkeypatch.setattr(pkh, "_cache", {"checked_at": time.time(), "providers": {
        "openai": {"configured": 1, "valid": 0, "invalid": 1, "unknown": 0},
        "anthropic": {"configured": 1, "valid": 0, "invalid": 0, "unknown": 1},
        "openrouter": {"configured": 1, "valid": 1, "invalid": 0, "unknown": 0},
    }})
    assert pkh.cached_unusable_providers() == {"openai"}
    monkeypatch.setattr(pkh, "_cache", {"checked_at": time.time() - 10 * pkh.CACHE_TTL_SECONDS, "providers": {
        "openai": {"configured": 1, "valid": 0, "invalid": 1, "unknown": 0},
    }})
    assert pkh.cached_unusable_providers() == set()
