from __future__ import annotations

from types import SimpleNamespace

from production_calibration import ALLOWED_DOMAINS, evaluate_outcomes


def test_empty_production_outcomes_remain_human_review_only() -> None:
    report = evaluate_outcomes([])
    assert report["calibration_status"] == "human_review_only"
    assert "insufficient_total_outcome_sample" in report["reasons"]


def test_verified_well_calibrated_outcomes_can_pass_contract() -> None:
    domains = sorted(ALLOWED_DOMAINS)
    rows = []
    for index in range(1050):
        observed = index % 2 == 0
        rows.append(SimpleNamespace(
            domain=domains[index % len(domains)],
            predicted_positive=observed,
            observed_positive=observed,
            predicted_probability=0.9 if observed else 0.1,
        ))
    report = evaluate_outcomes(rows)
    assert report["calibration_status"] == "approved"
    assert report["false_positive_rate"] == 0
    assert report["false_negative_rate"] == 0
    assert report["brier_score"] == 0.01
