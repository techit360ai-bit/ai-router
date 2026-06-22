"""
Contract test for PR #11 — WorkspaceAssistantAgent forwards
trigger_event.available_tools into the LLM input_data so the agent's prompt
becomes tool-aware (otherwise the F2 service-layer wiring would inject the
MCP tool catalogue and the agent would silently drop it).

Standalone (no pytest dependency, matching tests/test_model_routing.py). Run:
    python3 tests/test_workspace_agent_forwards_tools.py
Exit 0 = all asserts passed.

Strategy: stub out _call_ai on a real WorkspaceAssistantAgent instance to
capture the input_data dict the agent assembles. Assert available_tools and
workspace both reach it. We don't talk to any real LLM.
"""

import asyncio
import os
import sys
from types import SimpleNamespace
from typing import Any, Dict, List

# Allow running from repo root or tests/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Auth env hardening (C3) refuses to import main.py in prod when demo-auth is on;
# we don't import main here, only agent_orchestration. Set a harmless env anyway.
os.environ.setdefault("ENVIRONMENT", "development")

from agent_orchestration import (  # noqa: E402
    AgentContext,
    WorkspaceAssistantAgent,
)
from ai_router_core import (  # noqa: E402
    SubscriptionTier,
    UserContext,
    UserRole,
)


def _user() -> UserContext:
    return UserContext(
        user_id="u_test",
        role=UserRole.FOUNDER,
        subscription_tier=SubscriptionTier.FOUNDER_PRO,
        credits_remaining=100,
        project_id="p_test",
        project_stage="mvp",
        industry="saas",
        tech_stack=[],
        past_feedback=[],
        training_progress={},
        time_logged_today=0,
        tasks_completed_week=0,
        days_since_update=0,
        team_size=1,
        has_revenue=False,
        beta_users_count=0,
    )


def _agent_with_spy() -> tuple[WorkspaceAssistantAgent, Dict[str, Any]]:
    """Build a WorkspaceAssistantAgent whose _call_ai is replaced by a spy that
    captures the input_data dict and returns a fake AIResponse. Returns the
    agent and the captured dict (the dict is filled in by the spy on call)."""
    captured: Dict[str, Any] = {}

    async def spy_call_ai(task_type, input_data, user_context, **_):  # noqa: ARG001
        captured["task_type"] = task_type
        captured["input_data"] = input_data
        captured["user_context"] = user_context
        return SimpleNamespace(output={"task_suggestions": ["x"]}, credits_consumed=0)

    # Construct with bare-minimum config + brain — neither is touched once
    # _call_ai is replaced.
    agent = WorkspaceAssistantAgent.__new__(WorkspaceAssistantAgent)
    agent.config = None
    agent.ai_brain = None
    agent._history = []
    agent._call_ai = spy_call_ai  # type: ignore[attr-defined]
    return agent, captured


def test_available_tools_reach_input_data_when_present() -> None:
    """The whole point of PR #11: tools in trigger_event must reach input_data."""
    agent, captured = _agent_with_spy()
    tools: List[Dict[str, Any]] = [
        {"plugin": "github", "tool": {"name": "list_repositories"}},
        {"plugin": "github", "tool": {"name": "create_pull_request"}},
    ]
    ctx = AgentContext(
        user_context=_user(),
        trigger_event={
            "workspace_data": {"project": "demo"},
            "available_tools": tools,
        },
    )
    asyncio.run(agent.execute(ctx))
    assert "input_data" in captured, "spy was never called"
    payload = captured["input_data"]
    assert "available_tools" in payload, f"missing available_tools; got keys: {list(payload)}"
    assert payload["available_tools"] == tools, (
        f"available_tools mismatch: expected {tools!r}, got {payload['available_tools']!r}"
    )
    assert payload["workspace"] == {"project": "demo"}, "workspace dropped"


def test_available_tools_default_empty_when_missing() -> None:
    """Absent trigger_event.available_tools must surface as an empty list, not
    a missing key — keeps prompt-template shape consistent so the LLM never sees
    `available_tools: undefined`."""
    agent, captured = _agent_with_spy()
    ctx = AgentContext(
        user_context=_user(),
        trigger_event={"workspace_data": {"project": "demo"}},
    )
    asyncio.run(agent.execute(ctx))
    payload = captured["input_data"]
    assert payload.get("available_tools") == [], (
        f"available_tools should default to [], got {payload.get('available_tools')!r}"
    )


def test_trigger_event_none_doesnt_crash() -> None:
    """If trigger_event itself is None the agent must still produce a valid
    AgentResult — no AttributeError on .get()."""
    agent, captured = _agent_with_spy()
    ctx = AgentContext(user_context=_user(), trigger_event=None)
    result = asyncio.run(agent.execute(ctx))
    assert result.success is True
    assert captured["input_data"]["available_tools"] == []
    assert captured["input_data"]["workspace"] == {}


def main() -> int:
    tests = [
        test_available_tools_reach_input_data_when_present,
        test_available_tools_default_empty_when_missing,
        test_trigger_event_none_doesnt_crash,
    ]
    for t in tests:
        try:
            t()
            print(f"  ok  {t.__name__}")
        except AssertionError as exc:
            print(f"  FAIL {t.__name__}: {exc}")
            return 1
        except Exception as exc:  # noqa: BLE001
            print(f"  ERROR {t.__name__}: {type(exc).__name__}: {exc}")
            return 1
    print(f"\n{len(tests)} passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
