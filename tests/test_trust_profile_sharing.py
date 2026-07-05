"""
Trust milestone review and profile sharing tests. Standalone (no pytest dependency): run with
    python3 tests/test_trust_profile_sharing.py
Exit 0 = all asserts passed. Uses metadata-only local objects.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
from typing import Any, Callable, List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("ALLOW_DEMO_AUTH", "true")

from ai_router_core import SubscriptionTier, UserContext, UserRole  # noqa: E402
from integration_guide import TechITAIBrain, TrustVerificationService  # noqa: E402
from main import app  # noqa: E402
from trust_engine_lite import VerificationStatus  # noqa: E402
from trust_profile_sharing import TrustMilestoneReviewService, TrustProfileSharingService  # noqa: E402


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
    def __init__(self) -> None:
        self.profile: Any | None = None
        self.added: List[Any] = []
        self.commits = 0
        self.rollbacks = 0

    def query(self, model: Any) -> FakeQuery:
        table = getattr(model, "__tablename__", "")
        if table == "trust_profiles":
            return FakeQuery([self.profile] if self.profile else [])
        if table == "trust_verification_history":
            return FakeQuery([])
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
        user_id="u_trust_share",
        role=UserRole.FOUNDER,
        subscription_tier=SubscriptionTier.FREE,
        credits_remaining=10,
        project_id="p_trust_share",
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


def test_milestone_review_keeps_public_evidence_metadata_only() -> None:
    review = TrustMilestoneReviewService().review(
        {
            "milestone": "Beta launched",
            "evidence_url": "https://example.com/beta",
            "approval_status": "approved",
            "approved_by": "admin-1",
            "confidence": 0.97,
            "screenshot_blob": "drop-me",
            "raw_payload": {"drop": True},
            "attachment_file": "drop-me",
        }
    )

    assert review["approval_status"] == "approved"
    assert review["metadata"]["verified"] is True
    assert review["timeline_event"]["visibility"] == "public"
    assert review["raw_payload_stored"] is False
    assert review["uploaded_file_stored"] is False
    assert "screenshot_blob" in review["dropped_fields"]
    assert "raw_payload" in review["dropped_fields"]
    assert "attachment_file" in review["dropped_fields"]
    assert "drop-me" not in review["metadata_hash"]


def test_milestone_review_rejection_is_private_and_failed() -> None:
    result = _service().review_milestone(
        _user(),
        {
            "milestone": "Patent filed",
            "evidence_url": "https://example.com/patent",
            "approval_status": "rejected",
            "approved_by": "admin-1",
            "reason_code": "evidence_not_confirmed",
        },
        db=None,
    )

    assert result["review"]["approval_status"] == "rejected"
    assert result["verification"]["status"] == VerificationStatus.FAILED.value
    assert result["timeline_event"]["visibility"] == "private"
    assert result["investor_visible"] is False
    assert result["privacy"]["uploaded_file_stored"] is False


def test_approved_milestone_review_appends_metadata_only_rows() -> None:
    db = FakeSession()
    result = _service().review_milestone(
        _user(),
        {
            "milestone": "First paying customer",
            "evidence_url": "https://example.com/customer",
            "approval_status": "approved",
            "approved_by": "admin-1",
            "screenshot_blob": "drop-me",
        },
        db=db,
    )

    added_names = [row.__class__.__name__ for row in db.added]
    assert result["verification"]["persisted"] is True
    assert result["verification"]["status"] == VerificationStatus.VERIFIED.value
    assert result["investor_visible"] is True
    assert db.commits == 1
    assert "TrustVerificationHistory" in added_names
    assert "TrustTimelineEvent" in added_names
    assert db.profile.milestone_count == 1
    assert "screenshot_blob" in result["review"]["dropped_fields"]


def test_share_profile_requires_opt_in_and_filters_internal_fields() -> None:
    profile = {
        "user_id": "internal-user",
        "project_id": "internal-project",
        "email": "drop@example.com",
        "verification_status": "verified",
        "trust_score": 72.5,
        "tier": "Verified",
        "confidence_score": 0.725,
        "signals": ["email_verified", "domain_verified"],
        "breakdown": {"email_verified": 10, "user_email": "drop@example.com"},
        "metadata_hash": "drop",
    }
    badges = [
        {"badge_type": "verified_domain", "label": "Verified Domain", "source": "domain", "status": "verified", "active": True},
        {"badge_type": "product_live", "label": "Product Live", "source": "deployment", "status": "expired", "active": False},
        {
            "badge_type": "team_verified",
            "label": "Team Verified",
            "source": "team",
            "status": "verified",
            "active": True,
            "expires_at": (datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=1)).isoformat(),
        },
    ]
    history = [
        {"source": "domain", "status": "verified", "event_type": "domain_verified", "reference_id": "drop"},
        {"source": "github", "status": "failed", "event_type": "github_failed"},
    ]

    disabled = TrustProfileSharingService().build(
        profile=profile,
        badges=badges,
        history=history,
        settings={"share_enabled": False},
    )
    enabled = TrustProfileSharingService().build(
        profile=profile,
        badges=badges,
        history=history,
        settings={"share_enabled": True, "expiry_days": 10},
    )

    assert disabled["investor_visible"] is False
    assert disabled["profile"] == {}
    assert disabled["badges"] == []

    assert enabled["investor_visible"] is True
    assert enabled["profile"]["trust_score"] == 72.5
    assert "user_id" not in enabled["profile"]
    assert "project_id" not in enabled["profile"]
    assert "email" not in enabled["profile"]
    assert "metadata_hash" not in enabled["profile"]
    assert "user_email" not in enabled["profile"]["breakdown"]
    assert len(enabled["badges"]) == 1
    assert enabled["badges"][0]["label"] == "Verified Domain"
    assert len(enabled["timeline"]) == 1
    assert "reference_id" not in enabled["timeline"][0]
    assert enabled["privacy"]["internal_ids_exposed"] is False


def test_service_share_profile_preview_and_routes_are_registered() -> None:
    shared = _service().build_share_profile(
        _user(),
        {
            "settings": {"share_enabled": True},
            "profile": {
                "user_id": "internal-user",
                "verification_status": "verified",
                "trust_score": 42.0,
                "tier": "Partially Verified",
            },
            "badges": [],
            "history": [],
        },
        db=None,
    )
    routes = {getattr(route, "path", "") for route in app.routes}

    assert shared["investor_visible"] is True
    assert shared["owner_ids_exposed_to_investors"] is False
    assert "owner_user_id" not in shared
    assert "owner_project_id" not in shared
    assert "user_id" not in shared["profile"]
    assert "/api/v1/trust/share-profile/preview" in routes
    assert "/api/v1/trust/milestone/review" in routes


def main() -> int:
    tests: List[Callable[[], None]] = [
        test_milestone_review_keeps_public_evidence_metadata_only,
        test_milestone_review_rejection_is_private_and_failed,
        test_approved_milestone_review_appends_metadata_only_rows,
        test_share_profile_requires_opt_in_and_filters_internal_fields,
        test_service_share_profile_preview_and_routes_are_registered,
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
    print(f"\nAll {len(tests)} Trust profile sharing tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
