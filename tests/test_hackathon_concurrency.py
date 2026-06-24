"""
Contract test for B1 + B3:

- B1: the _HACKATHON_STORE asyncio.Lock prevents check-in losses under
  concurrent load. Without the lock, two concurrent log_check_in calls read
  the same (activity, checkIns) tuple and the last write wins, dropping one
  check-in. With the lock, both increments stick.

- B3: production env (ENVIRONMENT=production, HACKATHON_SEED_TEAMS unset)
  yields an empty store on first touch; dev env still gets the four seed
  teams. HACKATHON_SEED_TEAMS=true/false overrides regardless of env.

Standalone (no pytest). Run:
    python3 tests/test_hackathon_concurrency.py
"""

from __future__ import annotations

import asyncio
import importlib
import os
import sys
from types import SimpleNamespace

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Stub out everything integration_guide.py imports that we don't need.
os.environ.setdefault("SECRET_KEY", "test")
os.environ.setdefault("ALLOW_DEMO_AUTH", "true")


def _fresh_module():
    """Reimport integration_guide so module-level state (_HACKATHON_STORE,
    _HACKATHON_LOCKS, _SEED_TEAMS gating) resets between tests."""
    if "integration_guide" in sys.modules:
        del sys.modules["integration_guide"]
    return importlib.import_module("integration_guide")


def _user_ctx(mod):
    from ai_router_core import SubscriptionTier, UserContext, UserRole
    return UserContext(
        user_id="u_test", role=UserRole.FOUNDER,
        subscription_tier=SubscriptionTier.FOUNDER_PRO,
        credits_remaining=100, project_id="p", project_stage="mvp",
        industry="saas", tech_stack=[], past_feedback=[], training_progress={},
        time_logged_today=0, tasks_completed_week=0, days_since_update=0,
        team_size=1, has_revenue=False, beta_users_count=0,
    )


def test_concurrent_checkins_no_losses() -> None:
    """100 concurrent check-ins on the same team must produce checkIns == 100."""
    os.environ["ENVIRONMENT"] = "development"
    os.environ["HACKATHON_SEED_TEAMS"] = "true"
    mod = _fresh_module()
    # Use a fresh hackathon_id so seed teams don't pollute counts.
    hack_id = "hack_concurrency_test"
    # Plant a fresh team explicitly so we know the starting checkIns count.
    mod._HACKATHON_STORE[hack_id] = {
        "team_x": {"id": "team_x", "name": "X", "isSolo": True,
                   "status": "registered", "hasBrief": False, "composite": 0,
                   "checkIns": 0, "hasWorkspace": False, "activity": 0.0},
    }

    svc = mod.HackathonService(SimpleNamespace())  # brain unused for these methods
    ctx = _user_ctx(mod)

    async def run() -> None:
        await asyncio.gather(*[
            svc.log_check_in(ctx, {
                "hackathonId": hack_id, "teamId": "team_x",
                "note": f"n{i}", "progressDelta": 1,
            })
            for i in range(100)
        ])

    asyncio.run(run())
    assert mod._HACKATHON_STORE[hack_id]["team_x"]["checkIns"] == 100, (
        f"expected 100 check-ins, got {mod._HACKATHON_STORE[hack_id]['team_x']['checkIns']}"
    )


def test_concurrent_registers_no_corruption() -> None:
    """50 concurrent registers must leave a coherent team dict (no half-written
    fields), not raise, and produce 50 distinct teams."""
    os.environ["ENVIRONMENT"] = "development"
    os.environ["HACKATHON_SEED_TEAMS"] = "false"
    mod = _fresh_module()
    svc = mod.HackathonService(SimpleNamespace())
    ctx = _user_ctx(mod)

    async def run() -> None:
        await asyncio.gather(*[
            svc.register(ctx, {
                "hackathonId": "hack_reg", "teamId": f"team_{i}",
                "name": f"team_{i}", "members": [],
            })
            for i in range(50)
        ])

    asyncio.run(run())
    store = mod._HACKATHON_STORE["hack_reg"]
    assert len(store) == 50, f"expected 50 teams, got {len(store)}"
    for tid, team in store.items():
        assert team["id"] == tid
        assert team["status"] == "registered"
        assert team["isSolo"] is True


def test_seed_teams_off_in_production() -> None:
    os.environ["ENVIRONMENT"] = "production"
    os.environ.pop("HACKATHON_SEED_TEAMS", None)
    mod = _fresh_module()
    svc = mod.HackathonService(SimpleNamespace())
    teams = svc._teams("hack_prod")
    # Empty store on first touch — no Loom Health / Solaris / Verdant / Northwind.
    assert teams == [], f"production must NOT seed demo teams; got {len(teams)}: {teams}"


def test_seed_teams_on_in_development() -> None:
    os.environ["ENVIRONMENT"] = "development"
    os.environ.pop("HACKATHON_SEED_TEAMS", None)
    mod = _fresh_module()
    svc = mod.HackathonService(SimpleNamespace())
    teams = svc._teams("hack_dev")
    assert len(teams) == 4, f"development should seed 4 teams, got {len(teams)}"
    names = {t["name"] for t in teams}
    assert names == {"Loom Health", "Solaris", "Verdant", "Northwind"}


def test_explicit_override_wins() -> None:
    """HACKATHON_SEED_TEAMS=true forces seeding even in production."""
    os.environ["ENVIRONMENT"] = "production"
    os.environ["HACKATHON_SEED_TEAMS"] = "true"
    mod = _fresh_module()
    svc = mod.HackathonService(SimpleNamespace())
    assert len(svc._teams("hack_forced")) == 4


def main() -> int:
    tests = [
        test_concurrent_checkins_no_losses,
        test_concurrent_registers_no_corruption,
        test_seed_teams_off_in_production,
        test_seed_teams_on_in_development,
        test_explicit_override_wins,
    ]
    for t in tests:
        try:
            t()
            print(f"  ok  {t.__name__}")
        except AssertionError as exc:
            print(f"  FAIL {t.__name__}: {exc}")
            return 1
        except Exception as exc:  # noqa: BLE001
            print(f"  ERROR {t.__name__}: {type(exc).__name__}: {exc}")
            return 1
    print(f"\n{len(tests)} passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
