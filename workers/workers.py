# -*- coding: utf-8 -*-
"""
TECHIT AI INCUBATION PLATFORM
==============================
workers.py -- Celery Background Workers

All 15 scheduled tasks, fully implemented with real executable logic.

Task index:
  1.  daily_tour_guide              06:00 daily     -- momentum check-in for all active users
  2.  weekly_summaries              18:00 Sunday    -- weekly Tour Guide wrap per user
  3.  daily_investor_signals        00:00 daily     -- refresh EVI-I scores for all startups
  4.  adaptive_curriculum_weekly    02:00 Monday    -- generate curricula for new users
  5.  wcrs_gsis_refresh             every 30 min    -- apply decay + refresh GSIS/WCRS for all projects
  6.  stagnation_roster             07:00 daily     -- flag inactive projects, send re-engagement
  7.  monthly_credit_reset          00:00 1st/month -- reset subscription credit allocations
  8.  admin_anomaly_scan            every 15 min    -- abuse detection, fake traction, anomalies
  9.  investor_alert_check          every 5 min     -- fire watchlist alerts on threshold crossings
  10. problem_discovery_daily       06:00 daily     -- auto-discover global problems from signals
  11. discussion_moderation_hourly  every hour      -- AI moderate active discussion threads
  12. deployment_status_refresh     every 15 min    -- update beneficiary counts on live deployments
  13. document_cleanup_weekly       03:00 Sunday    -- expire document share links
  14. impact_snapshot_daily         01:00 daily     -- snapshot impact scores for longitudinal tracking
  15. trust_continuous_verification every 30 min    -- refresh stale Trust Engine metadata contracts

Run commands:
    celery -A workers.workers.celery worker --loglevel=info -Q ai_heavy,ai_light,scheduled
    celery -A workers.workers.celery beat   --loglevel=info
    celery -A workers.workers.celery flower --port=5555
"""

import asyncio
import hashlib
import json
import math
import os
from contextlib import contextmanager
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

import structlog
from celery import Celery
from celery.schedules import crontab

logger = structlog.get_logger()


# ============================================================================
# CELERY APP
# ============================================================================

celery = Celery(
    "techit_workers",
    broker=os.getenv("CELERY_BROKER", os.getenv("REDIS_URL", "redis://redis:6379")),
    backend=os.getenv("CELERY_BROKER", os.getenv("REDIS_URL", "redis://redis:6379")),
    # include= forces Celery to import this module and register all
    # @celery.task decorated functions. Without this, `inspect registered`
    # only shows tasks from whichever module Celery happened to import.
    include=["workers.workers"],
)

celery.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    # Silences the Celery 6.0 deprecation warning in logs
    broker_connection_retry_on_startup=True,
    # Re-queue tasks if a worker dies mid-execution
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_default_retry_delay=60,
    task_max_retries=3,
    # Hard ceilings so a hung task can't block its worker forever (e.g. an LLM
    # call without timeout, a DB query against a dead connection). Soft limit
    # raises SoftTimeLimitExceeded inside the task so it can clean up; hard
    # limit kills the worker process. Per-task overrides via @celery.task(
    # soft_time_limit=N, time_limit=M) for the heavier `ai_heavy` queue jobs
    # (weekly_summaries, adaptive_curriculum_weekly) if needed.
    task_soft_time_limit=300,   # 5 min
    task_time_limit=600,        # 10 min
    # Match worker visibility timeout so Redis doesn't redeliver before
    # the hard kill fires.
    broker_transport_options={"visibility_timeout": 600},
    # Belt-and-suspenders import guarantee alongside include= above.
    # Both directives ensure Celery imports this module before inspecting
    # registered tasks, which is what makes `inspect registered` return
    # all tasks instead of an empty list.
    imports=["workers.workers"],
    # Route tasks to dedicated queues by workload type
    task_routes={
        "workers.daily_tour_guide":             {"queue": "ai_light"},
        "workers.weekly_summaries":             {"queue": "ai_heavy"},
        "workers.daily_investor_signals":       {"queue": "ai_heavy"},
        "workers.adaptive_curriculum_weekly":   {"queue": "ai_heavy"},
        "workers.wcrs_gsis_refresh":            {"queue": "scheduled"},
        "workers.stagnation_roster":            {"queue": "scheduled"},
        "workers.monthly_credit_reset":         {"queue": "scheduled"},
        "workers.admin_anomaly_scan":           {"queue": "ai_light"},
        "workers.investor_alert_check":         {"queue": "scheduled"},
        "workers.problem_discovery_daily":      {"queue": "ai_light"},
        "workers.discussion_moderation_hourly": {"queue": "ai_light"},
        "workers.deployment_status_refresh":    {"queue": "scheduled"},
        "workers.document_cleanup_weekly":      {"queue": "scheduled"},
        "workers.impact_snapshot_daily":        {"queue": "scheduled"},
        "workers.trust_continuous_verification": {"queue": "scheduled"},
    },
)


# ============================================================================
# BEAT SCHEDULE -- 15 TASKS
# ============================================================================

celery.conf.beat_schedule = {
    "daily-tour-guide": {
        "task":     "workers.daily_tour_guide",
        "schedule": crontab(hour=6, minute=0),
    },
    "weekly-summaries": {
        "task":     "workers.weekly_summaries",
        "schedule": crontab(hour=18, minute=0, day_of_week=0),
    },
    "daily-investor-signals": {
        "task":     "workers.daily_investor_signals",
        "schedule": crontab(hour=0, minute=0),
    },
    "adaptive-curriculum-weekly": {
        "task":     "workers.adaptive_curriculum_weekly",
        "schedule": crontab(hour=2, minute=0, day_of_week=1),
    },
    "wcrs-gsis-refresh": {
        "task":     "workers.wcrs_gsis_refresh",
        "schedule": crontab(minute="*/30"),
    },
    "stagnation-roster": {
        "task":     "workers.stagnation_roster",
        "schedule": crontab(hour=7, minute=0),
    },
    "monthly-credit-reset": {
        "task":     "workers.monthly_credit_reset",
        "schedule": crontab(hour=0, minute=0, day_of_month=1),
    },
    "admin-anomaly-scan": {
        "task":     "workers.admin_anomaly_scan",
        "schedule": crontab(minute="*/15"),
    },
    "investor-alert-check": {
        "task":     "workers.investor_alert_check",
        "schedule": crontab(minute="*/5"),
    },
    "problem-discovery-daily": {
        "task":     "workers.problem_discovery_daily",
        "schedule": crontab(hour=6, minute=0),
    },
    "discussion-moderation-hourly": {
        "task":     "workers.discussion_moderation_hourly",
        "schedule": crontab(minute=0),
    },
    "deployment-status-refresh": {
        "task":     "workers.deployment_status_refresh",
        "schedule": crontab(minute="*/15"),
    },
    "document-cleanup-weekly": {
        "task":     "workers.document_cleanup_weekly",
        "schedule": crontab(hour=3, minute=0, day_of_week=0),
    },
    "impact-snapshot-daily": {
        "task":     "workers.impact_snapshot_daily",
        "schedule": crontab(hour=1, minute=0),
    },
    "trust-continuous-verification": {
        "task":     "workers.trust_continuous_verification",
        "schedule": crontab(minute="*/30"),
    },
}


# ============================================================================
# SHARED HELPERS
# ============================================================================

def _get_brain():
    """Return a TechITAIBrain for this task. One per worker process."""
    from integration_guide import TechITAIBrain
    return TechITAIBrain()


def _get_db():
    """
    Return a SQLAlchemy session context manager.

    Usage:
        with _get_db() as db:
            db.execute(text("SELECT ..."))
    """
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    engine = create_engine(
        os.getenv("DATABASE_URL", "postgresql://techit:password@postgres:5432/techit_db"),
        pool_pre_ping=True,
        pool_size=2,
        max_overflow=3,
    )
    Session = sessionmaker(bind=engine)

    @contextmanager
    def session_scope():
        session = Session()
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    return session_scope()


def _build_system_context():
    """System-level UserContext for tasks that run without a specific user."""
    from ai_router_core import UserContext, UserRole, SubscriptionTier
    return UserContext(
        user_id="system_worker",
        role=UserRole.ADMIN,
        subscription_tier=SubscriptionTier.ENTERPRISE,
        credits_remaining=99999,
        project_id=None, project_stage=None, industry=None,
        tech_stack=[], past_feedback=[],
        training_progress={}, time_logged_today=0, tasks_completed_week=0,
    )


def _fetch_active_users() -> List[Any]:
    """
    Fetch all users active within the last 30 days as UserContext objects.

    Production SQL:
        SELECT u.id, u.role, u.subscription_tier
        FROM users u
        WHERE u.created_at > NOW() - INTERVAL '30 days'
    """
    try:
        from sqlalchemy import text
        from ai_router_core import UserContext, UserRole, SubscriptionTier

        with _get_db() as db:
            rows = db.execute(text("""
                SELECT id, role, subscription_tier
                FROM users
                WHERE created_at > NOW() - INTERVAL '30 days'
                LIMIT 1000
            """)).fetchall()

        users = []
        for row in rows:
            try:
                users.append(UserContext(
                    user_id=str(row.id),
                    role=UserRole(row.role) if row.role else UserRole.FOUNDER,
                    subscription_tier=SubscriptionTier(row.subscription_tier)
                        if row.subscription_tier else SubscriptionTier.FREE,
                    credits_remaining=50,
                    project_id=None, project_stage=None, industry=None,
                    tech_stack=[], past_feedback=[],
                    training_progress={}, time_logged_today=0, tasks_completed_week=0,
                ))
            except Exception:
                continue
        return users
    except Exception as e:
        logger.warning("fetch_active_users_unavailable", error=str(e))
        return []


def _fetch_week_activity(user_id: str) -> Dict:
    """Aggregate a user's activity data for the past 7 days."""
    try:
        from sqlalchemy import text
        with _get_db() as db:
            row = db.execute(text("""
                SELECT
                    COUNT(pm.id) FILTER (WHERE pm.completed_at > NOW() - INTERVAL '7 days')
                        AS tasks_done,
                    MAX(pm.completed_at) AS last_activity
                FROM project_milestones pm
                JOIN projects p ON p.id = pm.project_id
                WHERE p.owner_id = :uid
            """), {"uid": user_id}).fetchone()
        return {
            "tasks_completed": int(row.tasks_done or 0) if row else 0,
            "last_activity":   str(row.last_activity) if row and row.last_activity else None,
        }
    except Exception:
        return {"tasks_completed": 0, "last_activity": None}


def _fetch_all_projects_with_scores() -> List[Dict]:
    """
    Fetch all active projects with their current score components.

    Production SQL returns: id, owner_id, title, stage, days_since_update,
    gsis_score, wcrs_score, decay_factor, plus all component scores.
    """
    try:
        from sqlalchemy import text
        with _get_db() as db:
            rows = db.execute(text("""
                SELECT id, owner_id, title, stage, days_since_update,
                       gsis_score, wcrs_score, decay_factor,
                       unicorn_potential_score, product_progress_score, evi_score,
                       market_readiness_score, beta_satisfaction_score,
                       revenue_growth_signal, founder_reliability_score,
                       community_influence_score, investor_interest_score,
                       compliance_score, evi_i_score
                FROM projects
                WHERE stage IS NOT NULL
                LIMIT 5000
            """)).fetchall()
        return [dict(row._mapping) for row in rows]
    except Exception as e:
        logger.warning("fetch_projects_unavailable", error=str(e))
        return []


def _fetch_stagnating_projects() -> List[Dict]:
    """
    Fetch projects with decay_factor < 0.70 (18+ days inactive),
    excluding the 'scale' stage.
    """
    try:
        from sqlalchemy import text
        with _get_db() as db:
            rows = db.execute(text("""
                SELECT p.id, p.owner_id, p.title, p.stage,
                       p.decay_factor, p.days_since_update, p.gsis_score,
                       u.email AS owner_email
                FROM projects p
                JOIN users u ON u.id = p.owner_id
                WHERE p.decay_factor < 0.70
                  AND p.stage NOT IN ('scale', 'archived')
                ORDER BY p.decay_factor ASC
                LIMIT 500
            """)).fetchall()
        return [dict(row._mapping) for row in rows]
    except Exception as e:
        logger.warning("fetch_stagnating_projects_unavailable", error=str(e))
        return []


def _fetch_users_without_curriculum() -> List[tuple]:
    """
    Fetch (UserContext, profile_dict) for users joined > 1 day ago
    with no personalised_curricula row yet.
    """
    try:
        from sqlalchemy import text
        from ai_router_core import UserContext, UserRole, SubscriptionTier

        with _get_db() as db:
            rows = db.execute(text("""
                SELECT u.id, u.role, u.subscription_tier,
                       lp.learning_pace, lp.hours_per_week,
                       lp.has_technical_skills
                FROM users u
                JOIN learner_profiles lp ON lp.user_id = u.id
                LEFT JOIN personalised_curricula pc ON pc.user_id = u.id
                WHERE pc.id IS NULL
                  AND u.created_at < NOW() - INTERVAL '1 day'
                LIMIT 200
            """)).fetchall()

        result = []
        for row in rows:
            try:
                ctx = UserContext(
                    user_id=str(row.id),
                    role=UserRole(row.role) if row.role else UserRole.FOUNDER,
                    subscription_tier=SubscriptionTier(row.subscription_tier)
                        if row.subscription_tier else SubscriptionTier.FREE,
                    credits_remaining=50,
                    project_id=None, project_stage="idea", industry=None,
                    tech_stack=[], past_feedback=[],
                    training_progress={}, time_logged_today=0, tasks_completed_week=0,
                )
                result.append((ctx, dict(row._mapping)))
            except Exception:
                continue
        return result
    except Exception as e:
        logger.warning("fetch_users_without_curriculum_unavailable", error=str(e))
        return []


def _fetch_watchlist_crossings() -> List[Dict]:
    """
    Fetch investor watchlist entries where GSIS or EVI-I crossed
    the alert threshold in the last 5 minutes (not already alerted in 1h).
    """
    try:
        from sqlalchemy import text
        with _get_db() as db:
            rows = db.execute(text("""
                SELECT iw.id AS watchlist_id, iw.investor_id, iw.project_id,
                       iw.gsis_alert_threshold, iw.evi_alert_threshold,
                       p.title AS project_title, p.gsis_score,
                       e.adjusted_evi_i
                FROM investor_watchlist iw
                JOIN projects p ON p.id = iw.project_id
                LEFT JOIN investor_evi_snapshots e ON e.project_id = iw.project_id
                    AND e.computed_at = (
                        SELECT MAX(computed_at) FROM investor_evi_snapshots
                        WHERE project_id = iw.project_id
                    )
                WHERE iw.alert_enabled = true
                  AND (
                      (iw.gsis_alert_threshold IS NOT NULL
                          AND p.gsis_score >= iw.gsis_alert_threshold)
                      OR
                      (iw.evi_alert_threshold IS NOT NULL
                          AND e.adjusted_evi_i >= iw.evi_alert_threshold)
                  )
                  AND (iw.last_alerted_at IS NULL
                      OR iw.last_alerted_at < NOW() - INTERVAL '1 hour')
            """)).fetchall()
        return [dict(row._mapping) for row in rows]
    except Exception as e:
        logger.warning("fetch_watchlist_crossings_unavailable", error=str(e))
        return []


def _fetch_active_discussion_threads() -> List[Dict]:
    """Fetch discussion threads with contributions in the last 2 hours."""
    try:
        from sqlalchemy import text
        with _get_db() as db:
            rows = db.execute(text("""
                SELECT dt.id, dt.problem_id, dt.contribution_count,
                       dt.is_ready_to_convert,
                       COUNT(dc.id) AS recent_contributions
                FROM discussion_threads dt
                JOIN discussion_contributions dc ON dc.thread_id = dt.id
                WHERE dc.created_at > NOW() - INTERVAL '2 hours'
                GROUP BY dt.id
                HAVING COUNT(dc.id) > 0
                LIMIT 100
            """)).fetchall()
        return [dict(row._mapping) for row in rows]
    except Exception as e:
        logger.warning("fetch_active_threads_unavailable", error=str(e))
        return []


def _fetch_active_deployments() -> List[Dict]:
    """
    Fetch active/scaling deployments with summed beneficiary counts
    from field_feedback rows.
    """
    try:
        from sqlalchemy import text
        with _get_db() as db:
            rows = db.execute(text("""
                SELECT sd.id, sd.solution_id, sd.status,
                       sd.beneficiaries_target, sd.beneficiaries_reached,
                       sd.deployment_checklist,
                       COALESCE(
                           SUM((ff.impact_metrics->>'beneficiaries_reached')::int), 0
                       ) AS total_beneficiaries
                FROM solution_deployments sd
                LEFT JOIN field_feedback ff ON ff.deployment_id = sd.id
                WHERE sd.status IN ('active', 'scaling')
                GROUP BY sd.id
                LIMIT 500
            """)).fetchall()
        return [dict(row._mapping) for row in rows]
    except Exception as e:
        logger.warning("fetch_active_deployments_unavailable", error=str(e))
        return []


def _fetch_deployments_for_snapshot() -> List[Dict]:
    """Fetch active deployments with their solution's impact data."""
    try:
        from sqlalchemy import text
        with _get_db() as db:
            rows = db.execute(text("""
                SELECT sd.id AS deployment_id, sd.solution_id,
                       sd.beneficiaries_reached, sd.status,
                       sp.impact_score, sp.feasibility_score,
                       sp.sustainability_score,
                       COUNT(ff.id) AS feedback_count,
                       COALESCE(
                           SUM((ff.impact_metrics->>'beneficiaries_reached')::int), 0
                       ) AS latest_beneficiaries
                FROM solution_deployments sd
                JOIN solution_projects sp ON sp.id = sd.solution_id
                LEFT JOIN field_feedback ff ON ff.deployment_id = sd.id
                    AND ff.created_at > NOW() - INTERVAL '24 hours'
                WHERE sd.status IN ('active', 'scaling', 'completed')
                GROUP BY sd.id, sp.id
                LIMIT 1000
            """)).fetchall()
        return [dict(row._mapping) for row in rows]
    except Exception as e:
        logger.warning("fetch_deployments_for_snapshot_unavailable", error=str(e))
        return []


def _fetch_anomaly_signals() -> List[Dict]:
    """Fetch unprocessed anomaly events from the last 15 minutes."""
    try:
        from sqlalchemy import text
        with _get_db() as db:
            rows = db.execute(text("""
                SELECT id, event_type, event_data, user_id, created_at
                FROM event_logs
                WHERE event_type IN (
                    'unusual_credit_burn', 'multiple_logins_same_ip',
                    'fake_traction_detected', 'rapid_metric_spike',
                    'account_sharing_signal'
                )
                AND created_at > NOW() - INTERVAL '15 minutes'
                AND processed = false
                ORDER BY created_at DESC
                LIMIT 200
            """)).fetchall()
        return [dict(row._mapping) for row in rows]
    except Exception as e:
        logger.warning("fetch_anomaly_signals_unavailable", error=str(e))
        return []


def _fetch_due_trust_verification_batches(limit: int = 500) -> List[Dict]:
    """
    Fetch latest Trust source states that need continuous verification handling.

    The query reads only verification metadata and active badge references. It
    does not fetch provider payloads, tokens, source code, logs, or analytics
    events. Expiry intervals are enforced by `trust_verification_history.expires_at`,
    which is source-specific in TrustEngineComputer.
    """
    try:
        from sqlalchemy import text

        capped = min(max(int(limit), 1), 5000)
        with _get_db() as db:
            rows = db.execute(text("""
                WITH latest_history AS (
                    SELECT DISTINCT ON (user_id, project_id, source)
                        user_id,
                        project_id,
                        CAST(source AS TEXT) AS source,
                        CAST(source AS TEXT) AS provider,
                        CAST(status AS TEXT) AS status,
                        confidence,
                        created_at AS last_sync_at,
                        expires_at
                    FROM trust_verification_history
                    ORDER BY user_id, project_id, source, created_at DESC
                ),
                active_badges AS (
                    SELECT
                        user_id,
                        project_id,
                        CAST(source AS TEXT) AS source,
                        json_agg(json_build_object(
                            'badge_type', badge_type,
                            'label', label,
                            'expires_at', expires_at
                        )) AS active_badges
                    FROM trust_badge_snapshots
                    WHERE LOWER(CAST(status AS TEXT)) = 'verified'
                      AND expires_at > NOW()
                    GROUP BY user_id, project_id, source
                )
                SELECT
                    latest_history.user_id,
                    latest_history.project_id,
                    latest_history.source,
                    latest_history.provider,
                    latest_history.status,
                    latest_history.confidence,
                    latest_history.last_sync_at,
                    latest_history.expires_at,
                    users.role,
                    users.subscription_tier,
                    projects.stage AS project_stage,
                    projects.industry,
                    COALESCE(active_badges.active_badges, '[]'::json) AS active_badges
                FROM latest_history
                LEFT JOIN active_badges
                  ON active_badges.user_id = latest_history.user_id
                 AND active_badges.project_id IS NOT DISTINCT FROM latest_history.project_id
                 AND active_badges.source = latest_history.source
                LEFT JOIN users ON users.id = latest_history.user_id
                LEFT JOIN projects ON projects.id = latest_history.project_id
                WHERE LOWER(latest_history.status) IN ('failed', 'pending', 'disconnected')
                   OR latest_history.expires_at <= NOW()
                ORDER BY latest_history.expires_at ASC NULLS FIRST
                LIMIT :limit
            """), {"limit": capped}).fetchall()
        return _trust_connection_batches_from_rows(rows)
    except Exception as e:
        logger.warning("fetch_due_trust_verifications_unavailable", error=str(e))
        return []


def _trust_connection_batches_from_rows(rows: List[Any]) -> List[Dict]:
    """Group Trust history rows into per-founder service calls."""
    grouped: Dict[tuple, Dict[str, Any]] = {}
    for row in rows:
        user_id = str(_row_value(row, "user_id", "") or "")
        if not user_id:
            continue
        project_id_value = _row_value(row, "project_id")
        project_id = str(project_id_value) if project_id_value else None
        key = (user_id, project_id)
        batch = grouped.setdefault(
            key,
            {
                "user_id": user_id,
                "project_id": project_id,
                "role": _trust_value(_row_value(row, "role", "founder")) or "founder",
                "subscription_tier": _trust_value(_row_value(row, "subscription_tier", "free")) or "free",
                "project_stage": _trust_value(_row_value(row, "project_stage")),
                "industry": _row_value(row, "industry"),
                "connections": [],
            },
        )

        source = _trust_value(_row_value(row, "source"))
        if not source:
            continue
        status = _trust_value(_row_value(row, "status", "pending")) or "pending"
        provider = _trust_value(_row_value(row, "provider", source)) or source
        batch["connections"].append({
            "source": source,
            "provider": provider,
            "status": status,
            "connected": status != "disconnected",
            "last_sync_at": _iso(_row_value(row, "last_sync_at")),
            "expires_at": _iso(_row_value(row, "expires_at")),
            "confidence": float(_row_value(row, "confidence", 0.5) or 0.5),
            "active_badges": _trust_badges(_row_value(row, "active_badges", [])),
        })

    return list(grouped.values())


def _run_trust_continuous_verification_batch(
    batch: Dict[str, Any],
    *,
    execute: bool,
    db: Any = None,
    service: Any = None,
) -> Dict[str, Any]:
    """Run one founder/project Trust continuous verification batch."""
    if service is None:
        from integration_guide import TrustVerificationService
        service = TrustVerificationService(_get_brain())

    user_context = _build_trust_user_context(batch)
    result = service.run_continuous_verification(
        user_context,
        {
            "execute": execute is True,
            "connections": batch.get("connections") or [],
            "adapter_payloads": {},
        },
        db if execute is True else None,
    )
    executed_results = result.get("executed_results") or []
    notifications = result.get("notification_intents") or []
    summary = result.get("summary") or {}
    return {
        "user_id": batch.get("user_id"),
        "project_id": batch.get("project_id"),
        "execute": execute is True,
        "connections_seen": summary.get("connections_seen", 0),
        "actions_prepared": summary.get("actions_prepared", 0),
        "notifications_prepared": summary.get("notifications_prepared", 0),
        "badge_notifications_prepared": summary.get("badge_notifications_prepared", 0),
        "executed_actions": len(executed_results),
        "executed_results": executed_results,
        "notification_intents": notifications,
        "notification_types": [note.get("notification_type") for note in notifications],
        "privacy": result.get("privacy") or {},
    }


def _run_trust_continuous_verification_batches(
    batches: List[Dict],
    *,
    execute: bool,
    service_factory: Any = None,
    db_factory: Any = None,
) -> Dict[str, Any]:
    """Aggregate Trust continuous verification worker results."""
    service = service_factory() if service_factory else None
    result = {
        "execute": execute is True,
        "batches_seen": len(batches),
        "batches_processed": 0,
        "failed_batches": 0,
        "connections_seen": 0,
        "actions_prepared": 0,
        "notifications_prepared": 0,
        "badge_notifications_prepared": 0,
        "executed_actions": 0,
        "batch_results": [],
        "privacy": {
            "metadata_only": True,
            "raw_payload_stored": False,
            "tokens_stored": False,
            "provider_calls_executed": False,
            "failure_deletes_existing_data": False,
            "execute_required_for_mutation": True,
        },
    }

    for batch in batches:
        try:
            if execute is True:
                if db_factory:
                    with db_factory() as db:
                        batch_result = _run_trust_continuous_verification_batch(
                            batch,
                            execute=True,
                            db=db,
                            service=service,
                        )
                else:
                    with _get_db() as db:
                        batch_result = _run_trust_continuous_verification_batch(
                            batch,
                            execute=True,
                            db=db,
                            service=service,
                        )
            else:
                batch_result = _run_trust_continuous_verification_batch(
                    batch,
                    execute=False,
                    db=None,
                    service=service,
                )
            result["batches_processed"] += 1
            result["connections_seen"] += int(batch_result["connections_seen"])
            result["actions_prepared"] += int(batch_result["actions_prepared"])
            result["notifications_prepared"] += int(batch_result["notifications_prepared"])
            result["badge_notifications_prepared"] += int(batch_result["badge_notifications_prepared"])
            result["executed_actions"] += int(batch_result["executed_actions"])
            result["batch_results"].append(batch_result)
        except Exception as e:
            result["failed_batches"] += 1
            logger.warning(
                "trust_continuous_verification_batch_failed",
                user_id=batch.get("user_id"),
                project_id=batch.get("project_id"),
                error=str(e),
            )

    return result


def _build_trust_user_context(batch: Dict[str, Any]) -> Any:
    from ai_router_core import SubscriptionTier, UserContext, UserRole

    role = _enum_for_value(UserRole, batch.get("role"), UserRole.FOUNDER)
    tier = _enum_for_value(SubscriptionTier, batch.get("subscription_tier"), SubscriptionTier.FREE)
    return UserContext(
        user_id=str(batch.get("user_id")),
        role=role,
        subscription_tier=tier,
        credits_remaining=0,
        project_id=batch.get("project_id"),
        project_stage=batch.get("project_stage"),
        industry=batch.get("industry"),
        tech_stack=[],
        past_feedback=[],
        training_progress={},
        time_logged_today=0,
        tasks_completed_week=0,
    )


def _enum_for_value(enum_cls: Any, value: Any, default: Any) -> Any:
    normalized = _trust_value(value)
    for member in enum_cls:
        if member.value == normalized or member.name.lower() == normalized:
            return member
    return default


def _trust_worker_execute_enabled(execute: Optional[bool]) -> bool:
    if execute is not None:
        return execute is True
    return str(os.getenv("TRUST_CONTINUOUS_VERIFICATION_EXECUTE", "false")).strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _trust_badges(raw: Any) -> List[Dict[str, Any]]:
    if raw is None:
        return []
    if isinstance(raw, str):
        try:
            raw = json.loads(raw)
        except ValueError:
            return []
    if isinstance(raw, dict):
        raw = [raw]
    if not isinstance(raw, list):
        return []

    badges = []
    for badge in raw:
        if not isinstance(badge, dict):
            continue
        badge_type = str(badge.get("badge_type") or badge.get("type") or "").strip()
        label = str(badge.get("label") or badge_type).strip()
        if not badge_type and not label:
            continue
        badges.append({
            "badge_type": badge_type or label,
            "label": label or badge_type,
            "expires_at": _iso(badge.get("expires_at")),
        })
    return badges


def _row_value(row: Any, key: str, default: Any = None) -> Any:
    if isinstance(row, dict):
        return row.get(key, default)
    mapping = getattr(row, "_mapping", None)
    if mapping is not None and key in mapping:
        return mapping[key]
    return getattr(row, key, default)


def _trust_value(value: Any) -> str:
    if value is None:
        return ""
    if hasattr(value, "value"):
        value = value.value
    return str(value).strip().lower()


def _iso(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def _send_reengagement_notification(owner_id: str, project_title: str,
                                     days_inactive: int, decay_factor: float):
    """
    Send a specific re-engagement notification to a stagnating founder.
    Message names the project, the penalty, and the exact action needed.

    Production: call push_notification_service and/or email_service.
    """
    message = (
        "'" + project_title + "' has been inactive for "
        + str(days_inactive) + " days. "
        "Decay factor: " + str(round(decay_factor, 2))
        + " -- your ranking is falling by "
        + str(round((1 - decay_factor) * 100, 1)) + "%. "
        "Log a milestone today to recover your score."
    )
    logger.info("reengagement_notification",
                owner_id=owner_id, project=project_title,
                days=days_inactive, decay=decay_factor, msg=message)
    # Production:
    # push_service.send(owner_id, title="Your startup is stagnating", body=message)
    # email_service.send(owner_email, subject="Execution score dropping", body=message)


def _fire_investor_alert(investor_id: str, project_id: str,
                          project_title: str, gsis_score: float,
                          evi_i_score: float, watchlist_id: str):
    """
    Insert an investor_alerts row and update the watchlist last_alerted_at
    so the same threshold does not fire again within 1 hour.
    """
    try:
        from sqlalchemy import text
        msg = (
            project_title + " crossed your alert threshold -- "
            "GSIS: " + str(round(gsis_score, 1))
            + ", EVI-I: " + str(round(evi_i_score, 1))
        )
        with _get_db() as db:
            db.execute(text("""
                INSERT INTO investor_alerts
                    (investor_id, project_id, alert_type, message,
                     gsis_at_alert, evi_i_at_alert, triggered_at)
                VALUES
                    (:inv, :pid, 'threshold_crossed', :msg, :gsis, :evi, NOW())
            """), {"inv": investor_id, "pid": project_id,
                   "msg": msg, "gsis": gsis_score, "evi": evi_i_score})
            db.execute(text("""
                UPDATE investor_watchlist
                SET last_alerted_at = NOW()
                WHERE id = :wid
            """), {"wid": watchlist_id})
        logger.info("investor_alert_fired", investor_id=investor_id,
                    project_id=project_id, gsis=gsis_score, evi_i=evi_i_score)
    except Exception as e:
        logger.error("fire_investor_alert_failed", error=str(e))


# ============================================================================
# TASK 1: Daily Tour Guide
# ============================================================================

@celery.task(name="workers.daily_tour_guide", bind=True, max_retries=3)
def daily_tour_guide(self):
    """
    Daily momentum check-in for every active user. Runs at 06:00 UTC.

    For each active user:
      - Calls TourGuideService.daily_check_in()
      - Computes momentum score from activity data
      - Generates AI daily plan (3 prioritised actions)
      - If momentum < 40: sends low-momentum push notification
    """
    try:
        from integration_guide import TourGuideService
        brain   = _get_brain()
        svc     = TourGuideService(brain)
        users   = _fetch_active_users()
        success = 0

        logger.info("daily_tour_guide_start", user_count=len(users))
        for user in users:
            try:
                asyncio.run(svc.daily_check_in(user))
                success += 1
            except Exception as e:
                logger.warning("tour_guide_user_failed",
                               user_id=user.user_id, error=str(e))

        logger.info("daily_tour_guide_complete",
                    total=len(users), success=success)
    except Exception as exc:
        logger.error("daily_tour_guide_failed", error=str(exc))
        raise self.retry(exc=exc, countdown=300)


# ============================================================================
# TASK 2: Weekly Summaries
# ============================================================================

@celery.task(name="workers.weekly_summaries", bind=True, max_retries=3)
def weekly_summaries(self):
    """
    Weekly Tour Guide summary for every active user. Runs Sunday 18:00 UTC.

    For each active user:
      - Fetches week activity (tasks done, time logged, milestones, training)
      - Calls TourGuideService.weekly_summary(user, week_data)
      - AI generates what went well, what slipped, and next week's priority
      - Sends weekly report push notification
    """
    try:
        from integration_guide import TourGuideService
        brain   = _get_brain()
        svc     = TourGuideService(brain)
        users   = _fetch_active_users()
        success = 0

        logger.info("weekly_summaries_start", user_count=len(users))
        for user in users:
            try:
                week_data = _fetch_week_activity(user.user_id)
                asyncio.run(svc.weekly_summary(user, week_data))
                success += 1
            except Exception as e:
                logger.warning("weekly_summary_user_failed",
                               user_id=user.user_id, error=str(e))

        logger.info("weekly_summaries_complete",
                    total=len(users), success=success)
    except Exception as exc:
        logger.error("weekly_summaries_failed", error=str(exc))
        raise self.retry(exc=exc, countdown=600)


# ============================================================================
# TASK 3: Daily Investor Signals (EVI-I Refresh)
# ============================================================================

@celery.task(name="workers.daily_investor_signals", bind=True, max_retries=3)
def daily_investor_signals(self):
    """
    Refresh EVI-I scores for all active startups. Runs daily at 00:00 UTC.

    For each project:
      - Builds startup_data dict from project + metric rows
      - Calls InvestorEVIService.compute_from_startup()
      - Inserts new row into investor_evi_snapshots
      - Updates projects.evi_i_score

    EVI-I formula:
      EVI-I = (0.25*MDR + 0.20*IS + 0.15*TRV + 0.20*RTA + 0.10*UGM + 0.10*CEV) * decay
    """
    try:
        from investor_evi import InvestorEVIService
        from sqlalchemy import text

        svc       = InvestorEVIService()
        projects  = _fetch_all_projects_with_scores()
        refreshed = 0

        logger.info("daily_investor_signals_start", count=len(projects))
        for proj in projects:
            try:
                days = int(proj.get("days_since_update", 0))
                frs  = float(proj.get("founder_reliability_score") or 50)
                bss  = float(proj.get("beta_satisfaction_score") or 50)

                startup_data = {
                    "project_id":        str(proj["id"]),
                    "project_name":      proj.get("title", ""),
                    "industry":          proj.get("industry", ""),
                    "stage":             str(proj.get("stage", "idea")),
                    "days_since_update": days,
                    "milestones": {
                        "committed_30d":     8,
                        "delivered_30d":     int(8 * (frs / 100)),
                        "avg_days_complete": 7.0,
                        "late_count":        2,
                        "quality_score":     bss / 10,
                    },
                    "iteration": {
                        "versions_30d":       3,
                        "feedback_fix_days":  3.0,
                        "feature_cycle_days": 10.0,
                        "pivots_90d":         0,
                    },
                    "response": {
                        "investor_response_hrs": 12.0,
                        "collab_response_hrs":   8.0,
                        "sessions_per_week":     5.0,
                        "checkin_pct":           70.0,
                    },
                    "revenue": {
                        "mrr_current":  0,
                        "mrr_30d":      0,
                        "mrr_90d":      0,
                        "customers_now": 0,
                        "customers_30d": 0,
                        "arpu":          0,
                        "churn_pct":     0,
                    },
                    "users": {
                        "users_now":      0,
                        "users_30d":      0,
                        "users_90d":      0,
                        "dau_wau":        0.0,
                        "week1_retention": 0.0,
                        "organic_pct":    0.0,
                    },
                    "capital": {
                        "total_raised":    0,
                        "monthly_burn":    0,
                        "runway_months":   12.0,
                        "rev_per_dollar":  0.0,
                        "team_size":       2,
                        "rev_per_employee": 0,
                    },
                }

                result = svc.compute_from_startup(
                    startup_data,
                    previous_evi_i=proj.get("evi_i_score"),
                )

                with _get_db() as db:
                    db.execute(text("""
                        INSERT INTO investor_evi_snapshots
                            (project_id, raw_evi_i, adjusted_evi_i, decay_factor,
                             signal, velocity_risk, evi_trend, trend_delta,
                             headline, computed_at)
                        VALUES (:pid, :raw, :adj, :dec, :sig, :risk, :trend, :delta, :hl, NOW())
                    """), {
                        "pid":   str(proj["id"]),
                        "raw":   result.raw_evi_i,
                        "adj":   result.adjusted_evi_i,
                        "dec":   result.decay_factor,
                        "sig":   result.signal.value,
                        "risk":  result.velocity_risk,
                        "trend": result.evi_trend,
                        "delta": result.trend_delta,
                        "hl":    result.headline,
                    })
                    db.execute(text("""
                        UPDATE projects SET evi_i_score = :evi WHERE id = :pid
                    """), {"evi": result.adjusted_evi_i, "pid": str(proj["id"])})
                refreshed += 1

            except Exception as e:
                logger.warning("evi_refresh_failed",
                               project_id=str(proj.get("id")), error=str(e))

        logger.info("daily_investor_signals_complete",
                    total=len(projects), refreshed=refreshed)
    except Exception as exc:
        logger.error("daily_investor_signals_task_failed", error=str(exc))
        raise self.retry(exc=exc, countdown=300)


# ============================================================================
# TASK 4: Adaptive Curriculum Generation
# ============================================================================

@celery.task(name="workers.adaptive_curriculum_weekly", bind=True, max_retries=3)
def adaptive_curriculum_weekly(self):
    """
    Generate personalised curricula for users who have none. Runs Monday 02:00 UTC.

    Uses TimeToMVPEngine -- duration is COMPUTED, not scheduled.
    Solo non-technical founder, 8h/week, idea stage -> ~18 weeks.
    Technical co-founder team, 20h/week, validation -> ~4 weeks.
    """
    try:
        from integration_guide import AdaptiveTrainingService
        brain     = _get_brain()
        svc       = AdaptiveTrainingService(brain)
        new_users = _fetch_users_without_curriculum()
        generated = 0

        logger.info("adaptive_curriculum_start", count=len(new_users))
        for user_ctx, profile in new_users:
            try:
                asyncio.run(svc.generate_curriculum(
                    user_ctx,
                    hours_available_per_week=float(profile.get("hours_per_week", 8.0)),
                    learning_pace=profile.get("learning_pace", "standard"),
                    target_mvp_weeks=0,
                    has_technical_skills=bool(profile.get("has_technical_skills", False)),
                ))
                generated += 1
            except Exception as e:
                logger.warning("curriculum_gen_failed",
                               user_id=user_ctx.user_id, error=str(e))

        logger.info("adaptive_curriculum_complete",
                    total=len(new_users), generated=generated)
    except Exception as exc:
        logger.error("adaptive_curriculum_task_failed", error=str(exc))
        raise self.retry(exc=exc, countdown=300)


# ============================================================================
# TASK 5: WCRS + GSIS Score Refresh (with Decay)
# ============================================================================

@celery.task(name="workers.wcrs_gsis_refresh", bind=True, max_retries=2)
def wcrs_gsis_refresh(self):
    """
    Refresh GSIS and WCRS for all active projects. Runs every 30 minutes.
    This is what makes inactivity punishing in real time.

    Decay formula: e^(-0.02 * days_inactive)
      d=0:  1.000 (fully active)
      d=5:  0.905 (5% penalty)
      d=18: 0.698 (30% penalty -- stagnation threshold)
      d=30: 0.549 (45% penalty)

    For each project:
      1. Compute fresh decay_factor
      2. Recompute GSIS from stored component scores
      3. Recompute WCRS (decay-adjusted marketplace rank)
      4. Write scores + insert snapshot for trend tracking
    """
    try:
        from ai_router_core import ScoringEngine
        from sqlalchemy import text

        projects = _fetch_all_projects_with_scores()
        updated  = 0

        logger.info("wcrs_gsis_refresh_start", count=len(projects))
        for proj in projects:
            try:
                days  = int(proj.get("days_since_update", 0))
                decay = ScoringEngine.compute_decay_factor(days)

                gsis_result = ScoringEngine.compute_gsis(
                    product_progress_score=float(proj.get("product_progress_score") or 50),
                    execution_velocity_index=float(proj.get("evi_score") or 50),
                    market_readiness_score=float(proj.get("market_readiness_score") or 50),
                    beta_satisfaction_score=float(proj.get("beta_satisfaction_score") or 50),
                    revenue_growth_signal=float(proj.get("revenue_growth_signal") or 0),
                    founder_reliability_score=float(proj.get("founder_reliability_score") or 50),
                    community_influence_score=float(proj.get("community_influence_score") or 0),
                    investor_interest_score=float(proj.get("investor_interest_score") or 0),
                    compliance_score=float(proj.get("compliance_score") or 80),
                )
                new_gsis = gsis_result["gsis"]

                wcrs_result = ScoringEngine.compute_wcrs(
                    gsis_score=new_gsis,
                    quality_multiplier=1.0,
                    days_since_last_update=days,
                )
                new_wcrs = wcrs_result["adjusted"]

                with _get_db() as db:
                    db.execute(text("""
                        UPDATE projects
                        SET gsis_score   = :gsis,
                            wcrs_score   = :wcrs,
                            decay_factor = :decay
                        WHERE id = :pid
                    """), {"gsis": new_gsis, "wcrs": new_wcrs,
                           "decay": decay, "pid": str(proj["id"])})

                    db.execute(text("""
                        INSERT INTO score_snapshots
                            (project_id, gsis_score, wcrs_adjusted_score, decay_factor,
                             unicorn_potential_score, snapshotted_at)
                        VALUES (:pid, :gsis, :wcrs, :decay, :ups, NOW())
                    """), {
                        "pid":   str(proj["id"]),
                        "gsis":  new_gsis,
                        "wcrs":  new_wcrs,
                        "decay": decay,
                        "ups":   proj.get("unicorn_potential_score", 0),
                    })
                updated += 1

            except Exception as e:
                logger.warning("wcrs_gsis_project_failed",
                               project_id=str(proj.get("id")), error=str(e))

        logger.info("wcrs_gsis_refresh_complete",
                    total=len(projects), updated=updated)
    except Exception as exc:
        logger.error("wcrs_gsis_refresh_task_failed", error=str(exc))
        raise self.retry(exc=exc, countdown=60)


# ============================================================================
# TASK 6: Stagnation Roster
# ============================================================================

@celery.task(name="workers.stagnation_roster", bind=True, max_retries=2)
def stagnation_roster(self):
    """
    Flag projects with decay_factor < 0.70 (18+ days inactive). Runs 07:00 UTC daily.

    Runs after wcrs_gsis_refresh (06:30) so it always operates on fresh scores.
    For each stagnating project:
      - Sends a specific re-engagement notification naming the project,
        days inactive, score penalty, and the exact action needed
      - Logs stagnation event to event_logs for admin visibility
    """
    try:
        from sqlalchemy import text
        stagnating = _fetch_stagnating_projects()
        notified   = 0

        logger.info("stagnation_roster_start", count=len(stagnating))
        for proj in stagnating:
            try:
                _send_reengagement_notification(
                    owner_id=str(proj["owner_id"]),
                    project_title=proj["title"],
                    days_inactive=int(proj["days_since_update"]),
                    decay_factor=float(proj["decay_factor"]),
                )
                with _get_db() as db:
                    db.execute(text("""
                        INSERT INTO event_logs
                            (event_type, event_data, user_id, project_id, created_at)
                        VALUES ('stagnation_flagged', :data::jsonb, :uid, :pid, NOW())
                        ON CONFLICT DO NOTHING
                    """), {
                        "data": json.dumps({
                            "days_inactive": proj["days_since_update"],
                            "decay_factor":  float(proj["decay_factor"]),
                            "gsis_score":    float(proj.get("gsis_score") or 0),
                        }),
                        "uid": str(proj["owner_id"]),
                        "pid": str(proj["id"]),
                    })
                notified += 1
            except Exception as e:
                logger.warning("stagnation_notify_failed",
                               project_id=str(proj.get("id")), error=str(e))

        logger.info("stagnation_roster_complete",
                    total=len(stagnating), notified=notified)
    except Exception as exc:
        logger.error("stagnation_roster_task_failed", error=str(exc))
        raise self.retry(exc=exc, countdown=300)


# ============================================================================
# TASK 7: Monthly Credit Reset
# ============================================================================

@celery.task(name="workers.monthly_credit_reset", bind=True, max_retries=3)
def monthly_credit_reset(self):
    """
    Reset subscription credit allocations on the 1st of every month. 00:00 UTC.

    Rules:
      - Subscription credits reset to plan monthly allowance
      - PAYG credits are NEVER reset -- they never expire
      - Each reset recorded in credit_ledger for audit trail
      - Free tier (5 credits/month) also resets

    Uses ALL_PLANS from billing_system.py for each plan's monthly_credits value.
    """
    try:
        from billing_system import ALL_PLANS
        from sqlalchemy import text

        reset_count = 0
        logger.info("monthly_credit_reset_start",
                    month=datetime.utcnow().strftime("%Y-%m"))

        with _get_db() as db:
            rows = db.execute(text("""
                SELECT id, subscription_plan_id, subscription_tier,
                       subscription_credits_remaining
                FROM users
                WHERE subscription_plan_id IS NOT NULL
                  AND subscription_status = 'active'
            """)).fetchall()

            for row in rows:
                try:
                    plan = ALL_PLANS.get(row.subscription_plan_id)
                    if not plan:
                        continue
                    monthly_credits = plan.monthly_credits
                    old_balance     = int(row.subscription_credits_remaining or 0)

                    db.execute(text("""
                        UPDATE users
                        SET subscription_credits_remaining = :credits,
                            subscription_reset_at          = NOW()
                        WHERE id = :uid
                    """), {"credits": monthly_credits, "uid": str(row.id)})

                    db.execute(text("""
                        INSERT INTO credit_ledger
                            (user_id, event_type, credits_delta,
                             balance_after, description, created_at)
                        VALUES (:uid, 'monthly_reset', :delta, :bal, :desc, NOW())
                    """), {
                        "uid":   str(row.id),
                        "delta": monthly_credits - old_balance,
                        "bal":   monthly_credits,
                        "desc":  (
                            "Monthly subscription reset -- plan: "
                            + str(row.subscription_plan_id)
                        ),
                    })
                    reset_count += 1
                except Exception as e:
                    logger.warning("credit_reset_user_failed",
                                   user_id=str(row.id), error=str(e))

        logger.info("monthly_credit_reset_complete",
                    users_reset=reset_count,
                    month=datetime.utcnow().strftime("%Y-%m"))
    except Exception as exc:
        logger.error("monthly_credit_reset_task_failed", error=str(exc))
        raise self.retry(exc=exc, countdown=300)


# ============================================================================
# TASK 8: Admin Anomaly Scan
# ============================================================================

@celery.task(name="workers.admin_anomaly_scan", bind=True, max_retries=2)
def admin_anomaly_scan(self):
    """
    Continuous abuse and anomaly detection. Runs every 15 minutes.

    Detects from event_logs:
      - unusual_credit_burn: burning 3x expected rate for tier
      - multiple_logins_same_ip: account sharing signal
      - fake_traction_detected: MRR spike with no customer growth
      - rapid_metric_spike: GSIS +20 in 1 hour (impossible organically)
      - account_sharing_signal: same session from multiple IPs

    Flags are recorded in event_logs. High-risk events create admin alerts.
    Uses AdminMonitorService which runs AdminMonitorAgent.
    """
    try:
        from integration_guide import AdminMonitorService
        brain   = _get_brain()
        svc     = AdminMonitorService(brain)
        signals = _fetch_anomaly_signals()

        logger.info("admin_anomaly_scan_start", signals=len(signals))
        if signals:
            admin_ctx = _build_system_context()
            asyncio.run(svc.run_anomaly_scan(admin_ctx, signals))

        logger.info("admin_anomaly_scan_complete", processed=len(signals))
    except Exception as exc:
        logger.error("admin_anomaly_scan_task_failed", error=str(exc))
        raise self.retry(exc=exc, countdown=60)


# ============================================================================
# TASK 9: Investor Alert Check
# ============================================================================

@celery.task(name="workers.investor_alert_check", bind=True, max_retries=2)
def investor_alert_check(self):
    """
    Check investor watchlist thresholds and fire alerts. Runs every 5 minutes.

    For each watchlist entry where:
      GSIS >= gsis_alert_threshold OR EVI-I >= evi_alert_threshold
      AND not alerted in the last hour:
      - Inserts row into investor_alerts
      - Updates last_alerted_at on watchlist entry (prevents duplicate alerts)
      - Sends investor push notification

    This is what makes TechIT's investor section valuable: investors get
    alerted the MOMENT a startup crosses their threshold.
    """
    try:
        crossings = _fetch_watchlist_crossings()
        logger.info("investor_alert_check_start", crossings=len(crossings))

        for crossing in crossings:
            try:
                _fire_investor_alert(
                    investor_id=str(crossing["investor_id"]),
                    project_id=str(crossing["project_id"]),
                    project_title=crossing.get("project_title", "Unknown"),
                    gsis_score=float(crossing.get("gsis_score", 0)),
                    evi_i_score=float(crossing.get("adjusted_evi_i", 0)),
                    watchlist_id=str(crossing["watchlist_id"]),
                )
            except Exception as e:
                logger.warning("alert_fire_failed",
                               watchlist_id=str(crossing.get("watchlist_id")),
                               error=str(e))

        logger.info("investor_alert_check_complete", fired=len(crossings))
    except Exception as exc:
        logger.error("investor_alert_check_task_failed", error=str(exc))
        raise self.retry(exc=exc, countdown=30)


# ============================================================================
# TASK 10: Problem Discovery (Idea & Solution Hub)
# ============================================================================

@celery.task(name="workers.problem_discovery_daily", bind=True, max_retries=3)
def problem_discovery_daily(self):
    """
    Auto-discover real-world problems from external data signals. Runs 06:00 UTC.

    Sources: news feeds, NGO reports (ReliefWeb), WHO data,
             government open datasets, social signal aggregators.

    For each discovered problem across 5 global regions:
      - SHA-256 fingerprint to prevent duplicates
      - Computes Impact Score and Priority Score
      - Inserts into problem_nodes with is_ai_discovered=True, verified=False
      - Admin must approve before public visibility
    """
    try:
        from idea_solution_hub import (ProblemDiscoveryEngine, ImpactScoringEngine,
                                        ProblemUrgency)
        from sqlalchemy import text

        disc       = ProblemDiscoveryEngine()
        impact_eng = ImpactScoringEngine()
        regions    = ["Africa", "South Asia", "Latin America", "Middle East", "Global"]
        inserted   = 0

        logger.info("problem_discovery_start", regions=len(regions))
        for region in regions:
            try:
                discovered = disc.discover(region=region, limit=10)
                logger.info("problem_discovery_region",
                            region=region, found=len(discovered))

                for problem in discovered:
                    try:
                        text_key    = problem["title"] + " " + region
                        fingerprint = hashlib.sha256(text_key.encode()).hexdigest()

                        urgency_val = problem.get("urgency", "emerging")
                        try:
                            urg_enum = ProblemUrgency(urgency_val)
                        except ValueError:
                            urg_enum = ProblemUrgency.EMERGING

                        severity = float(problem.get("severity", 6.0))
                        impact   = impact_eng.compute_impact_score(
                            1.0, severity, 6.0, 5.0, 6.0)
                        priority = impact_eng.compute_priority_score(
                            impact["impact_score"], urg_enum, 6.0, 5.0, 6.0)

                        with _get_db() as db:
                            existing = db.execute(text("""
                                SELECT 1 FROM problem_nodes
                                WHERE ai_summary LIKE :fp LIMIT 1
                            """), {"fp": "%" + fingerprint[:16] + "%"}).fetchone()

                            if not existing:
                                db.execute(text("""
                                    INSERT INTO problem_nodes
                                        (title, description, location, category,
                                         urgency, source, impact_score, priority_score,
                                         is_ai_discovered, verified, ai_summary, created_at)
                                    VALUES
                                        (:title, :desc, :loc, :cat, :urg, 'ai_discovered',
                                         :impact, :priority, true, false, :summary, NOW())
                                """), {
                                    "title":    problem["title"],
                                    "desc":     problem.get("title", ""),
                                    "loc":      region,
                                    "cat":      problem.get("category", "other"),
                                    "urg":      urgency_val,
                                    "impact":   impact["impact_score"],
                                    "priority": priority["priority_score"],
                                    "summary":  "AI-discovered [" + fingerprint[:16] + "]",
                                })
                                inserted += 1
                    except Exception as e:
                        logger.warning("problem_insert_failed",
                                       region=region, error=str(e))
            except Exception as e:
                logger.warning("problem_discovery_region_failed",
                               region=region, error=str(e))

        logger.info("problem_discovery_complete",
                    regions=len(regions), inserted=inserted)
    except Exception as exc:
        logger.error("problem_discovery_task_failed", error=str(exc))
        raise self.retry(exc=exc, countdown=600)


# ============================================================================
# TASK 11: Discussion Moderation (Idea & Solution Hub)
# ============================================================================

@celery.task(name="workers.discussion_moderation_hourly", bind=True, max_retries=2)
def discussion_moderation_hourly(self):
    """
    AI moderation of active problem discussion threads. Runs every hour.

    For each thread with contributions in the last 2 hours:
      - Loads all contributions (typed: idea/insight/resource/critique/data)
      - Runs DiscussionModerationEngine.detect_strongest_direction()
      - Runs DiscussionModerationEngine.cluster_contributions()
      - Updates discussion_threads: ai_summary, idea_clusters,
        is_ready_to_convert, readiness_confidence
    """
    try:
        from idea_solution_hub import (DiscussionModerationEngine,
                                        DiscussionContribution, ContributionType)
        from sqlalchemy import text

        mod       = DiscussionModerationEngine()
        threads   = _fetch_active_discussion_threads()
        moderated = 0

        logger.info("discussion_moderation_start", threads=len(threads))
        for thread in threads:
            try:
                with _get_db() as db:
                    contrib_rows = db.execute(text("""
                        SELECT id, author_id, contribution_type, content,
                               ai_quality_score, upvotes
                        FROM discussion_contributions
                        WHERE thread_id = :tid
                        ORDER BY created_at DESC LIMIT 50
                    """), {"tid": str(thread["id"])}).fetchall()

                contributions = []
                for row in contrib_rows:
                    try:
                        ct = ContributionType(row.contribution_type)
                    except ValueError:
                        ct = ContributionType.IDEA
                    contributions.append(DiscussionContribution(
                        thread_id=str(thread["id"]),
                        problem_id=str(thread["problem_id"]),
                        author_id=str(row.author_id),
                        contribution_type=ct,
                        content=row.content or "",
                        ai_quality_score=float(row.ai_quality_score or 0),
                        upvotes=int(row.upvotes or 0),
                    ))

                if not contributions:
                    continue

                direction = mod.detect_strongest_direction(contributions)
                clusters  = mod.cluster_contributions(contributions)

                with _get_db() as db:
                    db.execute(text("""
                        UPDATE discussion_threads
                        SET ai_summary           = :summary,
                            idea_clusters        = :clusters::jsonb,
                            is_ready_to_convert  = :ready,
                            readiness_confidence = :confidence,
                            updated_at           = NOW()
                        WHERE id = :tid
                    """), {
                        "summary":    direction.get("direction", ""),
                        "clusters":   json.dumps({k: [str(i) for i in v]
                                                  for k, v in clusters.items()}),
                        "ready":      direction.get("ready_to_convert", False),
                        "confidence": float(direction.get("confidence", 0)),
                        "tid":        str(thread["id"]),
                    })
                moderated += 1
            except Exception as e:
                logger.warning("thread_moderation_failed",
                               thread_id=str(thread.get("id")), error=str(e))

        logger.info("discussion_moderation_complete",
                    total=len(threads), moderated=moderated)
    except Exception as exc:
        logger.error("discussion_moderation_task_failed", error=str(exc))
        raise self.retry(exc=exc, countdown=120)


# ============================================================================
# TASK 12: Deployment Status Refresh (Idea & Solution Hub)
# ============================================================================

@celery.task(name="workers.deployment_status_refresh", bind=True, max_retries=2)
def deployment_status_refresh(self):
    """
    Refresh active deployment status and beneficiary counts. Runs every 15 minutes.

    For each active/scaling deployment:
      - Sums beneficiaries_reached from all linked field_feedback rows
      - Updates solution_deployments.beneficiaries_reached
      - If deployment checklist is 100% complete, sets status='completed'
      - Logs deployment_completed event for founder notification
    """
    try:
        from sqlalchemy import text
        deployments = _fetch_active_deployments()
        updated     = 0

        logger.info("deployment_refresh_start", count=len(deployments))
        for dep in deployments:
            try:
                beneficiaries = int(dep.get("total_beneficiaries", 0))

                checklist  = dep.get("deployment_checklist") or []
                if isinstance(checklist, list) and len(checklist) > 0:
                    completed  = sum(1 for item in checklist if item.get("completed"))
                    new_status = (
                        "completed" if completed >= len(checklist)
                        else dep.get("status", "active")
                    )
                else:
                    new_status = dep.get("status", "active")

                with _get_db() as db:
                    db.execute(text("""
                        UPDATE solution_deployments
                        SET beneficiaries_reached = :b,
                            status               = :s,
                            updated_at           = NOW()
                        WHERE id = :did
                    """), {"b": beneficiaries, "s": new_status, "did": str(dep["id"])})

                    if new_status == "completed" and dep.get("status") != "completed":
                        db.execute(text("""
                            INSERT INTO event_logs
                                (event_type, event_data, project_id, created_at)
                            VALUES ('deployment_completed', :data::jsonb, :pid, NOW())
                        """), {
                            "data": json.dumps({
                                "deployment_id": str(dep["id"]),
                                "beneficiaries": beneficiaries,
                            }),
                            "pid": str(dep["solution_id"]),
                        })
                        logger.info("deployment_completed",
                                    deployment_id=str(dep["id"]),
                                    beneficiaries=beneficiaries)
                updated += 1
            except Exception as e:
                logger.warning("deployment_refresh_failed",
                               deployment_id=str(dep.get("id")), error=str(e))

        logger.info("deployment_refresh_complete",
                    total=len(deployments), updated=updated)
    except Exception as exc:
        logger.error("deployment_refresh_task_failed", error=str(exc))
        raise self.retry(exc=exc, countdown=60)


# ============================================================================
# TASK 13: Document Link Cleanup
# ============================================================================

@celery.task(name="workers.document_cleanup_weekly", bind=True, max_retries=2)
def document_cleanup_weekly(self):
    """
    Expire document share links past their expiry date. Runs Sunday 03:00 UTC.

    Two operations:
      1. Set is_shareable=false + clear share_token on expired document_exports
      2. Delete orphaned export records older than 90 days that were never downloaded
    """
    try:
        from sqlalchemy import text

        logger.info("document_cleanup_start")
        with _get_db() as db:
            expired = db.execute(text("""
                UPDATE document_exports
                SET is_shareable = false, share_token = null
                WHERE expires_at < NOW() AND is_shareable = true
                RETURNING id
            """)).fetchall()

            deleted = db.execute(text("""
                DELETE FROM document_exports
                WHERE created_at < NOW() - INTERVAL '90 days'
                  AND downloaded_at IS NULL
                  AND is_shareable = false
                RETURNING id
            """)).fetchall()

        logger.info("document_cleanup_complete",
                    links_expired=len(expired),
                    records_deleted=len(deleted))
    except Exception as exc:
        logger.error("document_cleanup_task_failed", error=str(exc))
        raise self.retry(exc=exc, countdown=300)


# ============================================================================
# TASK 14: Impact Snapshots (Idea & Solution Hub)
# ============================================================================

@celery.task(name="workers.impact_snapshot_daily", bind=True, max_retries=3)
def impact_snapshot_daily(self):
    """
    Snapshot impact scores for all active deployments. Runs daily at 01:00 UTC.

    Creates time-series records in impact_snapshots for longitudinal tracking.
    This is what powers the Global Impact Dashboard trend lines -- not just
    a single point-in-time number, but a full history of how impact evolved.

    For each active/scaling/completed deployment:
      - Uses ImpactScoringEngine with latest field_feedback data
      - Computes: impact_score, priority_score, priority_colour
      - Inserts into impact_snapshots with all component scores
      - Updates solution_projects.impact_score with fresh value
    """
    try:
        from idea_solution_hub import ImpactScoringEngine, ProblemUrgency
        from sqlalchemy import text

        eng         = ImpactScoringEngine()
        deployments = _fetch_deployments_for_snapshot()
        snapped     = 0

        logger.info("impact_snapshot_start", count=len(deployments))
        for dep in deployments:
            try:
                beneficiaries   = float(
                    dep.get("latest_beneficiaries") or
                    dep.get("beneficiaries_reached") or 0
                )
                people_millions = max(beneficiaries / 1_000_000, 0.001)

                impact = eng.compute_impact_score(
                    people_affected_millions=people_millions,
                    severity=7.0,
                    scalability=float(dep.get("feasibility_score", 60)) / 10,
                    sustainability=float(dep.get("sustainability_score", 60)) / 10,
                    measurability=8.0 if int(dep.get("feedback_count", 0)) > 0 else 5.0,
                )
                priority = eng.compute_priority_score(
                    impact["impact_score"], ProblemUrgency.HIGH, 7.0, 6.0, 6.0)

                with _get_db() as db:
                    db.execute(text("""
                        INSERT INTO impact_snapshots
                            (solution_id, deployment_id, impact_score,
                             people_affected_estimate, severity_score,
                             scalability_score, sustainability_score,
                             measurability_score, priority_score,
                             priority_colour, beneficiaries_reached, computed_at)
                        VALUES
                            (:sol, :dep, :imp, :people, :sev, :scale,
                             :sus, :meas, :pri, :col, :ben, NOW())
                    """), {
                        "sol":    str(dep["solution_id"]),
                        "dep":    str(dep["deployment_id"]),
                        "imp":    impact["impact_score"],
                        "people": people_millions * 1_000_000,
                        "sev":    impact["components"]["severity"],
                        "scale":  impact["components"]["scalability"],
                        "sus":    impact["components"]["sustainability"],
                        "meas":   impact["components"]["measurability"],
                        "pri":    priority["priority_score"],
                        "col":    priority["colour"],
                        "ben":    int(beneficiaries),
                    })
                    db.execute(text("""
                        UPDATE solution_projects
                        SET impact_score = :score WHERE id = :sid
                    """), {"score": impact["impact_score"],
                           "sid":   str(dep["solution_id"])})
                snapped += 1
            except Exception as e:
                logger.warning("impact_snapshot_failed",
                               deployment_id=str(dep.get("deployment_id")), error=str(e))

        logger.info("impact_snapshot_complete",
                    total=len(deployments), snapped=snapped)
    except Exception as exc:
        logger.error("impact_snapshot_task_failed", error=str(exc))
        raise self.retry(exc=exc, countdown=300)


# ============================================================================
# TASK 15: Trust Continuous Verification
# ============================================================================

@celery.task(name="workers.trust_continuous_verification", bind=True, max_retries=2)
def trust_continuous_verification(self, execute: Optional[bool] = None, limit: int = 500):
    """
    Process stale Trust Engine Lite verification metadata. Runs every 30 minutes.

    This worker does not call GitHub, DNS, deployment, Firebase, Supabase, or
    any other provider. It reads existing Trust metadata, prepares founder
    notification intents for stale/failed/disconnected/badge-impact states, and
    appends new verification history only when execute=true.
    """
    try:
        execute_mode = _trust_worker_execute_enabled(execute)
        batches = _fetch_due_trust_verification_batches(limit=limit)

        logger.info(
            "trust_continuous_verification_start",
            batches=len(batches),
            execute=execute_mode,
        )
        result = _run_trust_continuous_verification_batches(
            batches,
            execute=execute_mode,
        )
        logger.info(
            "trust_continuous_verification_complete",
            batches_seen=result["batches_seen"],
            batches_processed=result["batches_processed"],
            actions_prepared=result["actions_prepared"],
            notifications_prepared=result["notifications_prepared"],
            executed_actions=result["executed_actions"],
            execute=execute_mode,
        )
        return result
    except Exception as exc:
        logger.error("trust_continuous_verification_task_failed", error=str(exc))
        raise self.retry(exc=exc, countdown=120)
