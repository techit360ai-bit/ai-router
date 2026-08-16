"""Deterministic offline evaluation and calibration gates for router scores."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional

from ai_router_core import ScoringEngine
from policy_registry import SCORING_POLICY, calibration_metadata, policy_metadata


REQUIRED_DOMAINS = {
    "matching", "gsis", "gsis_v2", "ups", "evi_investor", "investment", "risk", "valuation",
}
DEFAULT_CONTRACT_PATH = Path(__file__).with_name("config") / "evaluation_contract.json"
DEFAULT_FIXTURE_PATH = Path(__file__).with_name("tests") / "fixtures" / "scoring_backtest_cases.json"


class OfflineEvaluationError(RuntimeError):
    """Raised when evaluation inputs or deterministic outputs violate the contract."""


def _load_json(path: Path) -> Dict[str, Any]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            value = json.load(handle)
    except (OSError, ValueError) as exc:
        raise OfflineEvaluationError(f"Unable to load evaluation data: {path}") from exc
    if not isinstance(value, dict):
        raise OfflineEvaluationError(f"Evaluation data must be an object: {path}")
    return value


def load_evaluation_contract(path: Optional[Path] = None) -> Dict[str, Any]:
    contract = _load_json(path or DEFAULT_CONTRACT_PATH)
    _validate_evaluation_contract(contract)
    return contract


def _validate_evaluation_contract(contract: Mapping[str, Any]) -> None:
    if contract.get("policy_id") != SCORING_POLICY["policy_id"]:
        raise OfflineEvaluationError("Evaluation contract policy_id does not match the active scoring policy")
    if contract.get("contract_id") != SCORING_POLICY["calibration"]["evaluation_contract_id"]:
        raise OfflineEvaluationError("Evaluation contract id does not match scoring policy calibration metadata")
    domains = contract.get("domains")
    if not isinstance(domains, dict) or set(domains) != REQUIRED_DOMAINS:
        raise OfflineEvaluationError("Evaluation contract must define every required score domain")
    if not isinstance(contract.get("release_gates"), dict):
        raise OfflineEvaluationError("Evaluation contract requires release_gates")


def load_backtest_cases(path: Optional[Path] = None) -> List[Dict[str, Any]]:
    payload = _load_json(path or DEFAULT_FIXTURE_PATH)
    contract = load_evaluation_contract()
    if payload.get("fixture_schema_version") != contract.get("fixture_schema_version"):
        raise OfflineEvaluationError("Backtest fixture schema version does not match the contract")
    if payload.get("contract_id") != contract.get("contract_id"):
        raise OfflineEvaluationError("Backtest fixtures reference the wrong evaluation contract")
    cases = payload.get("cases")
    if not isinstance(cases, list) or not cases:
        raise OfflineEvaluationError("Backtest fixtures require at least one case")
    case_ids = set()
    for case in cases:
        if not isinstance(case, dict) or not case.get("case_id"):
            raise OfflineEvaluationError("Every backtest case requires a case_id")
        if case["case_id"] in case_ids:
            raise OfflineEvaluationError(f"Duplicate backtest case id: {case['case_id']}")
        case_ids.add(case["case_id"])
        if case.get("domain") not in REQUIRED_DOMAINS:
            raise OfflineEvaluationError(f"Unknown backtest domain: {case.get('domain')}")
        if not isinstance(case.get("input"), dict) or not isinstance(case.get("expected"), dict):
            raise OfflineEvaluationError(f"Backtest case requires input and expected objects: {case['case_id']}")
    return cases


def _evaluate_case(case: Mapping[str, Any], contract: Mapping[str, Any]) -> Dict[str, Any]:
    domain = str(case["domain"])
    values = dict(case["input"])
    if domain == "matching":
        score = ScoringEngine.compute_match_score(**values)
        minimums = SCORING_POLICY["match"]["minimums"]
        classification = "high" if score >= minimums["recommended"] else "medium" if score >= minimums["review"] else "low"
        return _score_result(match_score=score, classification=classification)
    if domain == "gsis":
        return ScoringEngine.compute_gsis(**values)
    if domain == "gsis_v2":
        return ScoringEngine.compute_gsis_v2(values)
    if domain == "ups":
        return ScoringEngine.compute_unicorn_potential_score(values)
    if domain == "evi_investor":
        return ScoringEngine.compute_evi_investor(**values)
    if domain == "investment":
        return _score_result(investment_score=ScoringEngine.compute_investment_score(**values))
    if domain == "risk":
        required = contract["domains"]["risk"]["required_fields"]
        missing = [name for name in required if not str(values.get(name) or "").strip()]
        return {
            "status": "insufficient_evidence" if missing else "provisional_human_review_required",
            "missing_fields": missing,
            "policy": policy_metadata(),
            "calibration": calibration_metadata(),
            "human_review_required": True,
        }
    if domain == "valuation":
        valuation = float(values.get("mrr", 0)) * 12 * float(SCORING_POLICY["valuation"]["arr_multiple"])
        return _score_result(valuation=round(valuation, 2))
    raise OfflineEvaluationError(f"No evaluator for domain: {domain}")


def _score_result(**values: Any) -> Dict[str, Any]:
    return {
        **values,
        "policy": policy_metadata(),
        "calibration": calibration_metadata(),
        "human_review_required": True,
    }


def _path_value(value: Mapping[str, Any], path: str) -> Any:
    current: Any = value
    for part in path.split("."):
        if not isinstance(current, Mapping) or part not in current:
            raise OfflineEvaluationError(f"Evaluation result is missing path: {path}")
        current = current[part]
    return current


def _compare_expected(actual: Any, expected: Any, tolerance: float, path: str = "") -> List[float]:
    if isinstance(expected, dict):
        if not isinstance(actual, Mapping):
            raise OfflineEvaluationError(f"Expected object at {path or '<root>'}")
        drift: List[float] = []
        for key, expected_value in expected.items():
            if key not in actual:
                raise OfflineEvaluationError(f"Evaluation result is missing expected field: {path}{key}")
            drift.extend(_compare_expected(actual[key], expected_value, tolerance, f"{path}{key}."))
        return drift
    if isinstance(expected, list):
        if actual != expected:
            raise OfflineEvaluationError(f"Evaluation mismatch at {path[:-1]}: expected {expected!r}, got {actual!r}")
        return []
    if isinstance(expected, (int, float)) and not isinstance(expected, bool):
        if not isinstance(actual, (int, float)) or isinstance(actual, bool):
            raise OfflineEvaluationError(f"Expected numeric result at {path[:-1]}")
        difference = abs(float(actual) - float(expected))
        if difference > tolerance:
            raise OfflineEvaluationError(
                f"Score drift at {path[:-1]} exceeds tolerance: expected {expected}, got {actual}"
            )
        return [difference]
    if actual != expected:
        raise OfflineEvaluationError(f"Evaluation mismatch at {path[:-1]}: expected {expected!r}, got {actual!r}")
    return []


def _probability_values(value: Any, path: str = "") -> Iterable[tuple[str, float]]:
    if isinstance(value, Mapping):
        for key, item in value.items():
            key_path = f"{path}.{key}" if path else str(key)
            normalized = str(key).lower()
            if (
                "probability" in normalized
                and "calibrated" not in normalized
                and "allowed" not in normalized
                and isinstance(item, (int, float))
                and not isinstance(item, bool)
            ):
                yield key_path, float(item)
            yield from _probability_values(item, key_path)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _probability_values(item, f"{path}[{index}]")


def validate_probability_claims(result: Mapping[str, Any], contract: Mapping[str, Any]) -> int:
    claims = list(_probability_values(result))
    if not claims:
        return 0
    calibration = result.get("calibration")
    requirements = contract["probability_claims"]
    if not isinstance(calibration, Mapping):
        raise OfflineEvaluationError("Numeric probability claim lacks calibration metadata")
    if calibration.get("status") != requirements["required_calibration_status"]:
        raise OfflineEvaluationError("Numeric probability claim is not calibrated")
    if calibration.get("probability_claims_allowed") is not True:
        raise OfflineEvaluationError("Numeric probability claims are not approved")
    for field in requirements["required_metadata"]:
        if calibration.get(field) in (None, ""):
            raise OfflineEvaluationError(f"Numeric probability claim lacks calibration field: {field}")
    if int(calibration.get("sample_size", 0)) < int(requirements["minimum_sample_size"]):
        raise OfflineEvaluationError("Numeric probability claim has insufficient calibration sample size")
    return len(claims)


def run_backtests(
    cases: Optional[List[Dict[str, Any]]] = None,
    contract: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    contract = contract if contract is not None else load_evaluation_contract()
    _validate_evaluation_contract(contract)
    cases = cases if cases is not None else load_backtest_cases()
    tolerance = float(contract.get("numeric_tolerance", 0))
    counts = {domain: 0 for domain in sorted(REQUIRED_DOMAINS)}
    drift_values: List[float] = []
    labeled = true_positive = true_negative = false_positive = false_negative = 0
    probability_claims = 0

    for case in cases:
        domain = str(case["domain"])
        counts[domain] += 1
        actual = _evaluate_case(case, contract)
        drift_values.extend(_compare_expected(actual, case["expected"], tolerance))
        probability_claims += validate_probability_claims(actual, contract)
        outcome = case.get("outcome")
        if not isinstance(outcome, dict) or not isinstance(outcome.get("observed_positive"), bool):
            continue
        prediction = outcome.get("prediction")
        if not isinstance(prediction, dict) or not prediction.get("path"):
            continue
        labeled += 1
        predicted_value = _path_value(actual, str(prediction["path"]))
        if "gte" in prediction:
            predicted_positive = float(predicted_value) >= float(prediction["gte"])
        elif "equals" in prediction:
            predicted_positive = predicted_value == prediction["equals"]
        else:
            raise OfflineEvaluationError(f"Outcome prediction is missing an operator: {case['case_id']}")
        observed_positive = outcome["observed_positive"]
        if predicted_positive and observed_positive:
            true_positive += 1
        elif predicted_positive:
            false_positive += 1
        elif observed_positive:
            false_negative += 1
        else:
            true_negative += 1

    outcome_coverage = labeled / len(cases)
    false_positive_rate = false_positive / (false_positive + true_negative) if false_positive + true_negative else None
    false_negative_rate = false_negative / (false_negative + true_positive) if false_negative + true_positive else None
    gates = contract["release_gates"]
    reasons = []
    if len(cases) < int(gates["minimum_total_cases"]):
        reasons.append("insufficient_total_outcome_sample")
    if any(count < int(gates["minimum_cases_per_domain"]) for count in counts.values()):
        reasons.append("insufficient_per_domain_outcome_sample")
    if outcome_coverage < float(gates["minimum_outcome_coverage"]):
        reasons.append("insufficient_outcome_coverage")
    if false_positive_rate is None or false_positive_rate > float(gates["maximum_false_positive_rate"]):
        reasons.append("false_positive_rate_not_approved")
    if false_negative_rate is None or false_negative_rate > float(gates["maximum_false_negative_rate"]):
        reasons.append("false_negative_rate_not_approved")
    if gates.get("require_calibrated_probability_claims") and SCORING_POLICY["calibration"]["status"] != "calibrated":
        reasons.append("probability_calibration_not_approved")

    return {
        "contract_id": contract["contract_id"],
        "policy": policy_metadata(),
        "cases_total": len(cases),
        "domain_case_counts": counts,
        "outcome_metrics": {
            "labeled_cases": labeled,
            "coverage": round(outcome_coverage, 6),
            "true_positive": true_positive,
            "true_negative": true_negative,
            "false_positive": false_positive,
            "false_negative": false_negative,
            "false_positive_rate": None if false_positive_rate is None else round(false_positive_rate, 6),
            "false_negative_rate": None if false_negative_rate is None else round(false_negative_rate, 6),
        },
        "drift_metrics": {
            "numeric_assertions": len(drift_values),
            "mean_absolute_drift": round(sum(drift_values) / len(drift_values), 8) if drift_values else 0.0,
            "maximum_absolute_drift": round(max(drift_values), 8) if drift_values else 0.0,
        },
        "calibration_metrics": {
            "status": SCORING_POLICY["calibration"]["status"],
            "numeric_probability_claims": probability_claims,
            "brier_score": None,
        },
        "release_gate": {
            "status": "approved" if not reasons else "human_review_only",
            "reasons": reasons,
        },
    }


if __name__ == "__main__":
    print(json.dumps(run_backtests(), indent=2, sort_keys=True))
