"""Production outcome ingestion and calibration reporting."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Iterable, Mapping
import uuid

from database_schema import DecisionOutcome
from offline_evaluation import load_evaluation_contract
from policy_registry import SCORING_POLICY


ALLOWED_DOMAINS = {"matching", "gsis", "ups", "evi_investor", "investment", "risk", "valuation"}
VERIFIED_SOURCES = {"verified_platform_event", "verified_financial_record", "verified_match_outcome", "human_reviewed_outcome"}


class ProductionCalibrationError(ValueError):
    pass


def record_outcome(db: Any, payload: Mapping[str, Any]) -> DecisionOutcome:
    domain = str(payload.get("domain") or "")
    source = str(payload.get("source") or "")
    decision_id = str(payload.get("decision_id") or "")
    if domain not in ALLOWED_DOMAINS or source not in VERIFIED_SOURCES or not decision_id:
        raise ProductionCalibrationError("verified decision_id, domain, and source are required")
    row = db.query(DecisionOutcome).filter(
        DecisionOutcome.decision_id == decision_id, DecisionOutcome.domain == domain,
    ).first()
    if row is None:
        row = DecisionOutcome(id=uuid.uuid4(), decision_id=decision_id, domain=domain)
        db.add(row)
    row.policy_id = str(payload.get("policy_id") or SCORING_POLICY["policy_id"])
    row.predicted_score = payload.get("predicted_score")
    row.predicted_probability = payload.get("predicted_probability")
    row.predicted_positive = payload.get("predicted_positive")
    row.observed_positive = payload.get("observed_positive")
    row.observed_at = datetime.now(timezone.utc) if isinstance(row.observed_positive, bool) else None
    row.source = source
    row.evidence = dict(payload.get("evidence") or {})
    db.commit()
    db.refresh(row)
    return row


def evaluate_outcomes(rows: Iterable[Any]) -> Dict[str, Any]:
    rows = list(rows)
    contract = load_evaluation_contract()
    labeled = [row for row in rows if isinstance(row.observed_positive, bool)]
    tp = sum(row.predicted_positive is True and row.observed_positive is True for row in labeled)
    tn = sum(row.predicted_positive is False and row.observed_positive is False for row in labeled)
    fp = sum(row.predicted_positive is True and row.observed_positive is False for row in labeled)
    fn = sum(row.predicted_positive is False and row.observed_positive is True for row in labeled)
    fpr = fp / (fp + tn) if fp + tn else None
    fnr = fn / (fn + tp) if fn + tp else None
    probabilities = [row for row in labeled if row.predicted_probability is not None]
    brier = sum((float(row.predicted_probability) - float(row.observed_positive)) ** 2 for row in probabilities) / len(probabilities) if probabilities else None
    coverage = len(labeled) / len(rows) if rows else 0.0
    gates = contract["release_gates"]
    domain_counts = {domain: sum(row.domain == domain for row in rows) for domain in ALLOWED_DOMAINS}
    reasons = []
    if len(rows) < gates["minimum_total_cases"]: reasons.append("insufficient_total_outcome_sample")
    if any(count < gates["minimum_cases_per_domain"] for count in domain_counts.values()): reasons.append("insufficient_per_domain_outcome_sample")
    if coverage < gates["minimum_outcome_coverage"]: reasons.append("insufficient_outcome_coverage")
    if fpr is None or fpr > gates["maximum_false_positive_rate"]: reasons.append("false_positive_rate_not_approved")
    if fnr is None or fnr > gates["maximum_false_negative_rate"]: reasons.append("false_negative_rate_not_approved")
    if len(probabilities) < contract["probability_claims"]["minimum_sample_size"]: reasons.append("insufficient_probability_calibration_sample")
    if brier is None or brier > gates["maximum_brier_score"]: reasons.append("brier_score_not_approved")
    return {"policy_id": SCORING_POLICY["policy_id"], "total_decisions": len(rows), "labeled_outcomes": len(labeled), "domain_counts": domain_counts, "outcome_coverage": round(coverage, 6), "false_positive_rate": None if fpr is None else round(fpr, 6), "false_negative_rate": None if fnr is None else round(fnr, 6), "brier_score": None if brier is None else round(brier, 6), "calibration_status": "approved" if not reasons else "human_review_only", "reasons": reasons}


def production_report(db: Any, policy_id: str | None = None) -> Dict[str, Any]:
    active = policy_id or SCORING_POLICY["policy_id"]
    rows = db.query(DecisionOutcome).filter(DecisionOutcome.policy_id == active).all()
    return evaluate_outcomes(rows)
