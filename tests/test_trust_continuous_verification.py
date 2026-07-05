"""
Trust continuous verification contract tests. Standalone (no pytest dependency): run with
    python3 tests/test_trust_continuous_verification.py
Exit 0 = all asserts passed. Uses local metadata only; no provider network calls.
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
from trust_continuous_verification import TrustContinuousVerificationRunner  # noqa: E402
from trust_engine_lite import VerificationSource, VerificationStatus  # noqa: E402


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
        user_id="u_trust_runner",
        role=UserRole.FOUNDER,
        subscription_tier=SubscriptionTier.FREE,
        credits_remaining=10,
        project_id="p_trust_runner",
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


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def test_runner_prepares_notifications_and_actions_without_provider_calls() -> None:
    now = datetime(2026, 7, 5, 12, 0, 0)
    result = TrustContinuousVerificationRunner().prepare(
        user_id="u1",
        project_id="p1",
        connections=[
            {
                "source": "github",
                "provider": "github",
                "status": "verified",
                "connected": True,
                "last_sync_at": (now - timedelta(hours=23)).isoformat(),
            },
            {
                "source": "deployment",
                "provider": "vercel",
                "status": "verified",
                "connected": True,
                "last_sync_at": (now - timedelta(hours=14)).isoformat(),
            },
            {
                "source": "product_analytics",
                "provider": "firebase",
                "status": "disconnected",
                "connected": False,
                "last_sync_at": (now - timedelta(days=2)).isoformat(),
            },
        ],
        now=now,
    )

    assert result["summary"]["connections_seen"] == 3
    assert result["summary"]["actions_prepared"] == 1
    assert result["summary"]["notifications_prepared"] == 2
    assert result["privacy"]["metadata_only"] is True
    assert result["privacy"]["provider_calls_executed"] is False
    assert result["privacy"]["investor_notifications"] is False

    action = result["verification_actions"][0]
    assert action["source"] == VerificationSource.DEPLOYMENT.value
    assert action["provider"] == "vercel"
    assert action["status"] == VerificationStatus.EXPIRED.value
    assert action["action_type"] == "mark_expired"
    assert action["metadata"] == {"verified": False, "confidence": 0.5}
    assert action["raw_payload_stored"] is False

    notification_types = {n["notification_type"] for n in result["notification_intents"]}
    assert notification_types == {"trust_verification_expired", "trust_integration_disconnected"}
    for notification in result["notification_intents"]:
        assert notification["raw_payload_stored"] is False
        assert notification["investor_visible"] is False
        assert len(notification["metadata_hash"]) == 64


def test_runner_uses_adapter_payload_when_scheduler_metadata_is_available() -> None:
    now = datetime(2026, 7, 5, 12, 0, 0)
    result = TrustContinuousVerificationRunner().prepare(
        user_id="u1",
        project_id="p1",
        connections=[
            {
                "source": "github",
                "provider": "github",
                "status": "verified",
                "connected": True,
                "last_sync_at": (now - timedelta(hours=25)).isoformat(),
            },
        ],
        adapter_payloads={
            "github": {
                "repo_count": 6,
                "commit_count": 120,
                "contributor_count": 3,
                "oauth_token": "drop-me",
                "source_code": "drop-me",
            }
        },
        now=now,
    )

    assert result["summary"]["actions_prepared"] == 1
    action = result["verification_actions"][0]
    assert action["action_type"] == "adapter_metadata"
    assert action["status"] == VerificationStatus.VERIFIED.value
    assert action["metadata"]["github_repo_count"] == 6
    assert action["metadata"]["github_commit_count"] == 120
    assert action["metadata"]["verified"] is True
    assert "oauth_token" in action["dropped_fields"]
    assert "source_code" in action["dropped_fields"]
    assert action["tokens_stored"] is False


def test_service_preview_does_not_persist_actions() -> None:
    result = _service().run_continuous_verification(
        _user(),
        {
            "execute": False,
            "connections": [
                {
                    "source": "deployment",
                    "provider": "vercel",
                    "status": "verified",
                    "connected": True,
                    "last_sync_at": (_utcnow() - timedelta(hours=14)).isoformat(),
                }
            ],
        },
        db=None,
    )

    assert result["execute"] is False
    assert result["executed_results"] == []
    assert result["summary"]["actions_prepared"] == 1
    assert result["privacy"]["notifications_are_intents_only"] is True
    assert result["privacy"]["raw_payload_stored"] is False


def test_service_execute_appends_metadata_only_rows_with_fake_session() -> None:
    db = FakeSession()
    result = _service().run_continuous_verification(
        _user(),
        {
            "execute": True,
            "connections": [
                {
                    "source": "deployment",
                    "provider": "vercel",
                    "status": "verified",
                    "connected": True,
                    "last_sync_at": (_utcnow() - timedelta(hours=14)).isoformat(),
                },
                {
                    "source": "github",
                    "provider": "github",
                    "status": "verified",
                    "connected": True,
                    "last_sync_at": (_utcnow() - timedelta(hours=25)).isoformat(),
                },
            ],
            "adapter_payloads": {
                "github": {
                    "repo_count": 4,
                    "commit_count": 44,
                    "raw_payload": {"drop": True},
                    "oauth_token": "drop-me",
                }
            },
        },
        db=db,
    )

    added_names = [row.__class__.__name__ for row in db.added]
    assert result["execute"] is True
    assert len(result["executed_results"]) == 2
    assert db.commits == 2
    assert "TrustProfile" in added_names
    assert added_names.count("TrustVerificationHistory") == 2
    assert all(row["raw_payload_stored"] is False for row in result["executed_results"])
    by_source = {row["source"]: row for row in result["executed_results"]}
    assert by_source["deployment"]["recorded_status"] == VerificationStatus.EXPIRED.value
    assert by_source["github"]["recorded_status"] == VerificationStatus.VERIFIED.value


def test_continuous_verification_route_is_registered() -> None:
    routes = {getattr(route, "path", "") for route in app.routes}
    assert "/api/v1/trust/continuous-verification/run" in routes


def main() -> int:
    tests: List[Callable[[], None]] = [
        test_runner_prepares_notifications_and_actions_without_provider_calls,
        test_runner_uses_adapter_payload_when_scheduler_metadata_is_available,
        test_service_preview_does_not_persist_actions,
        test_service_execute_appends_metadata_only_rows_with_fake_session,
        test_continuous_verification_route_is_registered,
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
    print(f"\nAll {len(tests)} Trust continuous verification tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
