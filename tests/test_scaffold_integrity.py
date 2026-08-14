"""Generated scaffold and deployment paths must not fabricate artifacts."""

from __future__ import annotations

import asyncio
import json
import os
import sys
from types import SimpleNamespace
from typing import Any, List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("ENVIRONMENT", "development")

from agent_orchestration import AgentContext, AppScaffoldAgent  # noqa: E402
from ai_router_core import PromptEngine, TaskType, UserContext, UserRole  # noqa: E402
from integration_guide import AppScaffoldService  # noqa: E402


def _user() -> UserContext:
    return UserContext(
        user_id="u_test",
        role=UserRole.FOUNDER,
        project_id="p_test",
        project_stage="mvp",
        industry="saas",
        tech_stack=[],
        past_feedback=[],
        training_progress={},
        time_logged_today=0,
        tasks_completed_week=0,
    )


def _agent(outputs: List[str]) -> tuple[AppScaffoldAgent, List[Any]]:
    agent = AppScaffoldAgent.__new__(AppScaffoldAgent)
    agent.config = None
    agent.ai_brain = None
    agent._history = []
    calls: List[Any] = []

    async def fake_call(*args: Any, **kwargs: Any) -> Any:
        calls.append((args, kwargs))
        return SimpleNamespace(output=outputs[len(calls) - 1], tokens_used=1)

    agent._call_ai = fake_call
    return agent, calls


def _valid_scaffold() -> str:
    return json.dumps({
        "pages": [{"route": "/", "component_name": "Home"}],
        "schema_sql": "CREATE TABLE projects (id uuid primary key);",
        "api_routes": [],
        "env_template": "DATABASE_URL=",
        "components": [],
        "setup_steps": ["npm install"],
        "estimated_build_hours": 8,
    })


def _context(stack: str | None = "nextjs_prisma") -> AgentContext:
    return AgentContext(
        user_context=_user(),
        trigger_event={"stack": stack} if stack else {},
        shared_memory={"venture_profile": {"startup_name": "Evidence App"}},
    )


def test_scaffold_requires_explicit_supported_stack_before_ai() -> None:
    agent, calls = _agent([])
    result = asyncio.run(agent.execute(_context(None)))

    assert result.success is False
    assert calls == []
    assert result.output["reason_code"] == "explicit_supported_stack_required"
    assert result.output["download_url"] is None


def test_invalid_scaffold_output_fails_without_deploy_generation() -> None:
    agent, calls = _agent(["not-json"])
    result = asyncio.run(agent.execute(_context()))

    assert result.success is False
    assert len(calls) == 1
    assert result.output["reason_code"] == "invalid_scaffold_output"
    assert result.output["live_url"] is None


def test_invalid_deploy_output_rejects_entire_generation() -> None:
    agent, calls = _agent([_valid_scaffold(), "{}"])
    result = asyncio.run(agent.execute(_context()))

    assert result.success is False
    assert len(calls) == 2
    assert result.output["reason_code"] == "invalid_deploy_configuration_output"
    assert result.output["artifact_registered"] is False


def test_valid_generation_has_no_urls_until_artifact_registration() -> None:
    agent, _calls = _agent([_valid_scaffold(), json.dumps({"deploy_steps": ["build"]})])
    context = _context()
    result = asyncio.run(agent.execute(context))

    assert result.success is True
    assert result.output["status"] == "generated_unregistered"
    assert result.output["artifact_registered"] is False
    assert result.output["download_url"] is None
    assert result.output["deploy_url"] is None
    assert result.output["live_url"] is None
    assert context.shared_memory["app_scaffold"] == result.output


def test_unconfigured_deployment_never_reports_started_or_live() -> None:
    service = AppScaffoldService(SimpleNamespace())
    deployment = asyncio.run(service.deploy_scaffold(_user(), "scaffold-1"))
    status = service.get_deploy_status("scaffold-1")
    live = service.get_live_url("scaffold-1")

    assert deployment["deployment_started"] is False
    assert deployment["live_url"] is None
    assert status["ready"] is False
    assert status["live_url"] is None
    assert live["deploy_status"] == "unavailable"
    assert live["live_url"] is None


def test_scaffold_prompt_has_no_framework_default() -> None:
    prompt = PromptEngine.SYSTEM_PROMPTS[TaskType.APP_SCAFFOLD_GENERATION]

    assert "Use Next.js 14 App Router + Supabase + Tailwind CSS by default" not in prompt
    assert "explicit approved stack" in prompt


if __name__ == "__main__":
    tests = [
        test_scaffold_requires_explicit_supported_stack_before_ai,
        test_invalid_scaffold_output_fails_without_deploy_generation,
        test_invalid_deploy_output_rejects_entire_generation,
        test_valid_generation_has_no_urls_until_artifact_registration,
        test_unconfigured_deployment_never_reports_started_or_live,
        test_scaffold_prompt_has_no_framework_default,
    ]
    for test in tests:
        test()
    print(f"{len(tests)} scaffold integrity tests passed")
