"""
Investment Intelligence Engine tests (TIRS vs TAS, Profile Header, Overview).
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("ALLOW_DEMO_AUTH", "true")

from ai_router_core import UserContext, UserRole
from integration_guide import InvestorSectionService, TechITAIBrain
from live_domain_repository import reset_memory_store_for_tests


def setup_module() -> None:
    reset_memory_store_for_tests()


def test_investment_readiness_score_tirs() -> None:
    reset_memory_store_for_tests()
    brain = TechITAIBrain()
    service = InvestorSectionService(brain)

    startup_data = {
        "market_opportunity": 85.0,
        "problem_solution_fit": 90.0,
        "competitive_differentiation": 80.0,
        "business_model": 85.0,
        "gtm_readiness": 75.0,
        "product_readiness": 80.0,
        "execution_capability": 88.0,
        "financial_viability": 70.0,
        "team_readiness": 90.0,
        "development_stage": "mvp",
        "verified": True,
    }

    tirs = service.compute_tirs(startup_data)
    assert "tirs_score" in tirs
    assert tirs["tirs_score"] > 0
    assert tirs["stage_aware"] == "mvp"
    assert "dimensions" in tirs


def test_thesis_alignment_score_tas() -> None:
    reset_memory_store_for_tests()
    brain = TechITAIBrain()
    service = InvestorSectionService(brain)

    startup_data = {
        "industry": "FinTech",
        "development_stage": "Seed",
        "geography": "Nigeria",
    }

    investor_thesis = {
        "industries": ["FinTech", "SaaS"],
        "stages": ["Seed", "Series A"],
        "geographies": ["Nigeria", "Kenya"],
    }

    tas = service.compute_tas(startup_data, investor_thesis)
    assert tas["tas_score"] == 100.0
    assert tas["thesis_alignment"] == "High"


def test_investment_intelligence_profile() -> None:
    reset_memory_store_for_tests()
    brain = TechITAIBrain()
    service = InvestorSectionService(brain)
    user = UserContext(
        user_id="u_inv", role=UserRole.INVESTOR, project_id="p_test",
        project_stage="growth", industry="FinTech", tech_stack=[], past_feedback=[],
        training_progress={}, time_logged_today=0, tasks_completed_week=0,
    )

    profile = asyncio_run(service.get_investment_intelligence_profile(user, "p_test", {"industries": ["FinTech"]}))
    assert profile["project_id"] == "p_test"
    assert "profile_header" in profile
    assert "investment_readiness_score" in profile
    assert "investment_attractiveness_score" in profile
    assert "overview_module" in profile


def asyncio_run(coro):
    import asyncio
    return asyncio.run(coro)
