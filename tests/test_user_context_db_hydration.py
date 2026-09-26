"""User identity hydration must not import commercial authorization state."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

import main as main_module
from main import (
    IdentityHydrationError,
    SessionFreshnessError,
    _assert_token_fresh,
    _context_from_claim,
    _hydrate_from_db,
)
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


def test_db_miss_preserves_context() -> None:
    ctx = _context_from_claim("u3", {"role": "founder"})
    assert _hydrate_from_db(ctx, _db()) == ctx


def test_db_error_is_not_silently_authorized() -> None:
    ctx = _context_from_claim("u3", {"role": "founder"})
    assert _hydrate_from_db(ctx, _db(error=True)) == ctx
    assert _hydrate_from_db(ctx, _db(error=True)) == ctx


def test_production_hydration_fails_closed_on_missing_user_or_query_error() -> None:
    ctx = _context_from_claim("u4", {"role": "founder"})
    with pytest.raises(IdentityHydrationError):
        _hydrate_from_db(ctx, _db(), require_user=True)
    with pytest.raises(IdentityHydrationError):
        _hydrate_from_db(ctx, _db(error=True), require_user=True)


def _session_db(user_id=None):
    db = MagicMock()
    db.execute.return_value.first.return_value = None if user_id is None else (user_id,)
    return db


def test_token_age_bound_rejects_stale_token(monkeypatch) -> None:
    monkeypatch.setenv("AI_ROUTER_MAX_TOKEN_AGE_SECONDS", "900")
    with pytest.raises(SessionFreshnessError):
        _assert_token_fresh({"sub": "u1", "iat": 1_000}, None, now=2_000)


def test_token_age_bound_allows_fresh_token(monkeypatch) -> None:
    monkeypatch.setenv("AI_ROUTER_MAX_TOKEN_AGE_SECONDS", "900")
    _assert_token_fresh({"sub": "u1", "iat": 1_900}, None, now=2_000)


def test_token_age_bound_requires_issued_at(monkeypatch) -> None:
    monkeypatch.setenv("AI_ROUTER_MAX_TOKEN_AGE_SECONDS", "900")
    with pytest.raises(SessionFreshnessError):
        _assert_token_fresh({"sub": "u1"}, None, now=2_000)


def test_age_bound_disabled_by_default() -> None:
    _assert_token_fresh({"sub": "u1"}, None, now=2_000_000_000)


def test_revoked_session_is_rejected(monkeypatch) -> None:
    monkeypatch.setattr(main_module, "ENVIRONMENT", "production")
    with pytest.raises(SessionFreshnessError):
        _assert_token_fresh({"sub": "u1", "sid": "s1"}, _session_db())


def test_active_session_is_accepted(monkeypatch) -> None:
    monkeypatch.setattr(main_module, "ENVIRONMENT", "production")
    _assert_token_fresh({"sub": "u1", "sid": "s1"}, _session_db("u1"))


def test_session_subject_mismatch_is_rejected(monkeypatch) -> None:
    monkeypatch.setattr(main_module, "ENVIRONMENT", "production")
    with pytest.raises(SessionFreshnessError):
        _assert_token_fresh({"sub": "u1", "sid": "s1"}, _session_db("u2"))


def test_revocation_check_can_be_disabled(monkeypatch) -> None:
    monkeypatch.setattr(main_module, "ENVIRONMENT", "production")
    monkeypatch.setenv("AI_ROUTER_SESSION_REVOCATION_CHECK", "false")
    _assert_token_fresh({"sub": "u1", "sid": "s1"}, _session_db())


def test_legacy_token_without_sid_skips_revocation(monkeypatch) -> None:
    monkeypatch.setattr(main_module, "ENVIRONMENT", "production")
    _assert_token_fresh({"sub": "u1"}, None)


def test_session_lookup_failure_fails_open(monkeypatch) -> None:
    monkeypatch.setattr(main_module, "ENVIRONMENT", "production")
    db = MagicMock()
    db.execute.side_effect = RuntimeError("relation \"user_sessions\" does not exist")
    _assert_token_fresh({"sub": "u1", "sid": "s1"}, db)


def test_session_lookup_failure_is_fatal_in_strict_mode(monkeypatch) -> None:
    monkeypatch.setattr(main_module, "ENVIRONMENT", "production")
    monkeypatch.setenv("AI_ROUTER_SESSION_REVOCATION_STRICT", "true")
    db = MagicMock()
    db.execute.side_effect = RuntimeError("boom")
    with pytest.raises(SessionFreshnessError):
        _assert_token_fresh({"sub": "u1", "sid": "s1"}, db)


def test_role_downgrade_takes_effect_on_the_next_request() -> None:
    ctx = _context_from_claim("u5", {"role": "admin"})
    assert ctx.role == UserRole.ADMIN
    hydrated = _hydrate_from_db(ctx, _db(SimpleNamespace(role="investor")))
    assert hydrated.role == UserRole.INVESTOR
