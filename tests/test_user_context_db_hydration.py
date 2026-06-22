"""
Contract test for H4 / ai-router #13: the JWT-claim-trust hole.

Before this fix: a forged JWT claim of `credits_remaining: 999999` granted that
many credits to the bearer. UserContext was built straight from the claim.

After: _hydrate_from_db reads the real value from the `users` table keyed by
`sub` and overrides the claim. A forged claim cannot inflate credits.

Standalone test (no pytest dependency). Run:
    python3 tests/test_user_context_db_hydration.py

Exit 0 = all asserts passed.
"""

from __future__ import annotations

import os
import sys
from types import SimpleNamespace
from unittest.mock import MagicMock

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Don't fail on missing env vars when importing main.
os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("ALLOW_DEMO_AUTH", "true")

from main import _context_from_claim, _hydrate_from_db  # noqa: E402


def _fake_db(row: object | None, *, raises: bool = False) -> MagicMock:
    """Build a mock DB session whose execute().scalar_one_or_none() returns
    `row`, or raises if `raises=True`."""
    db = MagicMock()
    if raises:
        db.execute.side_effect = RuntimeError("db unreachable")
    else:
        db.execute.return_value.scalar_one_or_none.return_value = row
    return db


def test_forged_credit_claim_is_overridden_by_db_value() -> None:
    """A token claiming 999_999 credits cannot bypass the paywall — the DB
    row (15 total) wins."""
    forged_claim = {
        "credits_remaining": 999_999,
        "subscription_tier": "founder_pro",
        "role": "founder",
    }
    ctx = _context_from_claim("user-uuid-1", forged_claim)
    assert ctx.credits_remaining == 999_999, "sanity: claim builder honors claim"

    row = SimpleNamespace(
        id="user-uuid-1",
        role="founder",
        subscription_tier="free",
        subscription_credits_remaining=10,
        payg_credits_balance=5,
    )
    hydrated = _hydrate_from_db(ctx, _fake_db(row))
    assert hydrated.credits_remaining == 15, (
        f"DB credits (10 + 5) must override forged claim 999999; got {hydrated.credits_remaining}"
    )
    # Subscription tier also from DB.
    from ai_router_core import SubscriptionTier
    assert hydrated.subscription_tier == SubscriptionTier.FREE, (
        f"DB tier (FREE) must override forged tier; got {hydrated.subscription_tier}"
    )


def test_unrelated_fields_stay_from_claim() -> None:
    """Identity (user_id) + incidental fields (industry, project_id, etc.)
    aren't security-critical and shouldn't be overridden by DB hydration."""
    claim = {
        "credits_remaining": 100,
        "project_id": "proj-from-claim",
        "industry": "saas",
        "team_size": 4,
    }
    ctx = _context_from_claim("user-uuid-2", claim)
    row = SimpleNamespace(
        id="user-uuid-2",
        role="founder",
        subscription_tier="founder_pro",
        subscription_credits_remaining=20,
        payg_credits_balance=0,
    )
    hydrated = _hydrate_from_db(ctx, _fake_db(row))
    assert hydrated.user_id == "user-uuid-2"
    assert hydrated.project_id == "proj-from-claim"
    assert hydrated.industry == "saas"
    assert hydrated.team_size == 4
    assert hydrated.credits_remaining == 20  # security-critical: DB wins


def test_db_miss_returns_claim_context_unchanged() -> None:
    """Token is valid but no user row exists yet (newly-issued token, demo
    mode, etc.). Don't 401 — preserve the claim context."""
    ctx = _context_from_claim("user-uuid-3", {"credits_remaining": 50})
    hydrated = _hydrate_from_db(ctx, _fake_db(row=None))
    assert hydrated is ctx or hydrated == ctx, "claim context returned unchanged"
    assert hydrated.credits_remaining == 50


def test_db_error_returns_claim_context_unchanged() -> None:
    """DB unreachable shouldn't take auth down — fall back to claim and log."""
    ctx = _context_from_claim("user-uuid-4", {"credits_remaining": 30})
    hydrated = _hydrate_from_db(ctx, _fake_db(row=None, raises=True))
    assert hydrated is ctx or hydrated == ctx
    assert hydrated.credits_remaining == 30


def main() -> int:
    tests = [
        test_forged_credit_claim_is_overridden_by_db_value,
        test_unrelated_fields_stay_from_claim,
        test_db_miss_returns_claim_context_unchanged,
        test_db_error_returns_claim_context_unchanged,
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
