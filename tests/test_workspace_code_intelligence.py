import json
import os
import sys
from types import SimpleNamespace

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ai_router_core import UserContext, UserRole
from integration_guide import WorkspaceAIService


def user() -> UserContext:
    return UserContext(
        user_id="user-1",
        role=UserRole.FOUNDER,
        project_id="project-1",
        project_stage="mvp",
        industry="saas",
        tech_stack=["typescript"],
        past_feedback=[],
        training_progress={},
        time_logged_today=0,
        tasks_completed_week=0,
        workspace_id="workspace-1",
    )


class Repo:
    def latest_workspace_context_pack(self, user_id, workspace_id):
        assert user_id == "user-1"
        assert workspace_id == "workspace-1"
        return {"contextData": {"schema_version": "1.0", "current_task": "Build onboarding"}}

    def workspace_context(self, user_id, workspace_id, project_id=None):
        return {"venture": {"stage": "MVP", "nextGoal": "Ship onboarding"}}


class Brain:
    def __init__(self, output):
        self.output = output
        self.requests = []

    async def process(self, request):
        self.requests.append(request)
        return SimpleNamespace(output=self.output, model_used="free-router-model")


def service(output) -> WorkspaceAIService:
    instance = WorkspaceAIService.__new__(WorkspaceAIService)
    instance.brain = Brain(output)
    instance.repo = Repo()
    return instance


@pytest.mark.asyncio
async def test_code_plan_is_contextual_and_never_claims_execution_authority():
    instance = service(json.dumps({
        "summary": "Extend the existing onboarding.",
        "existingSystems": ["authentication"],
        "changes": [{"path": "src/onboarding.ts", "action": "modify", "reason": "Reuse auth"}],
        "tests": ["Run onboarding tests"],
        "securityChecks": ["Verify role access"],
    }))

    result = await instance.plan_code_task(user(), {
        "workspace_id": "workspace-1",
        "project_id": "project-1",
        "requirement": "Build founder onboarding",
        "files": [{"path": "src/onboarding.ts", "language": "typescript"}],
    })

    assert result["authoritative"] is False
    assert result["execution"]["performed"] is False
    assert result["execution"]["requires_mcp"] is True
    assert result["context_injected"] is True
    assert result["plan"]["existingSystems"] == ["authentication"]
    assert "CodeAgent" in result["plan"]["recommendedAgentFlow"]
    assert instance.brain.requests[0].input_data["workspace_context_pack"]["current_task"] == "Build onboarding"


@pytest.mark.asyncio
async def test_code_proposal_is_limited_to_supplied_safe_paths_and_not_applied():
    instance = service({
        "summary": "Reviewable changes",
        "changes": [
            {"path": "src/app.ts", "content": "export const ready = true", "reason": "Implement task"},
            {"path": "src/unauthorized.ts", "content": "export const escape = true", "reason": "Not supplied"},
            {"path": "../secret", "content": "TOKEN=bad", "reason": "Traversal"},
        ],
        "tests": ["npm test"],
        "securityNotes": ["No authority to save or push"],
    })

    result = await instance.propose_code_changes(user(), {
        "workspace_id": "workspace-1",
        "requirement": "Update the app",
        "files": [
            {"path": "src/app.ts", "language": "typescript", "content": "export const ready = false"},
            {"path": "../secret", "language": "text", "content": "do not expose"},
        ],
    })

    assert result["authoritative"] is False
    assert result["applied"] is False
    assert [change["path"] for change in result["proposal"]["changes"]] == ["src/app.ts"]
    assert instance.brain.requests[0].input_data["files"] == [{
        "path": "src/app.ts",
        "content": "export const ready = false",
        "language": "typescript",
    }]


@pytest.mark.asyncio
async def test_bounded_orchestration_returns_every_stage_without_execution_authority():
    instance = service({
        "summary": "Build through existing workspace controls.",
        "stages": [
            {"stage": "execution_intelligence", "agent": "ExecutionIntelligenceAgent", "summary": "Prioritize onboarding."},
            {"stage": "code", "agent": "CodeAgent", "summary": "Propose a scoped edit.", "actions": ["Modify src/app.ts"]},
        ],
    })
    result = await instance.orchestrate_code_task(user(), {
        "workspace_id": "workspace-1",
        "requirement": "Build onboarding",
        "allowed_paths": ["src/app.ts", "../secret"],
        "allowed_commands": ["npm test"],
    })
    assert result["authoritative"] is False
    assert result["execution"] == {"performed": False, "requires_backend_run": True, "requires_mcp": True, "mutation_free": True}
    assert [stage["stage"] for stage in result["orchestration"]["stages"]] == [
        "execution_intelligence", "mvp_builder", "product_architect", "code", "test", "debugger", "security", "review", "deployment",
    ]
    assert instance.brain.requests[0].input_data["allowed_paths"] == ["src/app.ts"]
