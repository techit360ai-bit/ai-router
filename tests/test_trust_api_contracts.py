"""
Trust API contract tests. Standalone (no pytest dependency): run with
    python3 tests/test_trust_api_contracts.py
Exit 0 = all asserts passed. Uses fake sessions only.
"""

from __future__ import annotations

import os
import sys
from types import SimpleNamespace
from typing import Any, Dict, List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("ALLOW_DEMO_AUTH", "true")

from ai_router_core import SubscriptionTier, UserContext, UserRole  # noqa: E402
from integration_guide import TechITAIBrain, TrustVerificationService  # noqa: E402
from main import app  # noqa: E402
from trust_engine_lite import VerificationSource  # noqa: E402


class FakeQuery:
    def __init__(self, rows: List[Any] | None = None) -> None:
        self.rows = rows or []

    def filter(self, *_args: Any, **_kwargs: Any) -> "FakeQuery":
        return self

    def order_by(self, *_args: Any, **_kwargs: Any) -> "FakeQuery":
        return self

    def limit(self, _limit: int) -> "FakeQuery":
        return self

    def first(self) -> Any:
        return self.rows[0] if self.rows else None

    def all(self) -> List[Any]:
        return self.rows


class FakeSession:
    def __init__(self, profile: Any | None = None, history: List[Any] | None = None) -> None:
        self.profile = profile
        self.history = history or []
        self.added: List[Any] = []
        self.commits = 0
        self.rollbacks = 0

    def query(self, model: Any) -> FakeQuery:
        table = getattr(model, "__tablename__", "")
        if table == "trust_profiles":
            return FakeQuery([self.profile] if self.profile else [])
        if table == "trust_verification_history":
            return FakeQuery(self.history)
        return FakeQuery([])

    def add(self, row: Any) -> None:
        self.added.append(row)
        if getattr(row, "__tablename__", "") == "trust_profiles" or row.__class__.__name__ == "TrustProfile":
            self.profile = row

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


def _user() -> UserContext:
    return UserContext(
        user_id="u_trust_api",
        role=UserRole.FOUNDER,
        subscription_tier=SubscriptionTier.FREE,
        credits_remaining=10,
        project_id="p_trust_api",
        project_stage="mvp",
        industry="saas",
        tech_stack=[],
        past_feedback=[],
        training_progress={},
        time_logged_today=0,
        tasks_completed_week=0,
    )


def _service() -> TrustVerificationService:
    return TrustVerificationService(TechITAIBrain())


def test_verify_source_sanitizes_raw_payload_and_hashes_metadata_only() -> None:
    result = _service().verify_source(
        _user(),
        "github",
        {
            "repo_count": 3,
            "commit_count": 44,
            "contributor_count": 2,
            "last_activity": "2026-07-04T10:00:00",
            "verified": True,
            "confidence": 0.9,
            "oauth_token": "should-drop",
            "raw_payload": {"private": "should-drop"},
            "repository_contents": "should-drop",
        },
        db=None,
    )

    assert result["source"] == VerificationSource.GITHUB.value
    assert result["status"] == "verified"
    assert result["raw_payload_stored"] is False
    assert result["metadata_stored"] == {
        "repo_count": 3,
        "commit_count": 44,
        "contributor_count": 2,
        "last_activity": "2026-07-04T10:00:00",
        "verified": True,
        "confidence": 0.9,
        "github_repo_count": 3,
        "github_commit_count": 44,
        "github_contributor_count": 2,
        "github_last_activity_at": "2026-07-04T10:00:00",
    }
    assert "oauth_token" in result["dropped_fields"]
    assert "raw_payload" in result["dropped_fields"]
    assert "repository_contents" in result["dropped_fields"]
    assert len(result["metadata_hash"]) == 64
    assert "should-drop" not in result["metadata_hash"]


def test_verify_source_persists_append_only_rows_with_fake_session() -> None:
    db = FakeSession()
    result = _service().verify_source(
        _user(),
        "email",
        {"verified": True, "confidence": 1.0, "email": "drop@example.com"},
        db=db,
    )

    added_names = [row.__class__.__name__ for row in db.added]
    assert result["persisted"] is True
    assert db.commits == 1
    assert "TrustProfile" in added_names
    assert "TrustVerificationHistory" in added_names
    assert "TrustTimelineEvent" in added_names
    assert "TrustBadgeSnapshot" in added_names
    assert db.profile.email_verified is True
    assert db.profile.trust_score == 10.0
    assert "email" in result["dropped_fields"]


def test_disconnect_and_refresh_contracts_append_statuses() -> None:
    service = _service()

    disconnect = service.disconnect_source(_user(), "github", db=None)
    assert disconnect["status"] == "disconnected"
    assert disconnect["confidence"] == 0.0

    refresh = service.refresh_source(_user(), "domain", {"domain": "example.com"}, db=None)
    assert refresh["status"] == "pending"
    assert refresh["source"] == "domain"
    assert refresh["metadata_stored"] == {"domain": "example.com"}


def test_profile_badges_and_history_contracts_are_safe_without_db() -> None:
    service = _service()

    profile = service.get_profile(_user(), db=None)
    badges = service.get_badges(_user(), db=None)
    history = service.get_history(_user(), db=None)

    assert profile["privacy"]["metadata_only"] is True
    assert profile["privacy"]["raw_payload_stored"] is False
    assert badges["badges"] == []
    assert history["append_only"] is True
    assert history["history"] == []


def test_milestone_submission_prefers_evidence_url_metadata() -> None:
    result = _service().submit_milestone(
        _user(),
        {
            "title": "MVP launched",
            "evidence_url": "https://example.com/launch",
            "screenshot_blob": "should-drop",
            "approved_by": {"admin_id": "should-drop"},
            "approval_status": "pending",
        },
        db=None,
    )

    assert result["source"] == "milestone"
    assert result["status"] == "pending"
    assert result["metadata_stored"]["evidence_url"] == "https://example.com/launch"
    assert "screenshot_blob" in result["dropped_fields"]
    assert "approved_by" in result["dropped_fields"]
    assert "approved_by" not in result["metadata_stored"]
    assert result["review_status"] == "pending"


def test_unsupported_source_is_rejected() -> None:
    try:
        _service().verify_source(_user(), "banking", {}, db=None)
    except ValueError as exc:
        assert "Unsupported trust verification source" in str(exc)
    else:
        raise AssertionError("unsupported source did not raise")


def test_fastapi_trust_routes_are_registered() -> None:
    routes = {getattr(route, "path", "") for route in app.routes}
    expected = {
        "/api/v1/trust/profile",
        "/api/v1/trust/badges",
        "/api/v1/trust/history",
        "/api/v1/trust/share-profile/preview",
        "/api/v1/trust/integrations",
        "/api/v1/trust/verify/{source}",
        "/api/v1/trust/adapters/{provider}/verify",
        "/api/v1/trust/disconnect/{source}",
        "/api/v1/trust/refresh/{source}",
        "/api/v1/trust/refresh-plan",
        "/api/v1/trust/continuous-verification/run",
        "/api/v1/trust/milestone",
        "/api/v1/trust/milestone/review",
        "/api/v1/trust/team/invite",
        "/api/v1/trust/team/verify",
        "/api/v1/trust/notifications/preview",
        "/api/v1/investor/trust/startups",
        "/api/v1/investor/trust/{startup_id}",
    }
    assert expected.issubset(routes)


def main() -> int:
    tests = [
        test_verify_source_sanitizes_raw_payload_and_hashes_metadata_only,
        test_verify_source_persists_append_only_rows_with_fake_session,
        test_disconnect_and_refresh_contracts_append_statuses,
        test_profile_badges_and_history_contracts_are_safe_without_db,
        test_milestone_submission_prefers_evidence_url_metadata,
        test_unsupported_source_is_rejected,
        test_fastapi_trust_routes_are_registered,
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
    print(f"\nAll {len(tests)} Trust API contract tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
