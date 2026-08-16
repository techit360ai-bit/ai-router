"""PostgreSQL persistence and feedback services for GSIS v2."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Iterable, Optional
from uuid import UUID, uuid4

from sqlalchemy import desc

from database_schema import (
    GsisV2Benchmark,
    GsisV2ConfigAudit,
    GsisV2Profile,
    GsisV2Recommendation,
    GsisV2RecommendationOutcome,
    GsisV2Snapshot,
    Project,
)
from gsis_v2 import activate_policy_override, compute_scorecard
from policy_registry import SCORING_POLICY


MODEL_VERSION = SCORING_POLICY["gsis_v2"]["model_version"]


def _uuid(value: Any) -> Any:
    if value is None or isinstance(value, UUID):
        return value
    try:
        return UUID(str(value))
    except (TypeError, ValueError):
        return value


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _scorecard_fields(scorecard: Dict[str, Any]) -> Dict[str, Any]:
    risk = scorecard.get("risk") or {}
    readiness = scorecard.get("readiness") or {}
    stage = scorecard.get("stage") or {}
    momentum = scorecard.get("momentum") or {}
    pmf = scorecard.get("pmf") or {}
    return {
        "model_version": str((scorecard.get("model") or {}).get("version") or MODEL_VERSION),
        "detected_stage": str(stage.get("detected_stage") or "BUILD"),
        "declared_stage": stage.get("declared_stage"),
        "gsis": scorecard.get("gsis"),
        "stage_health": scorecard.get("stage_health"),
        "momentum": momentum.get("score"),
        "pmf": pmf.get("score"),
        "risk_score": risk.get("score"),
        "risk_level": risk.get("level"),
        "readiness_score": readiness.get("score"),
        "readiness_status": readiness.get("status"),
        "confidence": scorecard.get("confidence"),
        "data_coverage": scorecard.get("data_coverage"),
        "health_classification": scorecard.get("health_classification"),
        "bottleneck": (scorecard.get("bottleneck") or {}).get("category"),
    }


def persist_scorecard(db: Any, project_id: Any, scorecard: Dict[str, Any], *, owner_id: Any = None, trigger: str = "api", create_recommendation: bool = True) -> Dict[str, Any]:
    """Upsert the latest profile and append one immutable snapshot."""
    project_id = _uuid(project_id)
    owner_id = _uuid(owner_id)
    fields = _scorecard_fields(scorecard)
    profile = db.query(GsisV2Profile).filter(GsisV2Profile.project_id == project_id).first()
    if profile is None:
        profile = GsisV2Profile(id=uuid4(), project_id=project_id, owner_id=owner_id)
        db.add(profile)
    for key, value in fields.items():
        setattr(profile, key, value)
    profile.scorecard = scorecard
    profile.calculated_at = _now()
    profile.updated_at = _now()
    snapshot = GsisV2Snapshot(
        id=uuid4(), project_id=project_id, owner_id=owner_id, gsis=fields["gsis"],
        detected_stage=fields["detected_stage"], momentum=fields["momentum"],
        risk_score=fields["risk_score"], readiness_score=fields["readiness_score"],
        confidence=fields["confidence"], data_coverage=fields["data_coverage"],
        model_version=fields["model_version"], trigger=trigger, scorecard=scorecard,
        snapshotted_at=_now(),
    )
    db.add(snapshot)
    recommendation = None
    if create_recommendation and scorecard.get("recommendation") and scorecard.get("bottleneck"):
        rec_data = scorecard["recommendation"]
        bottleneck = scorecard["bottleneck"]
        recommendation = GsisV2Recommendation(
            id=uuid4(), project_id=project_id, owner_id=owner_id,
            model_version=fields["model_version"], category=str(bottleneck.get("category") or "UNKNOWN"),
            action=str(rec_data.get("action") or "Collect stronger evidence."),
            success_metric=rec_data.get("success_metric"), expected_impact=rec_data.get("expected_impact"),
            confidence=rec_data.get("confidence"), time_horizon_days=rec_data.get("time_horizon_days"),
            status="recommended", created_at=_now(), updated_at=_now(),
        )
        db.add(recommendation)
    db.commit()
    return {"profile": profile, "snapshot": snapshot, "recommendation": recommendation}


def score_and_persist(db: Any, project_id: Any, payload: Dict[str, Any], *, owner_id: Any = None, trigger: str = "api") -> Dict[str, Any]:
    payload = {**payload, "startup_id": str(project_id)}
    scorecard = compute_scorecard(payload)
    persist_scorecard(db, project_id, scorecard, owner_id=owner_id, trigger=trigger)
    return scorecard


def scorecard_for_project(db: Any, project_id: Any, *, role: str = "founder") -> Optional[Dict[str, Any]]:
    profile = db.query(GsisV2Profile).filter(GsisV2Profile.project_id == _uuid(project_id)).first()
    if profile is None:
        return None
    scorecard = dict(profile.scorecard or {})
    if role == "feed":
        return {key: scorecard.get(key) for key in ("startup_id", "model", "evaluated_at", "gsis", "stage", "momentum")}
    return scorecard


def scorecard_history(db: Any, project_id: Any, limit: int = 90) -> list[Dict[str, Any]]:
    rows = db.query(GsisV2Snapshot).filter(GsisV2Snapshot.project_id == _uuid(project_id)).order_by(desc(GsisV2Snapshot.snapshotted_at)).limit(min(max(limit, 1), 365)).all()
    return [{"id": str(row.id), "project_id": str(row.project_id), "gsis": row.gsis, "stage": row.detected_stage, "momentum": row.momentum, "risk_score": row.risk_score, "readiness": row.readiness_score, "confidence": row.confidence, "data_coverage": row.data_coverage, "trigger": row.trigger, "model_version": row.model_version, "snapshotted_at": row.snapshotted_at.isoformat() if row.snapshotted_at else None} for row in rows]


def list_recommendations(db: Any, project_id: Any, limit: int = 20) -> list[Dict[str, Any]]:
    rows = db.query(GsisV2Recommendation).filter(GsisV2Recommendation.project_id == _uuid(project_id)).order_by(desc(GsisV2Recommendation.created_at)).limit(min(max(limit, 1), 100)).all()
    return [{"id": str(row.id), "project_id": str(row.project_id), "category": row.category, "action": row.action, "success_metric": row.success_metric, "expected_impact": row.expected_impact, "confidence": row.confidence, "time_horizon_days": row.time_horizon_days, "task_id": row.task_id, "status": row.status, "created_at": row.created_at.isoformat() if row.created_at else None} for row in rows]


def record_recommendation_outcome(db: Any, recommendation_id: Any, payload: Dict[str, Any]) -> Dict[str, Any]:
    recommendation = db.query(GsisV2Recommendation).filter(GsisV2Recommendation.id == _uuid(recommendation_id)).first()
    if recommendation is None:
        raise ValueError("recommendation_not_found")
    outcome = db.query(GsisV2RecommendationOutcome).filter(GsisV2RecommendationOutcome.recommendation_id == recommendation.id).first()
    if outcome is None:
        outcome = GsisV2RecommendationOutcome(id=uuid4(), recommendation_id=recommendation.id, project_id=recommendation.project_id)
        db.add(outcome)
    outcome.metric = str(payload.get("metric") or recommendation.success_metric or "unknown")
    outcome.baseline_value = payload.get("baseline_value")
    outcome.observed_value = payload.get("observed_value")
    outcome.expected_value = payload.get("expected_value")
    outcome.outcome = str(payload.get("outcome") or "observed")
    outcome.evidence = dict(payload.get("evidence") or {})
    outcome.observed_at = _now()
    recommendation.outcome_id = outcome.id
    recommendation.task_id = payload.get("task_id") or recommendation.task_id
    recommendation.status = "measured"
    recommendation.updated_at = _now()
    db.commit()
    from production_calibration import record_outcome
    baseline = outcome.baseline_value
    observed = outcome.observed_value
    observed_positive = payload.get("observed_positive")
    if not isinstance(observed_positive, bool) and baseline is not None and observed is not None:
        observed_positive = float(observed) > float(baseline)
    record_outcome(db, {
        "decision_id": str(recommendation.id),
        "domain": "gsis_v2",
        "policy_id": SCORING_POLICY["policy_id"],
        "predicted_score": (recommendation.confidence or 0) * 100,
        "predicted_probability": recommendation.confidence,
        "predicted_positive": str(recommendation.expected_impact or "").upper() in {"HIGH", "MEDIUM"},
        "observed_positive": observed_positive,
        "source": str(payload.get("source") or "verified_platform_event"),
        "evidence": outcome.evidence,
    })
    return {"id": str(outcome.id), "recommendation_id": str(recommendation.id), "project_id": str(outcome.project_id), "metric": outcome.metric, "baseline_value": outcome.baseline_value, "observed_value": outcome.observed_value, "expected_value": outcome.expected_value, "outcome": outcome.outcome, "observed_at": outcome.observed_at.isoformat()}


def save_benchmark(db: Any, payload: Dict[str, Any], *, changed_by: Any = None) -> Dict[str, Any]:
    required = ("metric", "stage", "source")
    if any(not str(payload.get(key) or "").strip() for key in required):
        raise ValueError("metric, stage, and source are required")
    row = GsisV2Benchmark(id=uuid4(), metric=str(payload["metric"]), stage=str(payload["stage"]).upper(), business_model=payload.get("business_model"), industry=payload.get("industry"), geography=payload.get("geography"), sample_size=int(payload.get("sample_size") or 0), p25=payload.get("p25"), median=payload.get("median"), p75=payload.get("p75"), source=str(payload["source"]), as_of=payload.get("as_of"), is_active=bool(payload.get("is_active", True)), created_at=_now(), updated_at=_now())
    db.add(row)
    db.commit()
    return {"id": str(row.id), "metric": row.metric, "stage": row.stage, "business_model": row.business_model, "industry": row.industry, "geography": row.geography, "sample_size": row.sample_size, "p25": row.p25, "median": row.median, "p75": row.p75, "source": row.source, "as_of": row.as_of.isoformat() if row.as_of else None, "is_active": row.is_active}


def list_benchmarks(db: Any, *, stage: Optional[str] = None, metric: Optional[str] = None) -> list[Dict[str, Any]]:
    query = db.query(GsisV2Benchmark).filter(GsisV2Benchmark.is_active.is_(True))
    if stage:
        query = query.filter(GsisV2Benchmark.stage == stage.upper())
    if metric:
        query = query.filter(GsisV2Benchmark.metric == metric)
    return [{"id": str(row.id), "metric": row.metric, "stage": row.stage, "business_model": row.business_model, "industry": row.industry, "geography": row.geography, "sample_size": row.sample_size, "p25": row.p25, "median": row.median, "p75": row.p75, "source": row.source, "as_of": row.as_of.isoformat() if row.as_of else None} for row in query.order_by(desc(GsisV2Benchmark.updated_at)).limit(500).all()]


def audit_config(db: Any, payload: Dict[str, Any], *, changed_by: Any = None) -> Dict[str, Any]:
    version = str(payload.get("version") or "")
    config = payload.get("config")
    if not version or not isinstance(config, dict):
        raise ValueError("version and config are required")
    active = activate_policy_override(config)
    row = GsisV2ConfigAudit(id=uuid4(), version=version, config=config, changed_by=_uuid(changed_by), reason=payload.get("reason"), created_at=_now())
    db.add(row)
    db.commit()
    return {"id": str(row.id), "version": row.version, "config": row.config, "active_policy": active, "reason": row.reason, "created_at": row.created_at.isoformat()}


def activate_latest_config(db: Any) -> Optional[Dict[str, Any]]:
    row = db.query(GsisV2ConfigAudit).order_by(desc(GsisV2ConfigAudit.created_at)).first()
    return activate_policy_override(row.config) if row is not None else None
