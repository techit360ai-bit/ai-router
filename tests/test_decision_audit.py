"""Privacy and fail-closed contracts for ranking audit events."""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from decision_audit import DecisionAuditError, build_ranking_audit  # noqa: E402


def test_ranking_audit_contains_exposure_without_profile_values(monkeypatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "development")
    event = build_ranking_audit([{
        "user_id": "candidate-secret-id",
        "name": "Private Person",
        "skills": ["Private Skill"],
        "profile_signals": {"profile_completeness_pct": 85},
    }], "sufficient")

    serialized = str(event)
    assert event["candidates_returned"] == 1
    assert event["ranking_exposure"][0]["rank"] == 1
    assert event["ranking_exposure"][0]["evidence_quality_band"] == "high"
    assert event["outcome_parity"]["status"] == "insufficient_outcome_evidence"
    assert "candidate-secret-id" not in serialized
    assert "Private Person" not in serialized
    assert "Private Skill" not in serialized


def test_production_audit_requires_hmac_key(monkeypatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.delenv("DECISION_AUDIT_HMAC_KEY", raising=False)

    with pytest.raises(DecisionAuditError, match="HMAC_KEY"):
        build_ranking_audit([{"user_id": "candidate"}], "sufficient")
