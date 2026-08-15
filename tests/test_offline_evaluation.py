"""Offline score backtests and calibration release gates."""

from __future__ import annotations

import copy
import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from offline_evaluation import (  # noqa: E402
    REQUIRED_DOMAINS,
    OfflineEvaluationError,
    load_backtest_cases,
    load_evaluation_contract,
    run_backtests,
    validate_probability_claims,
)


def test_backtests_cover_all_domains_and_remain_human_review_only() -> None:
    report = run_backtests()

    assert report["cases_total"] == 8
    assert set(report["domain_case_counts"]) == REQUIRED_DOMAINS
    assert all(count >= 1 for count in report["domain_case_counts"].values())
    assert report["outcome_metrics"]["coverage"] == 1.0
    assert report["outcome_metrics"]["false_positive_rate"] == 0.0
    assert report["outcome_metrics"]["false_negative_rate"] == pytest.approx(1 / 3, abs=1e-6)
    assert report["drift_metrics"]["maximum_absolute_drift"] == 0.0
    assert report["calibration_metrics"]["numeric_probability_claims"] == 0
    assert report["release_gate"]["status"] == "human_review_only"
    assert "insufficient_total_outcome_sample" in report["release_gate"]["reasons"]
    assert "probability_calibration_not_approved" in report["release_gate"]["reasons"]


def test_numeric_probability_claim_without_calibration_is_rejected() -> None:
    contract = load_evaluation_contract()

    with pytest.raises(OfflineEvaluationError, match="not calibrated"):
        validate_probability_claims({
            "success_probability_pct": 72,
            "calibration": {
                "status": "not_calibrated",
                "probability_claims_allowed": False,
            },
        }, contract)


def test_calibrated_probability_claim_requires_minimum_metadata() -> None:
    contract = load_evaluation_contract()
    result = {
        "success_probability_pct": 72,
        "calibration": {
            "status": "calibrated",
            "probability_claims_allowed": True,
            "method": "isotonic",
            "sample_size": 1000,
            "as_of": "2026-08-15T00:00:00Z",
        },
    }

    assert validate_probability_claims(result, contract) == 1


def test_backtest_score_drift_fails_ci_contract() -> None:
    cases = copy.deepcopy(load_backtest_cases())
    cases[0]["expected"]["match_score"] = 99

    with pytest.raises(OfflineEvaluationError, match="Score drift"):
        run_backtests(cases=cases)


def test_contract_policy_identity_is_enforced() -> None:
    contract = copy.deepcopy(load_evaluation_contract())
    contract["policy_id"] = "wrong-policy"

    with pytest.raises(OfflineEvaluationError, match="policy_id"):
        run_backtests(contract=contract)
