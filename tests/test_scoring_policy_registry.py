"""Versioned deterministic scoring policy contracts."""

from __future__ import annotations

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ai_router_core import ScoringEngine  # noqa: E402
from integration_guide import MatchingEngineService  # noqa: E402
from policy_registry import SCORING_POLICY, ScoringPolicyError, _validate, _validate_freshness, policy_metadata  # noqa: E402


def test_policy_has_identity_and_normalized_weights() -> None:
    metadata = policy_metadata()

    assert metadata["policy_id"] == "techit-scoring-2026-08-14-v1"
    assert metadata["effective_at"]
    assert metadata["owner"] == "platform-risk"
    assert SCORING_POLICY["changelog"]
    for section in ("unicorn", "gsis", "evi_investor", "investment", "match"):
        assert sum(SCORING_POLICY[section]["weights"].values()) == pytest.approx(1.0)


def test_invalid_policy_weights_fail_validation() -> None:
    invalid = {
        **SCORING_POLICY,
        "match": {"weights": {"skill": 0.5, "goal": 0.2}},
    }

    with pytest.raises(ScoringPolicyError):
        _validate(invalid)


def test_non_numeric_policy_weights_raise_typed_error() -> None:
    invalid = {
        **SCORING_POLICY,
        "match": {**SCORING_POLICY["match"], "weights": {"skill": "not-a-number"}},
    }

    with pytest.raises(ScoringPolicyError, match="numeric"):
        _validate(invalid)


def test_production_policy_freshness_rejects_stale_policy(monkeypatch) -> None:
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("SCORING_POLICY_MAX_AGE_DAYS", "1")
    stale = {**SCORING_POLICY, "effective_at": "2020-01-01T00:00:00Z"}

    with pytest.raises(ScoringPolicyError, match="stale"):
        _validate_freshness(stale)


def test_existing_score_behavior_is_preserved_with_policy_metadata() -> None:
    gsis = ScoringEngine.compute_gsis(80, 70, 60, 50, 40, 30, 20, 10, 100)
    unicorn = ScoringEngine.compute_unicorn_potential_score({"market_size": 10})
    evi_i = ScoringEngine.compute_evi_investor(80, 70, 60, 50, 40, 90)

    assert gsis["gsis"] == 53.5
    assert gsis["policy"]["policy_id"] == policy_metadata()["policy_id"]
    assert unicorn["unicorn_potential_score"] == 15.0
    assert unicorn["policy"]["policy_id"] == policy_metadata()["policy_id"]
    assert evi_i["raw_evi_i"] == 66.0
    assert evi_i["policy"]["policy_id"] == policy_metadata()["policy_id"]


def test_investment_match_and_decay_read_policy_values() -> None:
    investment = ScoringEngine.compute_investment_score(80, 70, 60, 50, 40, 30)
    match = ScoringEngine.compute_match_score(0.9, 0.8, 0.7, 0.6, 0.5, 0.4)
    decay = ScoringEngine.compute_decay_factor(10)

    assert investment == 63.5
    assert match == 71.5
    assert decay == pytest.approx(0.818731)


def test_compatibility_response_exposes_policy_and_policy_thresholds() -> None:
    service = MatchingEngineService.__new__(MatchingEngineService)
    result = service.compute_compatibility(
        {"skill_similarity": 0.9, "goal_similarity": 0.8, "exec_style_sim": 0.7},
        {"availability_score": 0.6, "trust_score": 0.5, "domain_score": 0.4},
    )

    assert result["match_score"] == 71.5
    assert result["compatibility"] == "medium"
    assert result["policy"]["policy_id"] == SCORING_POLICY["policy_id"]


def test_compatibility_without_component_evidence_fails_closed() -> None:
    service = MatchingEngineService.__new__(MatchingEngineService)
    result = service.compute_compatibility({}, {})

    assert result["match_score"] is None
    assert result["compatibility"] == "insufficient_evidence"
    assert result["evidence_status"] == "insufficient_evidence"
    assert len(result["missing_evidence"]) == 6
