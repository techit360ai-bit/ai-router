"""
Trust continuous verification worker contract tests. Standalone (no pytest dependency): run with
    python3 tests/test_trust_continuous_verification_workers.py
Exit 0 = all asserts passed. Uses fake sessions only; no provider network calls.
"""

from __future__ import annotations

import os
import sys
import types
from types import SimpleNamespace
from typing import Any, Callable, List

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("ALLOW_DEMO_AUTH", "true")

try:
    import celery as _celery_dependency  # noqa: F401
except ModuleNotFoundError:
    class FakeCeleryConfig(dict):
        def __getattr__(self, key: str) -> Any:
            return self[key]

        def __setattr__(self, key: str, value: Any) -> None:
            self[key] = value

    class FakeCelery:
        def __init__(self, *_args: Any, **_kwargs: Any) -> None:
            self.conf = FakeCeleryConfig()

        def task(self, *_args: Any, **_kwargs: Any) -> Callable[[Callable[..., Any]], Callable[..., Any]]:
            def decorator(func: Callable[..., Any]) -> Callable[..., Any]:
                return func

            return decorator

    celery_module = types.ModuleType("celery")
    celery_module.Celery = FakeCelery
    schedules_module = types.ModuleType("celery.schedules")
    schedules_module.crontab = lambda **kwargs: {"crontab": kwargs}
    sys.modules["celery"] = celery_module
    sys.modules["celery.schedules"] = schedules_module

from integration_guide import TechITAIBrain, TrustVerificationService  # noqa: E402
from trust_engine_lite import VerificationStatus  # noqa: E402
from workers.workers import (  # noqa: E402
    _run_trust_continuous_verification_batch,
    _run_trust_continuous_verification_batches,
    _trust_connection_batches_from_rows,
    celery,
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
        return FakeQuery([])

    def add(self, row: Any) -> None:
        self.added.append(row)
        if getattr(row, "__tablename__", "") == "trust_profiles" or row.__class__.__name__ == "TrustProfile":
            self.profile = row

    def commit(self) -> None:
        self.commits += 1

    def rollback(self) -> None:
        self.rollbacks += 1


def _service() -> TrustVerificationService:
    return TrustVerificationService(TechITAIBrain())


def _expired_badge_batch() -> dict[str, Any]:
    return {
        "user_id": "u_trust_worker",
        "project_id": "p_trust_worker",
        "role": "founder",
        "subscription_tier": "free",
        "project_stage": "mvp",
        "industry": "saas",
        "connections": [
            {
                "source": "deployment",
                "provider": "vercel",
                "status": "verified",
                "connected": True,
                "last_sync_at": "2020-01-01T00:00:00",
                "expires_at": "2020-01-01T12:00:00",
                "active_badges": [
                    {
                        "badge_type": "product_live",
                        "label": "Product Live",
                        "expires_at": "2020-01-31T00:00:00",
                    }
                ],
            }
        ],
    }


def _expired_github_batch() -> dict[str, Any]:
    return {
        "user_id": "u_trust_worker",
        "project_id": "p_trust_worker",
        "role": "founder",
        "subscription_tier": "free",
        "project_stage": "mvp",
        "industry": "saas",
        "connections": [
            {
                "source": "github",
                "provider": "github",
                "status": "verified",
                "connected": True,
                "last_sync_at": "2020-01-01T00:00:00",
                "expires_at": "2020-01-02T00:00:00",
            }
        ],
    }


def test_worker_groups_due_trust_rows_with_badge_refs() -> None:
    rows = [
        SimpleNamespace(
            user_id="u1",
            project_id="p1",
            source="DEPLOYMENT",
            provider="VERCEL",
            status="VERIFIED",
            confidence=0.8,
            last_sync_at="2020-01-01T00:00:00",
            expires_at="2020-01-01T12:00:00",
            role="FOUNDER",
            subscription_tier="FREE",
            project_stage="MVP",
            industry="saas",
            active_badges=[{"badge_type": "product_live", "label": "Product Live"}],
        )
    ]

    batches = _trust_connection_batches_from_rows(rows)

    assert len(batches) == 1
    assert batches[0]["user_id"] == "u1"
    assert batches[0]["project_id"] == "p1"
    connection = batches[0]["connections"][0]
    assert connection["source"] == "deployment"
    assert connection["provider"] == "vercel"
    assert connection["status"] == "verified"
    assert connection["connected"] is True
    assert connection["active_badges"] == [
        {"badge_type": "product_live", "label": "Product Live", "expires_at": None}
    ]


def test_worker_dry_run_prepares_expiry_and_badge_notifications_without_mutation() -> None:
    db = FakeSession()
    result = _run_trust_continuous_verification_batch(
        _expired_badge_batch(),
        execute=False,
        db=db,
        service=_service(),
    )

    assert result["execute"] is False
    assert result["actions_prepared"] == 1
    assert result["executed_actions"] == 0
    assert db.added == []
    assert "trust_verification_expired" in result["notification_types"]
    assert "trust_badge_status_changed" in result["notification_types"]
    assert result["badge_notifications_prepared"] == 1
    assert result["privacy"]["raw_payload_stored"] is False
    assert result["privacy"]["provider_calls_executed"] is False


def test_worker_execute_appends_history_without_deleting_existing_data() -> None:
    db = FakeSession()
    result = _run_trust_continuous_verification_batch(
        _expired_github_batch(),
        execute=True,
        db=db,
        service=_service(),
    )

    added_names = [row.__class__.__name__ for row in db.added]
    assert result["execute"] is True
    assert result["executed_actions"] == 1
    assert db.commits == 1
    assert "TrustProfile" in added_names
    assert "TrustVerificationHistory" in added_names
    assert "TrustTimelineEvent" in added_names
    assert result["executed_results"][0]["recorded_status"] == VerificationStatus.EXPIRED.value
    assert result["executed_results"][0]["raw_payload_stored"] is False


def test_worker_aggregates_dry_run_metrics() -> None:
    result = _run_trust_continuous_verification_batches(
        [_expired_badge_batch()],
        execute=False,
        service_factory=_service,
    )

    assert result["execute"] is False
    assert result["batches_seen"] == 1
    assert result["batches_processed"] == 1
    assert result["connections_seen"] == 1
    assert result["actions_prepared"] == 1
    assert result["notifications_prepared"] == 2
    assert result["badge_notifications_prepared"] == 1
    assert result["executed_actions"] == 0
    assert result["privacy"]["execute_required_for_mutation"] is True


def test_trust_worker_is_registered_on_scheduled_queue() -> None:
    schedule = celery.conf.beat_schedule
    assert "trust-continuous-verification" in schedule
    assert schedule["trust-continuous-verification"]["task"] == "workers.trust_continuous_verification"
    assert celery.conf.task_routes["workers.trust_continuous_verification"]["queue"] == "scheduled"


def main() -> int:
    tests: List[Callable[[], None]] = [
        test_worker_groups_due_trust_rows_with_badge_refs,
        test_worker_dry_run_prepares_expiry_and_badge_notifications_without_mutation,
        test_worker_execute_appends_history_without_deleting_existing_data,
        test_worker_aggregates_dry_run_metrics,
        test_trust_worker_is_registered_on_scheduled_queue,
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
    print(f"\nAll {len(tests)} Trust continuous verification worker tests passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
