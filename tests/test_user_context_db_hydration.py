"""User identity hydration must not import commercial authorization state."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

from main import _context_from_claim, _hydrate_from_db
from ai_router_core import UserRole


def _db(row=None, error=False):
    db = MagicMock()
    if error:
        db.execute.side_effect = RuntimeError("db unavailable")
    else:
        db.execute.return_value.scalar_one_or_none.return_value = row
    return db


def test_commercial_claims_are_ignored() -> None:
    ctx = _context_from_claim("u1", {
        "role": "founder", "subscription_tier": "enterprise",
        "credits_remaining": 999999, "plan_id": "anything",
    })
    assert not hasattr(ctx, "subscription_tier")
    assert not hasattr(ctx, "credits_remaining")


def test_db_hydrates_role_only() -> None:
    ctx = _context_from_claim("u2", {"role": "founder", "industry": "saas"})
    hydrated = _hydrate_from_db(ctx, _db(SimpleNamespace(role="investor")))
    assert hydrated.role == UserRole.INVESTOR
    assert hydrated.industry == "saas"


def test_db_miss_or_error_preserves_context() -> None:
    ctx = _context_from_claim("u3", {"role": "founder"})
    assert _hydrate_from_db(ctx, _db()) == ctx
    assert _hydrate_from_db(ctx, _db(error=True)) == ctx
