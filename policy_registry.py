"""Validated, versioned policy inputs for deterministic AI Router scores."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import math
import os
from pathlib import Path
from typing import Any, Dict


class ScoringPolicyError(RuntimeError):
    """Raised when the deterministic scoring policy is missing or invalid."""


def _load_policy() -> Dict[str, Any]:
    configured = os.getenv("SCORING_POLICY_PATH", "").strip()
    path = Path(configured) if configured else Path(__file__).with_name("config") / "scoring_policies.json"
    try:
        with path.open("r", encoding="utf-8") as handle:
            policy = json.load(handle)
    except (OSError, ValueError) as exc:
        raise ScoringPolicyError(f"Unable to load scoring policy: {path}") from exc
    _validate(policy)
    _validate_freshness(policy)
    return policy


def _validate(policy: Any) -> None:
    if not isinstance(policy, dict):
        raise ScoringPolicyError("Scoring policy must be an object")
    for field in ("policy_id", "effective_at", "owner"):
        if not isinstance(policy.get(field), str) or not policy[field].strip():
            raise ScoringPolicyError(f"Scoring policy requires non-empty {field}")
    if not isinstance(policy.get("changelog"), list) or not policy["changelog"]:
        raise ScoringPolicyError("Scoring policy requires a non-empty changelog")
    for section_name in ("unicorn", "gsis", "evi_investor", "investment", "match", "decay", "valuation", "calibration"):
        if not isinstance(policy.get(section_name), dict):
            raise ScoringPolicyError(f"Scoring policy section is missing: {section_name}")
    for section_name in ("unicorn", "gsis", "evi_investor", "investment", "match"):
        weights = policy[section_name].get("weights")
        if not isinstance(weights, dict) or not weights:
            raise ScoringPolicyError(f"Scoring policy weights are missing: {section_name}")
        try:
            numeric_weights = [float(value) for value in weights.values()]
        except (TypeError, ValueError) as exc:
            raise ScoringPolicyError(f"Scoring policy weights must be numeric: {section_name}") from exc
        if any(not math.isfinite(value) for value in numeric_weights):
            raise ScoringPolicyError(f"Scoring policy weights must be finite: {section_name}")
        if abs(sum(numeric_weights) - 1.0) > 1e-6:
            raise ScoringPolicyError(f"Scoring policy weights must sum to 1: {section_name}")
        if any(value < 0 for value in numeric_weights):
            raise ScoringPolicyError(f"Scoring policy weights cannot be negative: {section_name}")
    try:
        exponent = float(policy["decay"].get("exponent_per_inactive_day"))
        multiple = float(policy["valuation"].get("arr_multiple"))
        match_minimums = policy["match"].get("minimums", {})
        recommended = float(match_minimums.get("recommended"))
        review = float(match_minimums.get("review"))
    except (TypeError, ValueError) as exc:
        raise ScoringPolicyError("Scoring policy constants must be numeric") from exc
    if exponent <= 0:
        raise ScoringPolicyError("Decay exponent must be positive")
    if multiple <= 0:
        raise ScoringPolicyError("Valuation multiple must be positive")
    if not 0 <= review <= recommended <= 100:
        raise ScoringPolicyError("Match minimums must satisfy 0 <= review <= recommended <= 100")
    calibration = policy["calibration"]
    if calibration.get("status") not in {"not_calibrated", "calibrated"}:
        raise ScoringPolicyError("Calibration status must be not_calibrated or calibrated")
    if not isinstance(calibration.get("probability_claims_allowed"), bool):
        raise ScoringPolicyError("Calibration probability_claims_allowed must be boolean")
    if calibration["probability_claims_allowed"] and calibration["status"] != "calibrated":
        raise ScoringPolicyError("Probability claims cannot be enabled before calibration")
    if not isinstance(calibration.get("evaluation_contract_id"), str):
        raise ScoringPolicyError("Calibration evaluation_contract_id is required")


def _validate_freshness(policy: Dict[str, Any]) -> None:
    """Fail closed on future or stale policy in production-like environments."""
    environment = os.getenv("ENVIRONMENT", "development").strip().lower()
    if environment not in {"production", "staging"}:
        return
    try:
        effective_at = datetime.fromisoformat(str(policy["effective_at"]).replace("Z", "+00:00"))
    except (TypeError, ValueError) as exc:
        raise ScoringPolicyError("Scoring policy effective_at must be an ISO timestamp") from exc
    now = datetime.now(timezone.utc)
    if effective_at > now:
        raise ScoringPolicyError("Scoring policy effective_at cannot be in the future")
    try:
        max_age_days = float(os.getenv("SCORING_POLICY_MAX_AGE_DAYS", "90"))
    except ValueError as exc:
        raise ScoringPolicyError("SCORING_POLICY_MAX_AGE_DAYS must be numeric") from exc
    if max_age_days < 0 or (now - effective_at).total_seconds() > max_age_days * 86400:
        raise ScoringPolicyError("Scoring policy is stale for production use")


SCORING_POLICY = _load_policy()


def policy_metadata() -> Dict[str, str]:
    return {
        "policy_id": str(SCORING_POLICY["policy_id"]),
        "effective_at": str(SCORING_POLICY["effective_at"]),
        "owner": str(SCORING_POLICY["owner"]),
    }


def calibration_metadata() -> Dict[str, Any]:
    calibration = SCORING_POLICY["calibration"]
    return {
        "status": str(calibration["status"]),
        "probability_claims_allowed": bool(calibration["probability_claims_allowed"]),
        "evaluation_contract_id": str(calibration["evaluation_contract_id"]),
        "human_review_required": calibration["status"] != "calibrated",
    }
