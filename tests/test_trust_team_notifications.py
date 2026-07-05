"""
Trust team verification and notification intent tests. Standalone (no pytest dependency): run with
    python3 tests/test_trust_team_notifications.py
Exit 0 = all asserts passed. Uses metadata-only local objects.
"""

from __future__ import annotations

import os
import sys
from typing import Any, Callable, List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("ALLOW_DEMO_AUTH", "true")

from ai_router_core import SubscriptionTier, UserContext, UserRole  # noqa: E402
from integration_guide import TechITAIBrain, TrustVerificationService  # noqa: E402
from main import app  # noqa: E402
from trust_engine_lite import VerificationStatus  # noqa: E402
from trust_team_notifications import (  # noqa: E402
    TrustNotificationPreviewService,
    TrustTeamVerificationService,
)


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
        user_id="u_trust_team",
        role=UserRole.FOUNDER,
        subscription_tier=SubscriptionTier.FREE,
        credits_remaining=10,
        project_id="p_trust_team",
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


def test_team_invitation_keeps_email_metadata_only() -> None:
    invitation = TrustTeamVerificationService().invite(
        {
            "teammate_email": "founder@example.com",
            "role": "cto",
            "pending_invitations": "bad-count",
            "message": "drop this raw invite note",
            "raw_payload": {"email": "founder@example.com"},
            "oauth_token": "drop-token",
        }
    )

    assert invitation["status"] == VerificationStatus.PENDING.value
    assert invitation["email_domain"] == "example.com"
    assert invitation["invitee_ref"].startswith("team_invitee_")
    assert invitation["metadata"]["pending_invitations"] == 1
    assert invitation["raw_email_stored"] is False
    assert invitation["raw_payload_stored"] is False
    assert invitation["hr_data_stored"] is False
    assert invitation["notification_intent"]["investor_visible"] is False
    assert invitation["notification_intent"]["raw_payload_stored"] is False
    assert "message" in invitation["dropped_fields"]
    assert "raw_payload" in invitation["dropped_fields"]
    assert "oauth_token" in invitation["dropped_fields"]
    assert "founder@example.com" not in str(invitation)


def test_service_invitation_is_not_persisted_before_teammate_verifies() -> None:
    result = _service().invite_team_member(
        _user(),
        {
            "teammate_email": "cofounder@example.com",
            "teammate_role": "engineering",
            "contact_list": ["drop@example.com"],
        },
        db=FakeSession(),
    )

    assert result["verification"]["status"] == VerificationStatus.PENDING.value
    assert result["verification"]["persisted"] is False
    assert result["privacy"]["metadata_only"] is True
    assert result["privacy"]["investor_visible"] is False
    assert "cofounder@example.com" not in str(result)
    assert "contact_list" in result["invitation"]["dropped_fields"]


def test_service_team_verify_persists_metadata_only_profile_update() -> None:
    db = FakeSession()
    result = _service().verify_team_member(
        _user(),
        {
            "teammate_email": "verified@example.com",
            "email_verified": True,
            "github_connected": True,
            "verified_team_count": 2,
            "pending_invitations": 1,
            "raw_payload": {"email": "verified@example.com"},
            "hr_record": "drop-me",
        },
        db=db,
    )

    added_names = [row.__class__.__name__ for row in db.added]
    assert result["team"]["verification_status"] == VerificationStatus.VERIFIED.value
    assert result["team"]["metadata"]["email_domain"] == "example.com"
    assert result["team"]["raw_email_stored"] is False
    assert result["team"]["raw_payload_stored"] is False
    assert result["verification"]["source"] == "team"
    assert result["verification"]["status"] == VerificationStatus.VERIFIED.value
    assert result["verification"]["persisted"] is True
    assert db.commits == 1
    assert db.profile.verified_team_count == 2
    assert "TrustVerificationHistory" in added_names
    assert result["notification_intent"]["founder_visible"] is True
    assert result["notification_intent"]["investor_visible"] is False
    assert "raw_payload" in result["team"]["dropped_fields"]
    assert "hr_record" in result["team"]["dropped_fields"]
    assert "verified@example.com" not in str(result)


def test_notification_preview_filters_internal_identifiers_and_raw_payloads() -> None:
    preview = TrustNotificationPreviewService().preview(
        [
            {
                "source": "github",
                "provider": "github",
                "status": "expired",
                "message": "GitHub trust check expired.",
                "user_id": "internal-user",
                "subject_id": "internal-subject",
                "email": "founder@example.com",
                "metadata_hash": "drop",
                "raw_payload": {"private": True},
            },
            "not-an-event",
        ]
    )

    assert preview["summary"]["events_seen"] == 1
    assert preview["summary"]["notifications_prepared"] == 1
    assert preview["notification_intents"][0]["notification_type"] == "trust_verification_expired"
    assert preview["notification_intents"][0]["severity"] == "critical"
    assert preview["notification_intents"][0]["founder_visible"] is True
    assert preview["notification_intents"][0]["investor_visible"] is False
    assert preview["privacy"]["delivery_executed"] is False
    assert preview["privacy"]["raw_payload_stored"] is False
    assert "user_id" in preview["dropped_fields"]
    assert "subject_id" in preview["dropped_fields"]
    assert "email" in preview["dropped_fields"]
    assert "raw_payload" in preview["dropped_fields"]
    assert "founder@example.com" not in str(preview)


def test_service_notification_preview_and_routes_are_registered() -> None:
    result = _service().preview_notifications(
        _user(),
        {
            "events": [
                {"source": "domain", "status": "failed", "reference_id": "drop-ref"},
                {"source": "team", "status": "verified", "message": "Team verified."},
            ]
        },
    )
    routes = {getattr(route, "path", "") for route in app.routes}

    assert result["summary"]["events_seen"] == 2
    assert result["summary"]["notifications_prepared"] == 2
    assert result["owner_ids_exposed_to_investors"] is False
    assert "user_id" not in result
    assert "project_id" not in result
    assert "reference_id" in result["dropped_fields"]
    assert "/api/v1/trust/team/invite" in routes
    assert "/api/v1/trust/team/verify" in routes
    assert "/api/v1/trust/notifications/preview" in routes


def main() -> int:
    tests: List[Callable[[], None]] = [
        test_team_invitation_keeps_email_metadata_only,
        test_service_invitation_is_not_persisted_before_teammate_verifies,
        test_service_team_verify_persists_metadata_only_profile_update,
        test_notification_preview_filters_internal_identifiers_and_raw_payloads,
        test_service_notification_preview_and_routes_are_registered,
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
    print(f"\nAll {len(tests)} Trust team notification tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
