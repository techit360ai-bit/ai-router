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
from main import (  # noqa: E402
    app,
    investor_trust_dashboard,
    investor_trust_notes,
    investor_trust_search,
    investor_trust_startups,
)
from trust_investor_read_model import InvestorTrustReadService, InvestorTrustStartupNotFound  # noqa: E402


class FakeQuery:
    def __init__(self, rows: List[Any] | None = None) -> None:
        self.rows = rows or []

    def filter(self, *_args: Any, **_kwargs: Any) -> "FakeQuery":
        return self

    def order_by(self, *_args: Any, **_kwargs: Any) -> "FakeQuery":
        return self

    def limit(self, limit: int) -> "FakeQuery":
        return FakeQuery(self.rows[:limit])

    def first(self) -> Any:
        return self.rows[0] if self.rows else None

    def all(self) -> List[Any]:
        return self.rows


class FakeSession:
    def __init__(self, rows_by_table: Dict[str, List[Any]]) -> None:
        self.rows_by_table = rows_by_table
        self.added: List[Any] = []
        self.deleted: List[Any] = []
        self.commits = 0
        self.rollbacks = 0

    def query(self, model: Any) -> FakeQuery:
        return FakeQuery(self.rows_by_table.get(getattr(model, "__tablename__", ""), []))

    def add(self, row: Any) -> None:
        table = getattr(row, "__tablename__", "")
        self.rows_by_table.setdefault(table, [])
        if row not in self.rows_by_table[table]:
            self.rows_by_table[table].append(row)
        self.added.append(row)

    def delete(self, row: Any) -> None:
        table = getattr(row, "__tablename__", "")
        if row in self.rows_by_table.get(table, []):
            self.rows_by_table[table].remove(row)
        self.deleted.append(row)

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


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


def _other_investor() -> UserContext:
    return UserContext(
        user_id="other_investor",
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
        "investor_trust_notes": [],
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


def test_directory_search_finds_non_watchlist_and_returns_not_found_state() -> None:
    service = InvestorTrustReadService()

    result = service.search_startups(_investor(), "NeuralEdge", _db())

    assert result["query"] == "NeuralEdge"
    assert [startup["startupId"] for startup in result["startups"]] == ["startup_002"]
    assert result["startups"][0]["watchlistIncluded"] is False
    assert result["notFound"] is None
    _assert_no_sensitive_payload(result)

    missing = service.search_startups(_investor(), "No Such Verified Startup", _db())

    assert missing["startups"] == []
    assert missing["notFound"]["state"] == "not_found"
    assert missing["notFound"]["requestAccessAllowed"] is True
    assert missing["notFound"]["addToWatchlistAllowed"] is False
    assert missing["privacy"]["investorNotesPrivate"] is True


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


def test_missing_startup_returns_explicit_not_found_state() -> None:
    try:
        InvestorTrustReadService().get_dashboard(_investor(), "startup_missing", FakeSession({}))
    except InvestorTrustStartupNotFound as exc:
        state = exc.state
    else:
        raise AssertionError("missing startup returned a dashboard payload")

    assert state["state"] == "not_found"
    assert state["startupId"] == "startup_missing"
    assert state["requestAccessAllowed"] is True
    assert state["addToWatchlistAllowed"] is False
    assert state["watchlistIncluded"] is False
    assert state["privacy"]["metadataOnly"] is True


def test_private_notes_persist_by_investor_and_sync_bookmark_watchlist() -> None:
    db = _db()
    service = InvestorTrustReadService()
    payload = {
        "note": "Partner review scheduled after diligence.",
        "internalRating": "priority",
        "followUpReminder": "Review on 2026-07-15",
        "checklist": [
            {"item": "Review verification sources", "done": True},
            {"item": "Check milestone evidence", "done": False},
        ],
        "bookmarked": True,
    }

    saved = service.save_notes(_investor(), "startup_002", payload, db)

    assert saved["ok"] is True
    assert saved["investorNotes"]["note"] == "Partner review scheduled after diligence."
    assert saved["investorNotes"]["internalRating"] == "priority"
    assert saved["investorNotes"]["bookmarked"] is True
    assert db.commits == 1
    assert any(
        row.investor_id == "investor_001" and row.project_id == "startup_002"
        for row in db.rows_by_table["investor_trust_notes"]
    )
    assert any(
        row.investor_id == "investor_001" and row.project_id == "startup_002"
        for row in db.rows_by_table["investor_watchlist"]
    )

    dashboard = service.get_dashboard(_investor(), "startup_002", db)
    assert dashboard["investorNotes"]["note"] == "Partner review scheduled after diligence."
    assert dashboard["startup"]["watchlistIncluded"] is True

    other_dashboard = service.get_dashboard(_other_investor(), "startup_002", db)
    assert other_dashboard["investorNotes"]["note"] == ""
    assert "Partner review scheduled" not in json.dumps(other_dashboard)
    _assert_no_sensitive_payload(other_dashboard)

    updated = service.save_notes(
        _investor(),
        "startup_002",
        {**payload, "note": "Investment committee passed.", "internalRating": "pass", "bookmarked": False},
        db,
    )

    assert updated["investorNotes"]["note"] == "Investment committee passed."
    assert updated["investorNotes"]["internalRating"] == "pass"
    assert updated["investorNotes"]["bookmarked"] is False
    assert len([
        row for row in db.rows_by_table["investor_trust_notes"]
        if row.investor_id == "investor_001" and row.project_id == "startup_002"
    ]) == 1
    assert not any(
        row.investor_id == "investor_001" and row.project_id == "startup_002"
        for row in db.rows_by_table["investor_watchlist"]
    )


def test_private_notes_cannot_be_read_or_mutated_by_other_roles() -> None:
    db = _db()
    service = InvestorTrustReadService()
    payload = {
        "note": "Internal investor thesis only.",
        "internalRating": "watch",
        "followUpReminder": "",
        "checklist": [],
        "bookmarked": False,
    }

    service.save_notes(_investor(), "startup_001", payload, db)
    service.save_notes(_other_investor(), "startup_001", {**payload, "note": "Other investor memo."}, db)

    own = service.get_dashboard(_investor(), "startup_001", db)
    other = service.get_dashboard(_other_investor(), "startup_001", db)

    assert own["investorNotes"]["note"] == "Internal investor thesis only."
    assert other["investorNotes"]["note"] == "Other investor memo."
    assert "Other investor memo" not in json.dumps(own)
    assert "Internal investor thesis" not in json.dumps(other)

    try:
        service.save_notes(_founder(), "startup_001", payload, db)
    except PermissionError as exc:
        assert "investor role" in str(exc).lower()
    else:
        raise AssertionError("founder note mutation was allowed")


def test_fastapi_routes_are_registered_and_role_guarded() -> None:
    route_paths = [getattr(route, "path", "") for route in app.routes]
    routes = set(route_paths)
    assert "/api/v1/investor/trust/startups" in routes
    assert "/api/v1/investor/trust/search" in routes
    assert "/api/v1/investor/trust/{startup_id}" in routes
    assert "/api/v1/investor/trust/{startup_id}/notes" in routes
    assert route_paths.index("/api/v1/investor/trust/search") < route_paths.index("/api/v1/investor/trust/{startup_id}")

    result = asyncio.run(investor_trust_startups(user=_investor(), db=_db()))
    assert result["watchlistStartupIds"] == ["startup_001"]

    search = asyncio.run(investor_trust_search(query="NeuralEdge", user=_investor(), db=_db()))
    assert [startup["startupId"] for startup in search["startups"]] == ["startup_002"]

    detail = asyncio.run(investor_trust_dashboard("startup_001", user=_investor(), db=_db()))
    assert detail["startup"]["startupId"] == "startup_001"

    db = _db()
    saved = asyncio.run(investor_trust_notes(
        "startup_002",
        notes={
            "note": "Route-level note.",
            "internalRating": "watch",
            "followUpReminder": "",
            "checklist": [],
            "bookmarked": True,
        },
        user=_investor(),
        db=db,
    ))
    assert saved["investorNotes"]["note"] == "Route-level note."

    try:
        asyncio.run(investor_trust_dashboard("startup_missing", user=_investor(), db=_db()))
    except Exception as exc:  # noqa: BLE001
        assert getattr(exc, "status_code", None) == 404
        assert getattr(exc, "detail", {}).get("state") == "not_found"
    else:
        raise AssertionError("missing startup route did not return 404")

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
        test_directory_search_finds_non_watchlist_and_returns_not_found_state,
        test_selected_dashboard_matches_frontend_contract_without_sensitive_fields,
        test_missing_startup_returns_explicit_not_found_state,
        test_private_notes_persist_by_investor_and_sync_bookmark_watchlist,
        test_private_notes_cannot_be_read_or_mutated_by_other_roles,
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
