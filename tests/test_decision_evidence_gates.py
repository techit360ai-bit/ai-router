"""Evidence gates for risk, investor, and unicorn decision surfaces."""

from __future__ import annotations

import asyncio
import os
import sys
from types import SimpleNamespace
from typing import Any, Dict

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("ENVIRONMENT", "development")

from agent_orchestration import (  # noqa: E402
    AgentContext,
    InvestorIntelligenceAgent,
    RiskEvaluatorAgent,
)
from ai_router_core import ScoringEngine, UserContext, UserRole  # noqa: E402
from integration_guide import InvestorSectionService, RiskEvaluatorService  # noqa: E402


def _user() -> UserContext:
    return UserContext(
        user_id="u_test",
        role=UserRole.FOUNDER,
        project_id="p_test",
        project_stage="idea",
        industry="saas",
        tech_stack=[],
        past_feedback=[],
        training_progress={},
        time_logged_today=0,
        tasks_completed_week=0,
        days_since_update=2,
        team_size=3,
        has_revenue=False,
        beta_users_count=25,
    )


def _agent(agent_type: type, output: str = "Provisional narrative") -> Any:
    agent = agent_type.__new__(agent_type)
    agent.config = None
    agent.ai_brain = None
    agent._history = []
    calls = []

    async def fake_call(*args: Any, **kwargs: Any) -> Any:
        calls.append((args, kwargs))
        return SimpleNamespace(output=output, tokens_used=0)

    agent._call_ai = fake_call
    agent.test_calls = calls
    return agent


def test_sparse_risk_input_is_blocked_without_ai_or_fake_swot() -> None:
    agent = _agent(RiskEvaluatorAgent)
    result = asyncio.run(agent.execute(AgentContext(
        user_context=_user(),
        trigger_event={"idea": {"problem": "A problem"}},
    )))
    risk = result.output["risk_analysis"]

    assert agent.test_calls == []
    assert risk["status"] == "insufficient_evidence"
    assert risk["competitive_risk"] is None
    assert risk["market_clarity_score"] is None
    assert risk["key_risks"] == []
    assert risk["swot"] == {}
    assert risk["evidence"]["missing_fields"] == ["solution", "target_customers"]


def test_complete_risk_input_remains_provisional_and_unscored() -> None:
    agent = _agent(RiskEvaluatorAgent)
    result = asyncio.run(agent.execute(AgentContext(
        user_context=_user(),
        trigger_event={"idea": {
            "problem": "Teams duplicate compliance evidence.",
            "solution": "A shared evidence workflow.",
            "target_customers": "Regulated software teams.",
        }},
    )))
    risk = result.output["risk_analysis"]

    assert len(agent.test_calls) == 1
    assert risk["status"] == "provisional_human_review_required"
    assert risk["ai_analysis"] == "Provisional narrative"
    assert risk["technical_feasibility"] is None
    assert risk["human_review_required"] is True


def test_investor_agent_does_not_derive_scores_from_user_counts() -> None:
    agent = _agent(InvestorIntelligenceAgent)
    result = asyncio.run(agent.execute(AgentContext(user_context=_user(), shared_memory={})))

    assert agent.test_calls == []
    assert result.output["investment_score"] is None
    assert result.output["evi_i"] is None
    assert result.output["evidence_status"] == "insufficient_evidence"
    assert "investment.market_readiness" in result.output["missing_evidence"]
    assert "evi_i.mdr" in result.output["missing_evidence"]


def test_investor_agent_computes_only_complete_explicit_scores() -> None:
    agent = _agent(InvestorIntelligenceAgent)
    memory: Dict[str, Any] = {
        "market_readiness": 80,
        "traction_score": 70,
        "team_score": 75,
        "risk_inverse": 65,
        "growth_rate": 60,
        "differentiation_score": 85,
        "mdr": 75,
        "is": 70,
        "trv": 65,
        "rta": 60,
        "ugm": 55,
        "cev": 80,
    }
    result = asyncio.run(agent.execute(AgentContext(user_context=_user(), shared_memory=memory)))

    assert len(agent.test_calls) == 1
    assert result.output["investment_score"] is not None
    assert result.output["evi_i"] is not None
    assert result.output["evidence_status"] == "sufficient"
    assert result.output["probability_calibrated"] is False


def test_unicorn_score_is_not_exposed_as_probability() -> None:
    result = ScoringEngine.compute_unicorn_potential_score({})

    assert result["unicorn_probability_pct"] is None
    assert result["probability_calibrated"] is False
    assert result["score_kind"] == "heuristic_human_review_required"


def test_risk_service_does_not_default_to_medium() -> None:
    class FakeBrain:
        async def trigger_agent(self, *_args: Any, **_kwargs: Any) -> Any:
            return SimpleNamespace(
                output={"risk_analysis": {
                    "status": "insufficient_evidence",
                    "competitive_risk": None,
                    "key_risks": [],
                    "swot": {},
                    "evidence": {"missing_fields": ["solution"]},
                }},
                recommendations=["Supply evidence"],
            )

    result = asyncio.run(RiskEvaluatorService(FakeBrain()).evaluate_idea_risk(_user(), {}))

    assert result["risk_level"] is None
    assert result["evidence_status"] == "insufficient_evidence"
    assert result["missing_evidence"] == ["solution"]


def test_investor_readiness_requires_all_normalized_scores() -> None:
    service = InvestorSectionService.__new__(InvestorSectionService)
    result = asyncio.run(service.get_investor_readiness(_user(), {
        "market_readiness_score": 80,
    }))

    assert result["investment_score"] is None
    assert result["investment_readiness"] == "insufficient_evidence"
    assert "traction_score" in result["missing_evidence"]


if __name__ == "__main__":
    tests = [
        test_sparse_risk_input_is_blocked_without_ai_or_fake_swot,
        test_complete_risk_input_remains_provisional_and_unscored,
        test_investor_agent_does_not_derive_scores_from_user_counts,
        test_investor_agent_computes_only_complete_explicit_scores,
        test_unicorn_score_is_not_exposed_as_probability,
        test_risk_service_does_not_default_to_medium,
        test_investor_readiness_requires_all_normalized_scores,
    ]
    for test in tests:
        test()
    print(f"{len(tests)} decision evidence tests passed")
