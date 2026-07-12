"""
Contract test for live hackathon repository behavior.

The hackathon command center must start from empty persisted state and derive
overview, velocity, leaderboard, and pipeline from real registrations, briefs,
and check-ins. No seeded team names are allowed.

Standalone (no pytest). Run:
    python3 tests/test_hackathon_live_repository.py
"""

from __future__ import annotations

import asyncio
import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.environ.setdefault("SECRET_KEY", "test")
os.environ["ENVIRONMENT"] = "development"
os.environ.pop("DATABASE_URL", None)

from ai_router_core import SubscriptionTier, UserContext, UserRole  # noqa: E402
from integration_guide import HackathonService  # noqa: E402
from live_domain_repository import reset_memory_store_for_tests  # noqa: E402


def _user_ctx() -> UserContext:
    return UserContext(
        user_id="u_test",
        role=UserRole.FOUNDER,
        subscription_tier=SubscriptionTier.FOUNDER_PRO,
        credits_remaining=100,
        project_id="p",
        project_stage="mvp",
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


def test_hackathon_state_starts_empty() -> None:
    reset_memory_store_for_tests()
    svc = HackathonService(SimpleNamespace())
    ctx = _user_ctx()

    async def run() -> None:
        listing = await svc.list_hackathons(ctx)
        overview = await svc.get_overview(ctx, "hack_live")
        velocity = await svc.get_velocity_heatmap(ctx, "hack_live")

        assert listing["hackathons"] == []
        assert overview["totalTeams"] == 0
        assert overview["registrants"] == 0
        assert velocity["teams"] == []

    asyncio.run(run())


def test_registered_activity_drives_org_metrics() -> None:
    reset_memory_store_for_tests()
    svc = HackathonService(SimpleNamespace())
    ctx = _user_ctx()

    async def run() -> None:
        created = await svc.create_hackathon(ctx, {"name": "Live Sprint", "status": "live"})
        hackathon_id = created["hackathon"]["id"]
        registered = await svc.register(ctx, {
            "hackathonId": hackathon_id,
            "name": "Real Team",
            "members": [{"name": "Alice"}, {"name": "Bob"}],
        })
        team_id = registered["team"]["id"]

        await svc.submit_brief(ctx, {
            "hackathonId": hackathon_id,
            "teamId": team_id,
            "problem": "A quantified user problem wastes 12 hours per team every month.",
            "solution": "A focused product workflow that removes duplicate reporting and keeps teams aligned.",
            "teamMomentum": 70,
            "demoReadinessHours": 8,
        })
        await asyncio.gather(*[
            svc.log_check_in(ctx, {
                "hackathonId": hackathon_id,
                "teamId": team_id,
                "note": f"update {i}",
                "progressDelta": 2,
            })
            for i in range(25)
        ])

        overview = await svc.get_overview(ctx, hackathon_id)
        velocity = await svc.get_velocity_heatmap(ctx, hackathon_id)
        leaderboard = await svc.get_leaderboard(ctx, hackathon_id)
        pipeline = await svc.get_pipeline(ctx, hackathon_id)

        assert overview["totalTeams"] == 1
        assert overview["registrants"] == 2
        assert overview["ideaSubmissions"] == 1
        assert overview["avgBuildVelocity"] > 0
        assert velocity["teams"][0]["teamId"] == team_id
        assert leaderboard["leaderboard"][0]["teamId"] == team_id
        assert sum(pipeline["buckets"].values()) == 1

    asyncio.run(run())


def main() -> int:
    tests = [
        test_hackathon_state_starts_empty,
        test_registered_activity_drives_org_metrics,
    ]
    for test in tests:
        try:
            test()
            print(f"  ok  {test.__name__}")
        except AssertionError as exc:
            print(f"  FAIL {test.__name__}: {exc}")
            return 1
        except Exception as exc:  # noqa: BLE001
            print(f"  ERROR {test.__name__}: {type(exc).__name__}: {exc}")
            return 1
    print(f"\n{len(tests)} passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
