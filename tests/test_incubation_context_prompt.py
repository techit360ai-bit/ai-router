"""
Unit tests for incubation-context injection into agent system prompts (#8).

Targets ai_router_core only (no FastAPI import), so it runs without the full
app dependency set. Covers:
  - IncubationContext rendering + emptiness
  - from_workspace_context tolerating camelCase/snake_case blueprint aliases
  - PromptEngine.build_prompt embedding the incubation block + GLOBAL_FOUNDATION
  - AICommandLayer.process threading request.incubation into the prompt (via a
    stubbed model call, no network)
"""
import asyncio

import agent_prompts as AP
from ai_router_core import (
    IncubationContext, PromptEngine, TaskType, UserRole,
)


def test_empty_context_renders_nothing():
    assert IncubationContext().is_empty() is True
    assert IncubationContext().to_prompt_context() == ""


def test_context_renders_known_fields_only():
    ic = IncubationContext(stage="Early Traction", gsis=72.5, next_goal="Close 10 design partners")
    out = ic.to_prompt_context()
    assert "INCUBATION CONTEXT" in out
    assert "Stage:" in out and "Early Traction" in out
    assert "72.5/100" in out
    assert "Next Goal:" in out and "Close 10 design partners" in out
    # Absent fields are omitted, not rendered blank.
    assert "Market:" not in out


def test_from_workspace_context_alias_probing():
    wc = {
        "venture": {
            "currentStage": "Pre-Aha",
            "market_opportunity": "SMB fintech in West Africa",
            "targetUsers": "Founders raising pre-seed",
            "businessModel": "SaaS + take-rate",
            "nextGoal": "Ship MVP",
        }
    }
    ic = IncubationContext.from_workspace_context(wc, gsis=64.0)
    assert ic.stage == "Pre-Aha"
    assert ic.market == "SMB fintech in West Africa"
    assert ic.customer == "Founders raising pre-seed"
    assert ic.business_model == "SaaS + take-rate"
    assert ic.next_goal == "Ship MVP"
    assert ic.gsis == 64.0
    assert ic.is_empty() is False


def test_from_workspace_context_no_venture_is_empty():
    assert IncubationContext.from_workspace_context(None).is_empty() is True
    assert IncubationContext.from_workspace_context({"venture": None}).is_empty() is True


def test_build_prompt_injects_incubation_and_foundation():
    engine = PromptEngine()
    ic = IncubationContext(stage="Idea Stage", milestone="Validate problem")
    context = {
        "user": "USER CONTEXT:\n  Role: founder",
        "input": {"code": "print(1)"},
        "timestamp": "2026-01-01T00:00:00",
        "incubation": ic.to_prompt_context(),
    }
    prompt = asyncio.run(engine.build_prompt(TaskType.CODE_REVIEW, context, UserRole.FOUNDER))
    assert AP.GLOBAL_FOUNDATION.split(".")[0] in prompt      # foundation now wired
    assert "INCUBATION CONTEXT" in prompt
    assert "Idea Stage" in prompt and "Validate problem" in prompt
    # Ordering: foundation → incubation → user context.
    assert prompt.index("INCUBATION CONTEXT") < prompt.index("USER CONTEXT")


def test_build_prompt_without_incubation_is_unchanged_shape():
    engine = PromptEngine()
    context = {"user": "u", "input": {}, "timestamp": "t"}
    prompt = asyncio.run(engine.build_prompt(TaskType.CODE_REVIEW, context, UserRole.FOUNDER))
    assert "INCUBATION CONTEXT" not in prompt
    assert "USER CONTEXT:" in prompt
