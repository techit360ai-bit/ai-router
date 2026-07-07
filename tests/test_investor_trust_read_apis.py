"""
Investor Trust Dashboard read API tests. Standalone (no pytest dependency): run with
    python3 tests/test_investor_trust_read_apis.py
Exit 0 = all asserts passed. Uses fake sessions only.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import Any, Dict, List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("ALLOW_DEMO_AUTH", "true")

from ai_router_core import SubscriptionTier, UserContext, UserRole  # noqa: E402
from main import app, investor_trust_dashboard, investor_trust_startups  # noqa: E402
from trust_investor_read_model import InvestorTrustReadService  # noqa: E402


class FakeQuery:
    def __init__(self, rows: List[Any] | None = None) -> None:
        self.rows = rows or []

    def filter(self, *_args: Any, **_kwargs: Any) -> "FakeQuery":
        return self

    def order_by(self, *_args: Any, **_kwargs: Any) -> "FakeQuery":
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


def _investor() -> UserContext:
    return UserContext(
        user_id="investor_001",
        role=UserRole.INVESTOR,
        subscription_tier=SubscriptionTier.INVESTOR,
        credits_remaining=100,
        project_id=None,
        project_stage=None,
        industry=None,
        tech_stack=[],
        past_feedback=[],
        training_progress={},
        time_logged_today=0,
        tasks_completed_week=0,
    )


def _founder() -> UserContext:
    return UserContext(
        user_id="founder_001",
        role=UserRole.FOUNDER,
        subscription_tier=SubscriptionTier.FOUNDER_PRO,
        credits_remaining=100,
        project_id="startup_001",
        project_stage="beta",
        industry="saas",
        tech_stack=[],
        past_feedback=[],
        training_progress={},
        time_logged_today=0,
        tasks_completed_week=0,
    )


def _db() -> FakeSession:
    now = datetime(2026, 7, 6, 10, 0, 0)
    return FakeSession({
        "projects": [
            SimpleNamespace(
                id="startup_001",
                title="QuantumAPI",
                industry="SaaS",
                stage=SimpleNamespace(value="beta"),
                transparency_items={
                    "country": "United States",
                    "funding_stage": "Seed",
                    "website": "https://quantumapi.example",
                },
                compliance_items={},
                created_at=datetime(2024, 1, 1),
                updated_at=now,
            ),
            SimpleNamespace(
                id="startup_002",
                title="NeuralEdge AI",
                industry="AI/ML",
                stage=SimpleNamespace(value="launch"),
                transparency_items={"country": "United Kingdom", "funding_stage": "Series A"},
                compliance_items={},
                created_at=datetime(2023, 1, 1),
                updated_at=now - timedelta(days=1),
            ),
        ],
        "investor_watchlist": [
            SimpleNamespace(investor_id="investor_001", project_id="startup_001", notes="private note must not leak"),
            SimpleNamespace(investor_id="other_investor", project_id="startup_002", notes="other private note"),
        ],
        "trust_profiles": [
            SimpleNamespace(
                project_id="startup_001",
                email_verified=True,
                phone_verified=False,
                github_connected=True,
                linkedin_connected=True,
                domain_verified=True,
                organization_verified=True,
                deployment_live=True,
                product_activity_verified=True,
                github_repo_count=4,
                github_commit_count=120,
                github_contributor_count=8,
                github_last_activity_at=now - timedelta(hours=2),
                deployments_30d=6,
                last_deployment_at=now - timedelta(hours=3),
                mau=3000,
                dau=600,
                growth_rate_pct=18.5,
                retention_rate_pct=64.0,
                verified_team_count=5,
                milestone_count=3,
                verification_status=SimpleNamespace(value="verified"),
                trust_score=96.0,
                confidence_score=0.96,
                badges=[],
                last_sync_at=now,
            ),
            SimpleNamespace(
                project_id="startup_002",
                email_verified=True,
                phone_verified=False,
                github_connected=False,
                linkedin_connected=True,
                domain_verified=True,
                organization_verified=False,
                deployment_live=False,
                product_activity_verified=False,
                github_repo_count=0,
                github_commit_count=0,
                github_contributor_count=0,
                github_last_activity_at=None,
                deployments_30d=0,
                last_deployment_at=None,
                mau=0,
                dau=0,
                growth_rate_pct=0.0,
                retention_rate_pct=0.0,
                verified_team_count=0,
                milestone_count=0,
                verification_status=SimpleNamespace(value="pending"),
                trust_score=25.0,
                confidence_score=0.25,
                badges=[],
                last_sync_at=now - timedelta(days=3),
            ),
        ],
        "trust_verification_history": [
            SimpleNamespace(
                id="h1",
                verification_id="ver_github_001",
                project_id="startup_001",
                source=SimpleNamespace(value="github"),
                status=SimpleNamespace(value="verified"),
                confidence=0.94,
                metadata_hash="hiddenhash",
                reference_id="hiddenref",
                event_type="trust_verified",
                expires_at=now + timedelta(days=30),
                created_at=now - timedelta(hours=2),
            ),
            SimpleNamespace(
                id="h2",
                verification_id="ver_deployment_001",
                project_id="startup_001",
                source=SimpleNamespace(value="deployment"),
                status=SimpleNamespace(value="verified"),
                confidence=0.96,
                metadata_hash="hiddenhash2",
                reference_id="hiddenref2",
                event_type="trust_verified",
                expires_at=now + timedelta(hours=12),
                created_at=now - timedelta(hours=3),
            ),
        ],
        "trust_badge_snapshots": [],
        "trust_timeline_events": [
            SimpleNamespace(
                id="t1",
                project_id="startup_001",
                event_type="deployment_completed",
                source=SimpleNamespace(value="deployment"),
                visibility="public",
                created_at=now - timedelta(hours=3),
            ),
        ],
        "project_milestones": [
            SimpleNamespace(
                id="m1",
                project_id="startup_001",
                title="MVP Launch",
                is_completed=True,
                completed_at=now - timedelta(days=10),
            ),
        ],
    })


def _assert_no_sensitive_payload(payload: Dict[str, Any]) -> None:
    text = json.dumps(payload, sort_keys=True).lower()
    blocked_terms = [
        "metadata_hash",
        "hiddenhash",
        "reference_id",
        "hiddenref",
        "owner_id",
        "founder_001",
        "private note",
        "raw_payload",
        "oauth",
        "token",
        "source_code",
        "customer_name",
        "customer_email",
        "customer_list",
        "user_email",
        "analytics_event",
        "government",
        "bank",
    ]
    for term in blocked_terms:
        assert term not in text, term


def test_service_rejects_non_investor_context() -> None:
    try:
        InvestorTrustReadService().get_startups(_founder(), _db())
    except PermissionError as exc:
        assert "investor role" in str(exc).lower()
    else:
        raise AssertionError("founder context was allowed")


def test_startup_list_is_current_investor_scoped_and_search_ready() -> None:
    result = InvestorTrustReadService().get_startups(_investor(), _db())

    assert result["privacy"]["metadataOnly"] is True
    assert result["privacy"]["rawPayloadsExposed"] is False
    assert result["watchlistStartupIds"] == ["startup_001"]
    assert [startup["startupId"] for startup in result["startups"]] == ["startup_001", "startup_002"]
    assert result["startups"][0]["watchlistIncluded"] is True
    assert result["startups"][1]["watchlistIncluded"] is False
    assert result["startups"][1]["name"] == "NeuralEdge AI"
    _assert_no_sensitive_payload(result)


def test_selected_dashboard_matches_frontend_contract_without_sensitive_fields() -> None:
    result = InvestorTrustReadService().get_dashboard(_investor(), "startup_001", _db())

    expected_keys = {
        "startup",
        "trustSummary",
        "badges",
        "verificationItems",
        "founderOverview",
        "productDevelopment",
        "productVerification",
        "productActivity",
        "teamOverview",
        "timeline",
        "milestones",
        "verificationSources",
        "riskStatus",
        "continuousVerification",
        "investmentReadiness",
        "evidenceExplorer",
        "investorNotes",
        "privacy",
    }
    assert expected_keys.issubset(result.keys())
    assert result["startup"]["startupId"] == "startup_001"
    assert result["startup"]["watchlistIncluded"] is True
    assert result["trustSummary"]["verificationConfidence"] >= 80
    assert result["verificationItems"][0]["label"] == "Founder Identity"
    assert {item["source"] for item in result["verificationItems"]}.issuperset({"github", "deployment", "product_analytics"})
    assert result["investorNotes"]["note"] == ""
    assert result["privacy"]["sourceCodeExposed"] is False
    assert result["sourceContract"]["metadataHashesExposed"] is False
    _assert_no_sensitive_payload(result)


def test_missing_trust_records_return_no_data_shape() -> None:
    result = InvestorTrustReadService().get_dashboard(_investor(), "startup_missing", FakeSession({}))

    assert result["startup"]["startupId"] == "startup_missing"
    assert result["startup"]["overallStatus"] == "Pending Verification"
    assert result["trustSummary"]["verificationConfidence"] == 0
    assert result["privacy"]["metadataOnly"] is True
    assert result["verificationItems"]
    _assert_no_sensitive_payload(result)


def test_fastapi_routes_are_registered_and_role_guarded() -> None:
    routes = {getattr(route, "path", "") for route in app.routes}
    assert "/api/v1/investor/trust/startups" in routes
    assert "/api/v1/investor/trust/{startup_id}" in routes

    result = asyncio.run(investor_trust_startups(user=_investor(), db=_db()))
    assert result["watchlistStartupIds"] == ["startup_001"]

    detail = asyncio.run(investor_trust_dashboard("startup_001", user=_investor(), db=_db()))
    assert detail["startup"]["startupId"] == "startup_001"

    try:
        asyncio.run(investor_trust_startups(user=_founder(), db=_db()))
    except Exception as exc:  # noqa: BLE001
        assert getattr(exc, "status_code", None) == 403
    else:
        raise AssertionError("founder route access was allowed")


def main() -> int:
    tests = [
        test_service_rejects_non_investor_context,
        test_startup_list_is_current_investor_scoped_and_search_ready,
        test_selected_dashboard_matches_frontend_contract_without_sensitive_fields,
        test_missing_trust_records_return_no_data_shape,
        test_fastapi_routes_are_registered_and_role_guarded,
    ]
    for test in tests:
        try:
            test()
            print(f"PASS {test.__name__}")
        except AssertionError as exc:
            print(f"FAIL {test.__name__}: {exc}")
            return 1
        except Exception as exc:  # noqa: BLE001
            print(f"ERROR {test.__name__}: {type(exc).__name__}: {exc}")
            return 1
    print(f"\nAll {len(tests)} investor Trust read API tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
