"""
WS4 routing smoke test. Standalone (no pytest dependency): run with
    python3 tests/test_model_routing.py
Exit 0 = all asserts passed. Imports ai_router_core directly (no external deps).
"""
import os
import sys

# allow running from repo root or tests/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ai_router_core import (  # noqa: E402
    ModelRouter, ModelProvider, ComplexityTier, TaskType,
    AIRequest, UserContext, UserRole, SubscriptionTier,
)


def _req(task: TaskType, tier: SubscriptionTier = SubscriptionTier.FOUNDER_PRO) -> AIRequest:
    ctx = UserContext(
        user_id="u_test", role=UserRole.FOUNDER, subscription_tier=tier,
        credits_remaining=100, project_id="p_test", project_stage="mvp",
        industry="saas", tech_stack=[], past_feedback=[], training_progress={},
        time_logged_today=0, tasks_completed_week=0,
    )
    return AIRequest(task_type=task, user_context=ctx, input_data={})


def test_construction_validates():
    ModelRouter()  # must not raise (exercises _validate_coverage)


def test_every_task_resolves_nonempty():
    r = ModelRouter()
    for task in TaskType:
        chain = r.select_chain(_req(task))
        assert chain, f"empty chain for {task}"


def test_trivial_is_free_first_when_keyed():
    os.environ["OPENROUTER_API_KEY"] = "test-key"
    try:
        r = ModelRouter()
        chain = r.select_chain(_req(TaskType.MATCHING))  # TRIVIAL
        assert chain[0].provider == ModelProvider.OPENROUTER_FREE, chain[0].provider
    finally:
        del os.environ["OPENROUTER_API_KEY"]


def test_trivial_nonempty_when_unkeyed():
    os.environ.pop("OPENROUTER_API_KEY", None)
    os.environ.pop("GEMINI_API_KEY", None)
    r = ModelRouter()
    chain = r.select_chain(_req(TaskType.MATCHING))
    assert chain, "chain must be non-empty even with no keys"


def test_free_subscription_never_premium():
    r = ModelRouter()
    chain = r.select_chain(_req(TaskType.UNICORN_ANALYSIS, SubscriptionTier.FREE))
    providers = {c.provider for c in chain}
    assert ModelProvider.OPENAI_GPT4 not in providers
    assert ModelProvider.ANTHROPIC_CLAUDE not in providers


def test_embeddings_routes_to_cohere():
    r = ModelRouter()
    chain = r.select_chain(_req(TaskType.EMBEDDINGS))
    assert chain[0].provider == ModelProvider.COHERE_EMBED


def test_select_model_is_chain_head():
    r = ModelRouter()
    req = _req(TaskType.CHAT)
    assert r.select_model(req).provider == r.select_chain(req)[0].provider


def test_ineligible_providers_appended_not_dropped():
    # With no keys set, TRIVIAL chain must still contain ALL four providers
    # (eligible-first ordering must never DROP a provider).
    for var in ("OPENROUTER_API_KEY", "GEMINI_API_KEY", "ANTHROPIC_API_KEY", "OPENAI_API_KEY"):
        os.environ.pop(var, None)
    r = ModelRouter()
    chain = r.select_chain(_req(TaskType.MATCHING))  # TRIVIAL
    providers = [c.provider for c in chain]
    assert ModelProvider.OPENROUTER_FREE in providers
    assert ModelProvider.GEMINI_FLASH_LITE in providers
    assert ModelProvider.ANTHROPIC_HAIKU in providers
    assert ModelProvider.OPENAI_GPT4_MINI in providers
    assert len(providers) == len(set(providers)), "chain must be deduped"


def test_heavy_tier_prefers_gpt4_head():
    # A HEAVY task for a paid user heads the chain with the strongest model.
    for var in ("OPENROUTER_API_KEY", "GEMINI_API_KEY", "ANTHROPIC_API_KEY", "OPENAI_API_KEY"):
        os.environ.pop(var, None)
    r = ModelRouter()
    chain = r.select_chain(_req(TaskType.UNICORN_ANALYSIS))  # HEAVY, FOUNDER_PRO
    assert chain[0].provider == ModelProvider.OPENAI_GPT4, chain[0].provider


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
        print(f"PASS {fn.__name__}")
    print(f"\nAll {len(fns)} routing tests passed.")
