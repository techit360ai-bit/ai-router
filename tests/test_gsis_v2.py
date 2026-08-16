"""Stage-aware GSIS v2 deterministic scoring contracts."""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ai_router_core import ScoringEngine
from gsis_v2 import project_scorecard


NOW = "2026-08-16T10:00:00Z"


def metric(score, *, level=4, previous=None, observed_at=NOW, status="observed"):
    result = {
        "score": score,
        "status": status,
        "evidence_level": level,
        "source": "test",
        "observed_at": observed_at,
    }
    if previous is not None:
        result["previous_score"] = previous
    return result


def test_build_model_does_not_require_revenue() -> None:
    result = ScoringEngine.compute_gsis_v2({
        "startup_id": "build-1",
        "declared_stage": "BUILD",
        "evaluated_at": NOW,
        "metrics": {
            "problem": metric(82),
            "customer_validation": metric(70),
            "solution": metric(76),
            "team": metric(84),
            "product_progress": metric(45),
            "market": metric(75),
            "business_model": metric(62),
            "execution": metric(80, previous=70),
        },
    })

    assert result["stage"]["detected_stage"] == "BUILD"
    assert result["stage_health"] > 70
    assert result["data_coverage"] == 1.0
    assert "revenue" not in result["components"]
    assert result["pmf"]["status"] == "NOT_APPLICABLE"


def test_stage_detection_uses_evidence_over_declaration() -> None:
    result = ScoringEngine.compute_gsis_v2({
        "declared_stage": "GROWTH",
        "evaluated_at": NOW,
        "metrics": {
            "product_available": {"value": True, "status": "observed", "evidence_level": 3},
            "active_users": {"value": 24, "status": "observed", "evidence_level": 3},
            "revenue": {"value": 500, "status": "observed", "evidence_level": 4},
            "retention": metric(32),
            "repeatable_acquisition": metric(35),
        },
    })

    assert result["stage"]["detected_stage"] == "LAUNCH"
    assert result["stage"]["matches_declaration"] is False
    assert "repeatable growth engine" in result["stage"]["reason"]


def test_growth_readiness_is_blocked_by_critical_retention_gate() -> None:
    high = {
        "revenue_growth": metric(90),
        "customer_growth": metric(88),
        "retention": metric(52),
        "unit_economics": metric(85),
        "acquisition_efficiency": metric(85),
        "repeatable_acquisition": metric(80),
        "expansion": metric(82),
        "market_position": metric(80),
        "operations": metric(85),
        "moat": metric(78),
        "capital_efficiency": metric(82),
        "revenue": {"value": 25000, "status": "observed", "evidence_level": 4},
    }
    result = ScoringEngine.compute_gsis_v2({"evaluated_at": NOW, "metrics": high})

    assert result["stage"]["detected_stage"] == "GROWTH"
    assert result["stage_health"] > 75
    assert result["readiness"]["status"] == "APPROACHING"
    assert any(gate["metric"] == "RETENTION" for gate in result["readiness"]["blocking_requirements"])


def test_missing_metrics_reduce_coverage_instead_of_becoming_zero() -> None:
    result = ScoringEngine.compute_gsis_v2({
        "evaluated_at": NOW,
        "metrics": {"problem": metric(80), "team": metric(90)},
    })

    assert result["stage"]["detected_stage"] == "BUILD"
    assert result["stage_health"] == 84
    assert 0 < result["data_coverage"] < 0.5
    assert result["confidence"] > 0


def test_evidence_quality_and_freshness_change_confidence_not_score() -> None:
    current = ScoringEngine.compute_gsis_v2({
        "evaluated_at": NOW,
        "metrics": {"problem": metric(75, level=5)},
    })
    stale_assertion = ScoringEngine.compute_gsis_v2({
        "evaluated_at": NOW,
        "metrics": {"problem": metric(75, level=1, observed_at="2025-01-01T00:00:00Z")},
    })

    assert current["stage_health"] == stale_assertion["stage_health"] == 75
    assert current["confidence"] > stale_assertion["confidence"]


def test_stage_aware_inactivity_decay_is_stricter_after_launch() -> None:
    payload = {
        "evaluated_at": NOW,
        "last_activity_at": "2026-07-27T10:00:00Z",
        "metrics": {"problem": metric(70)},
    }
    build = ScoringEngine.compute_gsis_v2(payload)
    launch = ScoringEngine.compute_gsis_v2({
        **payload,
        "metrics": {
            "product_available": {"value": True, "status": "observed", "evidence_level": 3},
            "activation": metric(70),
        },
    })

    assert build["momentum"]["score"] > launch["momentum"]["score"]


def test_feed_projection_cannot_leak_sensitive_intelligence() -> None:
    scorecard = ScoringEngine.compute_gsis_v2({
        "startup_id": "feed-1",
        "evaluated_at": NOW,
        "metrics": {"problem": metric(70), "team": metric(80)},
    })
    feed = project_scorecard(scorecard, "feed")

    assert set(feed) == {"startup_id", "model", "evaluated_at", "gsis", "stage", "momentum"}
    for sensitive in ("risk", "components", "recommendation", "bottleneck", "readiness", "legacy"):
        assert sensitive not in feed


def test_legacy_gsis_engine_remains_unchanged() -> None:
    legacy = ScoringEngine.compute_gsis(80, 70, 60, 50, 40, 30, 20, 10, 100)

    assert legacy["gsis"] == 53.5
    assert legacy["classification"] == "Early -- needs focus"
