"""Tier-aware routing: users who are not subscribed or paying run on Bedrock.

The backend signs routing_tier="standard" into the execution grant for users
without an active subscription or credit purchase, and "premium" otherwise.
Standard-tier requests are restricted to AI_STANDARD_TIER_PROVIDERS (default
"bedrock"); premium and tier-less grants keep the normal ranked chain, which
still falls back to Bedrock when OpenAI/Anthropic keys are unusable.
"""

from __future__ import annotations

import asyncio
import os
import sys

import pytest
from jose import jwt

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("SECRET_KEY", "unit-test-secret-value-that-is-long-enough")
os.environ.setdefault("ENVIRONMENT", "development")

from ai_router_core import AIRequest, ModelRouter, TaskType, UserContext, UserRole  # noqa: E402
from execution_controls import ExecutionAuthorizationError, ExecutionGrant, ExecutionGrantVerifier  # noqa: E402


@pytest.fixture(autouse=True)
def all_providers_configured(monkeypatch):
    for name, value in {
        "OPENAI_API_KEY": "sk-openai", "ANTHROPIC_API_KEY": "sk-ant", "OPENROUTER_API_KEY": "sk-or",
        "BEDROCK_ENABLED": "true", "BEDROCK_REGION": "us-east-1",
        "AWS_ACCESS_KEY_ID": "AKIAEXAMPLE", "AWS_SECRET_ACCESS_KEY": "example",
    }.items():
        monkeypatch.setenv(name, value)
    monkeypatch.delenv("AI_STANDARD_TIER_PROVIDERS", raising=False)


def _ctx(grant=None) -> UserContext:
    return UserContext(
        user_id="u", role=UserRole.FOUNDER, project_id="p", project_stage="mvp",
        industry="saas", tech_stack=[], past_feedback=[], training_progress={},
        time_logged_today=0, tasks_completed_week=0, execution_grant=grant,
    )


def _grant(tier: str) -> ExecutionGrant:
    return ExecutionGrant(subject="u", workspace_id=None, request_id="r-1", task_type=None, routing_tier=tier)


def _chain(task: str, tier: str, **input_data):
    return ModelRouter().select_chain(AIRequest(task_type=TaskType(task), user_context=_ctx(_grant(tier)), input_data=input_data or {"prompt": "x"}))


@pytest.mark.parametrize("task", ["chat", "business_plan", "market_intelligence", "document_investor_report", "embeddings", "idea_evaluation"])
def test_standard_tier_runs_on_bedrock_only(task) -> None:
    chain = _chain(task, "standard")
    assert chain and {config.provider for config in chain} == {"bedrock"}


def test_premium_and_tierless_grants_keep_the_ranked_chain() -> None:
    premium = _chain("business_plan", "premium")
    tierless = _chain("business_plan", "")
    assert [config.id for config in premium] == [config.id for config in tierless]
    assert premium[0].provider in {"openai", "anthropic"}  # quality ranking for paying users


def test_standard_tier_refuses_an_explicitly_requested_paid_plan_model() -> None:
    with pytest.raises(ExecutionAuthorizationError, match="paid plans"):
        _chain("chat", "standard", model_id="gpt-5.5")
    chain = _chain("chat", "standard", model_id="bedrock-claude-haiku")
    assert [config.id for config in chain] == ["bedrock-claude-haiku"]


def test_empty_provider_list_disables_tier_routing(monkeypatch) -> None:
    monkeypatch.setenv("AI_STANDARD_TIER_PROVIDERS", "")
    assert [config.id for config in _chain("business_plan", "standard")] == [config.id for config in _chain("business_plan", "premium")]


def test_verifier_reads_the_routing_tier_claim(monkeypatch) -> None:
    for key in ("AI_EXECUTION_GRANT_ALGORITHM", "AI_EXECUTION_GRANT_PUBLIC_KEY", "JWT_PUBLIC_KEY", "JWT_SECRET"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("AI_EXECUTION_GRANT_SECRET", "dev-grant-secret")

    def verify(**claims):
        token = jwt.encode({"sub": "u", "request_id": "r", "iss": "techit-backend", "aud": "techit-ai-router", **claims}, "dev-grant-secret", algorithm="HS256")
        return ExecutionGrantVerifier().verify(token).routing_tier

    assert verify(routing_tier="standard") == "standard"
    assert verify(routing_tier="PREMIUM") == "premium"
    assert verify(routing_tier="gold") == ""  # unknown tier: unrestricted
    assert verify() == ""


def test_model_listing_shows_standard_tier_users_only_what_they_can_run() -> None:
    import main as main_module

    listed = asyncio.run(main_module.list_models(task_type="chat", user=_ctx(_grant("standard"))))
    assert listed["models"] and {model["provider"] for model in listed["models"]} == {"bedrock"}
    everything = asyncio.run(main_module.list_models(task_type="chat", user=_ctx(_grant("premium"))))
    assert {model["provider"] for model in everything["models"]} > {"bedrock"}
