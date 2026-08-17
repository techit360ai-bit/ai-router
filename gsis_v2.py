"""Deterministic, stage-aware GSIS v2 scoring and role projections."""

from __future__ import annotations

import math
from copy import deepcopy
from threading import RLock
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, Optional, Tuple

from policy_registry import SCORING_POLICY, policy_metadata


POLICY = SCORING_POLICY["gsis_v2"]
_POLICY_LOCK = RLock()
SUPPORTED_STAGES = {"BUILD", "LAUNCH", "GROWTH"}
STATUS_FACTORS = {
    "observed": 1.0,
    "derived": 0.8,
    "estimated": 0.55,
    "ai_inferred": 0.4,
    "unknown": 0.0,
}


def activate_policy_override(overrides: Dict[str, Any]) -> Dict[str, Any]:
    """Atomically activate validated admin overrides without rewriting scoring code."""
    if not isinstance(overrides, dict):
        raise ValueError("GSIS configuration must be an object")

    def merge(base: Dict[str, Any], incoming: Dict[str, Any]) -> Dict[str, Any]:
        result = deepcopy(base)
        for key, value in incoming.items():
            if isinstance(value, dict) and isinstance(result.get(key), dict):
                result[key] = merge(result[key], value)
            else:
                result[key] = deepcopy(value)
        return result

    global POLICY
    candidate = merge(POLICY, overrides)
    for stage in SUPPORTED_STAGES:
        weights = candidate.get("stage_models", {}).get(stage, {})
        if not weights or abs(sum(float(value) for value in weights.values()) - 1.0) > 1e-6:
            raise ValueError(f"{stage} weights must sum to 1")
    with _POLICY_LOCK:
        POLICY = candidate
        SCORING_POLICY["gsis_v2"] = candidate
    return deepcopy(candidate)


def _clamp(value: float, minimum: float = 0.0, maximum: float = 100.0) -> float:
    return min(maximum, max(minimum, float(value)))


def _number(value: Any) -> Optional[float]:
    if isinstance(value, bool):
        return 1.0 if value else 0.0
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None
    return result if math.isfinite(result) else None


def _time(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)


def _now(payload: Dict[str, Any]) -> datetime:
    return _time(payload.get("evaluated_at")) or datetime.now(timezone.utc)


def _record(metrics: Dict[str, Any], key: str) -> Optional[Dict[str, Any]]:
    value = metrics.get(key)
    if value is None:
        return None
    if isinstance(value, dict):
        return value
    return {"value": value, "status": "observed", "evidence_level": 3}


def _raw(metrics: Dict[str, Any], *keys: str) -> Optional[float]:
    for key in keys:
        record = _record(metrics, key)
        if record and str(record.get("status", "observed")).lower() != "unknown":
            value = _number(record.get("value", record.get("score")))
            if value is not None:
                return value
    return None


def _normalize_value(key: str, value: float) -> float:
    rate_keys = {
        "activation", "retention", "organic_growth", "referrals", "willingness_to_pay",
        "customer_satisfaction", "expansion", "churn", "repeatable_acquisition",
        "revenue_growth", "customer_growth", "gross_margin", "conversion_to_paid",
    }
    count_keys = {"active_users", "customers", "design_partners", "pilots", "team_size"}
    money_keys = {"revenue", "mrr", "arr"}
    if key in rate_keys:
        return _clamp(value * 100 if 0 <= value <= 1 else value)
    if key in count_keys:
        return _clamp(math.log10(max(0.0, value) + 1.0) * 25.0)
    if key in money_keys:
        return _clamp(math.log10(max(0.0, value) + 1.0) * 18.0)
    if key == "ltv_cac":
        return _clamp(value / 5.0 * 100.0)
    if key == "cac_payback_months":
        return _clamp(100.0 - max(0.0, value - 3.0) * 5.0)
    return _clamp(value * 100 if 0 <= value <= 1 else value)


def _freshness(observed_at: Optional[datetime], evaluated_at: datetime) -> Tuple[str, float, Optional[int]]:
    if observed_at is None:
        return "UNKNOWN", 0.6, None
    age_days = max(0, (evaluated_at - observed_at).days)
    policy = POLICY["freshness"]
    if age_days <= policy["current_days"]:
        return "CURRENT", 1.0, age_days
    if age_days <= policy["recent_days"]:
        return "RECENT", float(policy["recent_factor"]), age_days
    if age_days <= policy["stale_days"]:
        return "STALE", float(policy["stale_factor"]), age_days
    return "STALE", max(0.15, float(policy["stale_factor"]) * 0.5), age_days


def _metric(metrics: Dict[str, Any], key: str, evaluated_at: datetime) -> Optional[Dict[str, Any]]:
    record = _record(metrics, key)
    if not record:
        return None
    status = str(record.get("status", "observed")).lower()
    if status not in STATUS_FACTORS or status == "unknown":
        return None
    raw = _number(record.get("score"))
    if raw is None:
        raw = _number(record.get("value"))
        if raw is None:
            return None
        score = _normalize_value(key, raw)
    else:
        score = _clamp(raw)
    level = min(5, max(1, int(_number(record.get("evidence_level")) or 1)))
    observed_at = _time(record.get("observed_at"))
    freshness, freshness_factor, data_age = _freshness(observed_at, evaluated_at)
    confidence = (
        float(POLICY["evidence_level_factors"][str(level)])
        * STATUS_FACTORS[status]
        * freshness_factor
    )
    previous = _number(record.get("previous_score"))
    if previous is None:
        previous_raw = _number(record.get("previous_value"))
        previous = _normalize_value(key, previous_raw) if previous_raw is not None else None
    change = None if previous is None else round(score - previous, 2)
    trend = "UNKNOWN" if change is None else "IMPROVING" if change > 2 else "DECLINING" if change < -2 else "STABLE"
    return {
        "key": key,
        "score": round(score, 2),
        "confidence": round(confidence, 4),
        "status": status.upper(),
        "evidence_level": level,
        "source": record.get("source") or "unspecified",
        "observed_at": observed_at.isoformat() if observed_at else None,
        "data_age_days": data_age,
        "freshness": freshness,
        "previous_score": None if previous is None else round(previous, 2),
        "change": change,
        "trend": trend,
    }


def _weighted(values: Iterable[Tuple[Optional[float], float]]) -> Optional[float]:
    observed = [(float(value), float(weight)) for value, weight in values if value is not None]
    weight_sum = sum(weight for _, weight in observed)
    if not observed or weight_sum <= 0:
        return None
    return round(sum(value * weight for value, weight in observed) / weight_sum, 2)


def _detect_stage(payload: Dict[str, Any], metrics: Dict[str, Any]) -> Dict[str, Any]:
    declared = str(payload.get("declared_stage") or "UNKNOWN").upper()
    if declared == "IDEA":
        declared_supported = "BUILD"
    else:
        declared_supported = declared if declared in SUPPORTED_STAGES else None
    rules = POLICY["stage_detection"]
    product = _raw(metrics, "product", "product_progress", "mvp_status") or 0
    users = _raw(metrics, "active_users") or 0
    revenue = _raw(metrics, "revenue", "mrr") or 0
    retention = _raw(metrics, "retention") or 0
    repeatable = _raw(metrics, "repeatable_acquisition", "acquisition") or 0
    product_available = bool(_raw(metrics, "product_available") or product >= rules["launch_min_product"])
    growth_matches = [
        retention >= rules["growth_min_retention"],
        repeatable >= rules["growth_min_repeatable_acquisition"],
        revenue >= rules["growth_min_revenue"],
    ]
    if all(growth_matches):
        detected = "GROWTH"
        reason = "Retention, revenue, and repeatable acquisition meet growth-stage evidence thresholds."
        matched = 3
    elif product_available or users >= rules["launch_min_users"] or revenue > 0:
        detected = "LAUNCH"
        reason = "A usable product or market activity exists, but the repeatable growth engine is not yet evidenced."
        matched = sum([product_available, users > 0, revenue > 0])
    else:
        detected = "BUILD"
        reason = "Evidence currently supports problem, solution, and product development work before market launch."
        matched = 1 + int(product > 0)
    confidence = min(0.95, 0.55 + matched * 0.10)
    return {
        "declared_stage": declared,
        "detected_stage": detected,
        "confidence": round(confidence, 2),
        "matches_declaration": declared_supported == detected if declared_supported else None,
        "reason": reason,
    }


def _component(metrics: Dict[str, Any], key: str, evaluated_at: datetime, pmf: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if key == "pmf" and pmf and pmf.get("score") is not None:
        return {
            "key": key,
            "score": pmf["score"],
            "confidence": pmf["confidence"],
            "status": "DERIVED",
            "evidence_level": None,
            "source": "gsis_v2_pmf",
            "observed_at": evaluated_at.isoformat(),
            "data_age_days": 0,
            "freshness": "CURRENT",
            "previous_score": None,
            "change": None,
            "trend": "UNKNOWN",
        }
    aliases = {
        "product": ("product", "product_progress"),
        "customer_validation": ("customer_validation", "active_users", "design_partners", "pilots"),
        "team": ("team", "team_size"),
        "execution": ("execution", "learning_velocity", "execution_velocity"),
        "activation": ("activation", "active_users"),
        "acquisition": ("acquisition", "active_users"),
        "monetization": ("monetization", "conversion_to_paid", "revenue", "mrr"),
        "acquisition_efficiency": ("acquisition_efficiency", "repeatable_acquisition"),
        "unit_economics": ("unit_economics", "ltv_cac"),
    }
    for candidate in aliases.get(key, (key,)):
        result = _metric(metrics, candidate, evaluated_at)
        if result:
            return {**result, "key": key}
    return None


def _pmf(stage: str, metrics: Dict[str, Any], evaluated_at: datetime) -> Dict[str, Any]:
    if stage == "BUILD":
        return {"score": None, "confidence": 0.0, "status": "NOT_APPLICABLE", "interpretation": "N/A"}
    observed = []
    confidences = []
    for key, weight in POLICY["pmf_metrics"].items():
        if key == "churn_inverse":
            metric = _metric(metrics, "churn", evaluated_at)
            value = None if metric is None else 100.0 - metric["score"]
        else:
            metric = _metric(metrics, key, evaluated_at)
            value = None if metric is None else metric["score"]
        observed.append((value, weight))
        if metric:
            confidences.append((metric["confidence"], weight))
    score = _weighted(observed)
    confidence = _weighted(confidences) or 0.0
    if score is None:
        interpretation = "No Evidence"
    elif score >= 91:
        interpretation = "Exceptional PMF"
    elif score >= 76:
        interpretation = "Strong PMF"
    elif score >= 61:
        interpretation = "Emerging PMF"
    elif score >= 41:
        interpretation = "Early Traction"
    elif score >= 21:
        interpretation = "Problem Validation"
    else:
        interpretation = "No Evidence"
    return {"score": score, "confidence": round(confidence, 4), "status": "AVAILABLE" if score is not None else "UNKNOWN", "interpretation": interpretation}


def _momentum(stage: str, metrics: Dict[str, Any], payload: Dict[str, Any], evaluated_at: datetime) -> Dict[str, Any]:
    changes = []
    for key in metrics:
        metric = _metric(metrics, key, evaluated_at)
        if metric and metric["change"] is not None:
            changes.append(metric["change"] * metric["confidence"])
    trend_value = sum(changes) / max(1, len(changes))
    decay_policy = POLICY["decay"][stage]
    expected_days = max(1, int(payload.get("expected_activity_days") or decay_policy["expected_activity_days"]))
    last_activity = _time(payload.get("last_activity_at"))
    inactive_days = max(0, (evaluated_at - last_activity).days) if last_activity else 0
    overdue_days = max(0, inactive_days - expected_days)
    decay_factor = math.exp(-float(decay_policy["exponent"]) * overdue_days)
    inactivity_penalty = 20.0 * (1.0 - decay_factor)
    score = round(_clamp(trend_value / 2.5 - inactivity_penalty, -25.0, 25.0), 1)
    direction = "IMPROVING" if score > 2 else "DECLINING" if score < -2 else "STABLE"
    activity = "DANGEROUS_INACTIVITY" if overdue_days > expected_days else "HEALTHY_LOW_ACTIVITY" if inactive_days > expected_days else "ACTIVE"
    return {"score": score, "direction": direction, "activity_status": activity, "inactive_days": inactive_days, "expected_activity_days": expected_days, "decay_factor": round(decay_factor, 4), "evidence_available": bool(changes or last_activity)}


def _risk(components: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    radar = {}
    for category, keys in POLICY["risk_categories"].items():
        score = _weighted((components.get(key, {}).get("score"), 1.0) for key in keys)
        risk_score = None if score is None else round(100.0 - score, 2)
        radar[category] = {"score": risk_score, "status": "UNKNOWN" if risk_score is None else "AVAILABLE"}
    observed = [(value["score"], 1.0) for value in radar.values()]
    score = _weighted(observed)
    levels = POLICY["risk_levels"]
    if score is None:
        level = "UNKNOWN"
    elif score >= levels["critical"]:
        level = "CRITICAL"
    elif score >= levels["high"]:
        level = "HIGH"
    elif score >= levels["medium"]:
        level = "MEDIUM"
    else:
        level = "LOW"
    ranked = sorted(((name, value["score"]) for name, value in radar.items() if value["score"] is not None), key=lambda row: row[1], reverse=True)
    primary = ranked[0][0].upper() if ranked else "UNKNOWN"
    secondary = ranked[1][0].upper() if len(ranked) > 1 else "UNKNOWN"
    return {"score": score, "level": level, "primary_risk": primary, "secondary_risk": secondary, "trend": "UNKNOWN", "radar": radar}


def _readiness(stage: str, components: Dict[str, Dict[str, Any]], pmf: Dict[str, Any]) -> Dict[str, Any]:
    config = POLICY["readiness"][stage]
    values = []
    for key, weight in config["components"].items():
        value = pmf.get("score") if key == "pmf" else components.get(key, {}).get("score")
        values.append((value, weight))
    score = _weighted(values)
    blockers = []
    satisfied = []
    for key, minimum in config["critical_gates"].items():
        value = pmf.get("score") if key == "pmf" else components.get(key, {}).get("score")
        gate = {"metric": key.upper(), "minimum": minimum, "value": value}
        if value is None or value < minimum:
            blockers.append(gate)
        else:
            satisfied.append(gate)
    thresholds = config["thresholds"]
    if score is None or score < thresholds["approaching"]:
        status = "NOT_READY"
    elif blockers:
        status = "APPROACHING"
    elif score >= thresholds["advanced"]:
        status = "ADVANCED"
    elif score >= thresholds["ready"]:
        status = "READY"
    else:
        status = "APPROACHING"
    return {"next_stage": config["next_stage"], "score": score, "status": status, "blocking_requirements": blockers, "satisfied_gates": satisfied}


ACTIONS = {
    "problem": ("Validate the problem with qualified target customers.", "Complete 10 ICP interviews and document repeated pain signals."),
    "customer_validation": ("Strengthen customer evidence.", "Convert at least 3 qualified interviews into active design partners."),
    "product": ("Complete the core value workflow.", "Ship and test the smallest usable workflow with target users."),
    "activation": ("Improve time to first value.", "Instrument the aha event and remove the largest onboarding drop-off."),
    "retention": ("Diagnose and improve retention.", "Interview 10 churned users and test one onboarding or product intervention."),
    "acquisition": ("Prove one repeatable acquisition channel.", "Run a focused channel experiment with a defined qualified-customer target."),
    "monetization": ("Validate willingness to pay.", "Test a priced offer with qualified active users and measure conversion."),
    "unit_economics": ("Improve unit economics before scaling.", "Reduce CAC or improve gross margin until payback is sustainable."),
    "operations": ("Remove the operational scaling constraint.", "Automate the highest-volume manual onboarding or support workflow."),
    "team": ("Close the highest-impact capability gap.", "Assign an owner or recruit the missing capability for the current milestone."),
}


def _bottleneck(stage: str, components: Dict[str, Dict[str, Any]], readiness: Dict[str, Any]) -> Dict[str, Any]:
    weights = POLICY["stage_models"][stage]
    candidates = []
    for key, weight in weights.items():
        component = components.get(key)
        if component:
            impact = (100.0 - component["score"]) * float(weight)
            candidates.append((impact, key, component["score"], component["confidence"]))
    for blocker in readiness["blocking_requirements"]:
        key = blocker["metric"].lower()
        if blocker["value"] is None:
            candidates.append((25.0, key, None, 0.0))
    if not candidates:
        return {"category": "INSUFFICIENT_EVIDENCE", "severity": "UNKNOWN", "score": None}
    _, key, score, confidence = max(candidates, key=lambda row: row[0])
    severity = "HIGH" if score is None or score < 45 else "MEDIUM" if score < 65 else "LOW"
    return {"category": key.upper(), "severity": severity, "score": score, "confidence": round(confidence, 4)}


def _recommendation(bottleneck: Dict[str, Any]) -> Dict[str, Any]:
    key = str(bottleneck["category"]).lower()
    action, milestone = ACTIONS.get(key, ("Collect stronger evidence for the primary constraint.", "Add one current behavioral or commercial observation."))
    confidence = bottleneck.get("confidence") or 0.35
    return {"action": action, "next_milestone": milestone, "expected_impact": "HIGH" if bottleneck["severity"] == "HIGH" else "MEDIUM", "time_horizon_days": 14, "owner": "Founder", "confidence": round(confidence, 2), "success_metric": milestone}


def _health_classification(gsis: Optional[float], momentum: float, risk_score: Optional[float]) -> str:
    if gsis is None:
        return "UNKNOWN"
    if risk_score is not None and risk_score >= 75:
        return "CRITICAL"
    if momentum <= -10:
        return "STAGNATING"
    for threshold, label in POLICY["health_tiers"]:
        if gsis >= threshold:
            return label
    return "AT_RISK"


def _prediction_estimates(stage: str, readiness: Dict[str, Any], momentum: Dict[str, Any], confidence: float) -> Dict[str, Any]:
    """Return non-calibrated estimates until verified outcome data approves probabilities."""
    readiness_score = readiness.get("score")
    momentum_score = float(momentum.get("score") or 0)
    base = None if readiness_score is None else _clamp(float(readiness_score) + momentum_score)
    band = "UNKNOWN" if base is None else "HIGH" if base >= 75 else "MEDIUM" if base >= 50 else "LOW"
    return {
        "calibration_status": "not_calibrated",
        "launch_readiness_30d": {"estimate": band if stage == "BUILD" else "N/A", "probability": None, "confidence": round(confidence, 4), "label": "AI_ESTIMATE"},
        "growth_readiness_90d": {"estimate": band if stage in {"BUILD", "LAUNCH"} else "N/A", "probability": None, "confidence": round(confidence, 4), "label": "AI_ESTIMATE"},
        "stagnation": {"estimate": "HIGH" if momentum_score <= -10 else "MEDIUM" if momentum_score < 0 else "LOW", "probability": None, "confidence": round(confidence, 4), "label": "AI_ESTIMATE"},
    }


def compute_scorecard(payload: Dict[str, Any]) -> Dict[str, Any]:
    metrics = payload.get("metrics") if isinstance(payload.get("metrics"), dict) else {}
    evaluated_at = _now(payload)
    stage = _detect_stage(payload, metrics)
    detected = stage["detected_stage"]
    pmf = _pmf(detected, metrics, evaluated_at)
    components = {}
    for key in set(POLICY["stage_models"][detected]) | set(POLICY["readiness"][detected]["components"]):
        component = _component(metrics, key, evaluated_at, pmf)
        if component:
            components[key] = component
    stage_weights = POLICY["stage_models"][detected]
    stage_health = _weighted((components.get(key, {}).get("score"), weight) for key, weight in stage_weights.items())
    coverage = round(sum(weight for key, weight in stage_weights.items() if key in components), 4)
    confidence = _weighted((components.get(key, {}).get("confidence"), weight) for key, weight in stage_weights.items()) or 0.0
    momentum = _momentum(detected, metrics, payload, evaluated_at)
    risk = _risk(components)
    readiness = _readiness(detected, components, pmf)
    globals_config = POLICY["global_weights"]
    gsis = _weighted([
        (stage_health, globals_config["stage_health"]),
        (50.0 + momentum["score"] * 2.0 if momentum["evidence_available"] else None, globals_config["momentum"]),
        (readiness["score"], globals_config["readiness"]),
        (None if risk["score"] is None else 100.0 - risk["score"], globals_config["risk_inverse"]),
    ])
    bottleneck = _bottleneck(detected, components, readiness)
    recommendation = _recommendation(bottleneck)
    strongest = max(components.values(), key=lambda row: row["score"], default=None)
    weakest = min(components.values(), key=lambda row: row["score"], default=None)
    scorecard = {
        "startup_id": payload.get("startup_id"),
        "model": {"name": "GSIS", "version": POLICY["model_version"], "policy": policy_metadata(), "legacy_compatible": True},
        "evaluated_at": evaluated_at.isoformat(),
        "stage": stage,
        "gsis": gsis,
        "stage_health": stage_health,
        "confidence": round(confidence, 4),
        "data_coverage": coverage,
        "health_classification": _health_classification(gsis, momentum["score"], risk["score"]),
        "momentum": momentum,
        "pmf": pmf,
        "risk": risk,
        "readiness": readiness,
        "components": components,
        "strongest_area": None if strongest is None else {"category": strongest["key"].upper(), "score": strongest["score"]},
        "weakest_area": None if weakest is None else {"category": weakest["key"].upper(), "score": weakest["score"]},
        "bottleneck": bottleneck,
        "recommendation": recommendation,
        "predictions": _prediction_estimates(detected, readiness, momentum, confidence),
        "legacy": {"gsis": payload.get("legacy_gsis"), "model": "GSIS v1" if payload.get("legacy_gsis") is not None else None},
    }
    return scorecard


def project_scorecard(scorecard: Dict[str, Any], role: str) -> Dict[str, Any]:
    role = role.lower()
    common = {
        "startup_id": scorecard["startup_id"],
        "model": scorecard["model"],
        "evaluated_at": scorecard["evaluated_at"],
        "gsis": scorecard["gsis"],
        "stage": scorecard["stage"],
        "stage_health": scorecard["stage_health"],
        "momentum": scorecard["momentum"],
        "pmf": scorecard["pmf"],
        "confidence": scorecard["confidence"],
        "data_coverage": scorecard["data_coverage"],
        "health_classification": scorecard["health_classification"],
    }
    if role == "feed":
        return {key: common[key] for key in ("startup_id", "model", "evaluated_at", "gsis", "stage", "momentum")}
    if role == "investor":
        return {**common, "risk": scorecard["risk"], "readiness": scorecard["readiness"], "components": scorecard["components"], "strongest_area": scorecard["strongest_area"], "weakest_area": scorecard["weakest_area"], "bottleneck": scorecard["bottleneck"], "predictions": scorecard["predictions"], "legacy": scorecard["legacy"]}
    if role == "founder":
        return {**common, "risk": {key: scorecard["risk"][key] for key in ("score", "level", "primary_risk", "trend")}, "readiness": scorecard["readiness"], "strongest_area": scorecard["strongest_area"], "weakest_area": scorecard["weakest_area"], "bottleneck": scorecard["bottleneck"], "recommendation": scorecard["recommendation"], "predictions": scorecard["predictions"], "components": scorecard["components"], "legacy": scorecard["legacy"]}
    return scorecard
