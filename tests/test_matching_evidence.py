"""Fail-closed collaborator matching contracts."""

from __future__ import annotations

import asyncio
import os
import sys
import uuid
from types import SimpleNamespace
from typing import Any, Dict, List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("ENVIRONMENT", "development")

from agent_orchestration import AgentContext, MatchingAgent  # noqa: E402
from ai_router_core import UserContext, UserRole  # noqa: E402
from integration_guide import MatchingEngineService  # noqa: E402
from live_domain_repository import LiveDomainRepository  # noqa: E402


class FakeQuery:
    def __init__(self, rows: List[Any]) -> None:
        self.rows = rows

    def filter(self, *_args: Any) -> "FakeQuery":
        return self

    def order_by(self, *_args: Any) -> "FakeQuery":
        return self

    def limit(self, limit: int) -> "FakeQuery":
        return FakeQuery(self.rows[:limit])

    def all(self) -> List[Any]:
        return self.rows


class FakeSession:
    def __init__(self, rows_by_table: Dict[str, List[Any]]) -> None:
        self.rows_by_table = rows_by_table

    def query(self, model: Any) -> FakeQuery:
        return FakeQuery(self.rows_by_table.get(getattr(model, "__tablename__", ""), []))


def _user(user_id: str = "u_test") -> UserContext:
    return UserContext(
        user_id=user_id,
        role=UserRole.FOUNDER,
        project_id="p_test",
        project_stage="idea",
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


def _agent(ai_output: str = "Evidence-based explanation") -> MatchingAgent:
    agent = MatchingAgent.__new__(MatchingAgent)
    agent.config = None
    agent.ai_brain = None
    agent._history = []

    async def fake_call(*_args: Any, **_kwargs: Any) -> Any:
        return SimpleNamespace(output=ai_output, tokens_used=0)

    agent._call_ai = fake_call  # type: ignore[method-assign]
    return agent


def test_matching_agent_fails_closed_without_persisted_candidates() -> None:
    result = asyncio.run(_agent().execute(AgentContext(user_context=_user(), trigger_event={})))

    assert result.output["matches"] == []
    assert result.output["evidence_status"] == "insufficient_evidence"
    assert result.output["missing_evidence"] == ["persisted_match_candidates"]
    assert "Aisha Osei" not in str(result.output)
    assert "David Mensah" not in str(result.output)


def test_matching_agent_accepts_only_persisted_evidence() -> None:
    fabricated = {"user_id": "fake", "match_score": 99, "evidence": {"source": "request_payload"}}
    persisted = {
        "user_id": "real-user",
        "name": "Real Collaborator",
        "match_score": 81.5,
        "evidence": {"source": "persisted_match_record", "match_id": "match-1"},
    }
    result = asyncio.run(_agent().execute(AgentContext(
        user_context=_user(),
        trigger_event={"persisted_candidates": [fabricated, persisted]},
    )))

    assert result.output["matches"] == [persisted]
    assert result.output["evidence_status"] == "sufficient"


def test_repository_returns_real_match_and_structured_skills() -> None:
    seeker_id = uuid.uuid4()
    candidate_id = uuid.uuid4()
    match_id = uuid.uuid4()
    db = FakeSession({
        "matches": [SimpleNamespace(
            id=match_id,
            seeker_id=seeker_id,
            candidate_id=candidate_id,
            project_id=None,
            match_type="founder_builder",
            skill_similarity=0.9,
            goal_similarity=0.8,
            execution_style_similarity=0.7,
            availability_overlap=0.75,
            trust_score=0.82,
            domain_experience=0.68,
            match_score=83.4,
            risk_flags=[],
            status="pending",
            created_at=SimpleNamespace(isoformat=lambda: "2026-08-14T10:00:00"),
        )],
        "users": [SimpleNamespace(
            id=candidate_id,
            full_name="Verified Builder",
            role=SimpleNamespace(value="collaborator"),
            profile_completeness_pct=90,
            github_connected=True,
            linkedin_connected=False,
            created_at=SimpleNamespace(isoformat=lambda: "2026-08-13T10:00:00"),
        )],
        "user_skill_embeddings": [SimpleNamespace(
            user_id=candidate_id,
            skill_text='{"skills":["Python","FastAPI"]}',
            updated_at=SimpleNamespace(isoformat=lambda: "2026-08-14T09:00:00"),
        )],
    })

    matches = LiveDomainRepository(db).collaborator_matches(
        str(seeker_id),
        {"required_skills": ["Python"]},
    )

    assert len(matches) == 1
    assert matches[0]["user_id"] == str(candidate_id)
    assert matches[0]["name"] == "Verified Builder"
    assert matches[0]["skills"] == ["Python", "FastAPI"]
    assert matches[0]["match_score"] == 83.4
    assert matches[0]["profile_signals"]["profile_completeness_pct"] == 90
    assert matches[0]["evidence"]["source"] == "persisted_match_record"
    assert matches[0]["evidence"]["field_provenance"]["match_score"] == "matches.match_score"
    assert matches[0]["evidence"]["field_confidence"]["skills"] == 1.0
    assert matches[0]["evidence"]["freshness"]["skills"]["status"] == "known"
    assert matches[0]["evidence"]["policy_id"] is None
    assert matches[0]["evidence"]["policy_status"] == "legacy_or_unversioned"


def test_match_policy_status_recognizes_only_active_policy() -> None:
    assert LiveDomainRepository._match_policy_status("techit-scoring-2026-08-14-v1") == "current"
    assert LiveDomainRepository._match_policy_status(None) == "legacy_or_unversioned"
    assert LiveDomainRepository._match_policy_status("older-policy") == "legacy_or_unversioned"


def test_service_loads_repository_candidates_before_agent_execution() -> None:
    candidate = {
        "user_id": "real-user",
        "match_score": 80,
        "evidence": {"source": "persisted_match_record"},
    }

    class FakeRepository:
        def collaborator_matches(self, user_id: str, criteria: Dict[str, Any], limit: int) -> List[Dict[str, Any]]:
            assert user_id == "u_test"
            assert criteria == {"limit": 5}
            assert limit == 5
            return [candidate]

    class FakeBrain:
        async def trigger_agent(self, _agent_type: Any, context: AgentContext) -> Any:
            assert context.trigger_event["persisted_candidates"] == [candidate]
            return SimpleNamespace(output={
                "matches": [candidate],
                "explanations": None,
                "evidence_status": "sufficient",
                "missing_evidence": [],
            })

    class FakeAuditRecorder:
        def __init__(self) -> None:
            self.events: List[Dict[str, Any]] = []

        def record(self, event: Dict[str, Any]) -> None:
            self.events.append(event)

    recorder = FakeAuditRecorder()

    result = asyncio.run(MatchingEngineService(
        FakeBrain(),  # type: ignore[arg-type]
        FakeRepository(),  # type: ignore[arg-type]
        recorder,  # type: ignore[arg-type]
    ).find_collaborators(_user(), {"limit": 5}))

    assert result["matches"] == [candidate]
    assert result["evidence_status"] == "sufficient"
    assert len(recorder.events) == 1
    audit = recorder.events[0]
    assert audit["ranking_exposure"][0]["candidate_ref"] != candidate["user_id"]
    assert audit["protected_attributes_used"] is False
    assert audit["sensitive_profile_fields_recorded"] is False
    assert "real-user" not in str(audit)


if __name__ == "__main__":
    tests = [
        test_matching_agent_fails_closed_without_persisted_candidates,
        test_matching_agent_accepts_only_persisted_evidence,
        test_repository_returns_real_match_and_structured_skills,
        test_service_loads_repository_candidates_before_agent_execution,
    ]
    for test in tests:
        test()
    print(f"{len(tests)} matching evidence tests passed")
