"""
TECHIT AI INCUBATION PLATFORM
==============================
workers.py -- Celery Background Workers

14 scheduled tasks covering:
  - Daily Tour Guide check-ins
  - Weekly summaries
  - EVI-I investor signals
  - Adaptive curriculum generation
  - GSIS/WCRS score refresh
  - Stagnation detection
  - Monthly credit resets
  - Admin anomaly scanning
  - Investor alert checks
  - Problem discovery (Idea & Solution Hub)
  - Discussion moderation (Idea & Solution Hub)
  - Deployment status refresh
  - Document link cleanup
  - Impact snapshots

Start workers:
    celery -A workers.celery worker --loglevel=info -Q ai_heavy,ai_light,scheduled

Start scheduler (beat):
    celery -A workers.celery beat --loglevel=info

Monitor (Flower):
    celery -A workers.celery flower --port=5555
"""

import asyncio
import structlog
from celery import Celery
from celery.schedules import crontab

logger = structlog.get_logger()


# ============================================================================
# CELERY CONFIGURATION
# ============================================================================

celery = Celery(
    "techit_workers",
    broker="redis://redis:6379",
    backend="redis://redis:6379",
)

celery.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    # Route heavy AI tasks to dedicated queue
    task_routes={
        "workers.daily_tour_guide": {"queue": "ai_light"},
        "workers.weekly_summaries": {"queue": "ai_heavy"},
        "workers.daily_investor_signals": {"queue": "ai_heavy"},
        "workers.adaptive_curriculum_weekly": {"queue": "ai_heavy"},
        "workers.wcrs_gsis_refresh": {"queue": "scheduled"},
        "workers.stagnation_roster": {"queue": "scheduled"},
        "workers.monthly_credit_reset": {"queue": "scheduled"},
        "workers.admin_anomaly_scan": {"queue": "ai_light"},
        "workers.investor_alert_check": {"queue": "scheduled"},
        "workers.problem_discovery_daily": {"queue": "ai_light"},
        "workers.discussion_moderation_hourly": {"queue": "ai_light"},
        "workers.deployment_status_refresh": {"queue": "scheduled"},
        "workers.document_cleanup_weekly": {"queue": "scheduled"},
        "workers.impact_snapshot_daily": {"queue": "scheduled"},
    },
    # Retry failed tasks up to 3 times with exponential backoff
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    task_default_retry_delay=60,
    task_max_retries=3,
)


# ============================================================================
# BEAT SCHEDULE -- 14 TASKS
# ============================================================================

celery.conf.beat_schedule = {
    # ── Daily at 06:00 UTC ─────────────────────────────────────────────────
    "daily-tour-guide": {
        "task": "workers.daily_tour_guide",
        "schedule": crontab(hour=6, minute=0),
    },
    # ── Sunday at 18:00 UTC ────────────────────────────────────────────────
    "weekly-summaries": {
        "task": "workers.weekly_summaries",
        "schedule": crontab(hour=18, minute=0, day_of_week=0),
    },
    # ── Daily at 00:00 UTC ─────────────────────────────────────────────────
    "daily-investor-signals": {
        "task": "workers.daily_investor_signals",
        "schedule": crontab(hour=0, minute=0),
    },
    # ── Monday at 02:00 UTC ────────────────────────────────────────────────
    "adaptive-curriculum-weekly": {
        "task": "workers.adaptive_curriculum_weekly",
        "schedule": crontab(hour=2, minute=0, day_of_week=1),
    },
    # ── Every 30 minutes ───────────────────────────────────────────────────
    "wcrs-gsis-refresh": {
        "task": "workers.wcrs_gsis_refresh",
        "schedule": crontab(minute="*/30"),
    },
    # ── Daily at 07:00 UTC ─────────────────────────────────────────────────
    "stagnation-roster": {
        "task": "workers.stagnation_roster",
        "schedule": crontab(hour=7, minute=0),
    },
    # ── 1st of each month at 00:00 UTC ─────────────────────────────────────
    "monthly-credit-reset": {
        "task": "workers.monthly_credit_reset",
        "schedule": crontab(hour=0, minute=0, day_of_month=1),
    },
    # ── Every 15 minutes ───────────────────────────────────────────────────
    "admin-anomaly-scan": {
        "task": "workers.admin_anomaly_scan",
        "schedule": crontab(minute="*/15"),
    },
    # ── Every 5 minutes ────────────────────────────────────────────────────
    "investor-alert-check": {
        "task": "workers.investor_alert_check",
        "schedule": crontab(minute="*/5"),
    },
    # ── Idea & Solution Hub: Daily at 06:00 UTC ────────────────────────────
    "problem-discovery-daily": {
        "task": "workers.problem_discovery_daily",
        "schedule": crontab(hour=6, minute=0),
    },
    # ── Idea & Solution Hub: Every hour ────────────────────────────────────
    "discussion-moderation-hourly": {
        "task": "workers.discussion_moderation_hourly",
        "schedule": crontab(minute=0),
    },
    # ── Idea & Solution Hub: Every 15 minutes ──────────────────────────────
    "deployment-status-refresh": {
        "task": "workers.deployment_status_refresh",
        "schedule": crontab(minute="*/15"),
    },
    # ── Document Generation: Sunday at 03:00 UTC ───────────────────────────
    "document-cleanup-weekly": {
        "task": "workers.document_cleanup_weekly",
        "schedule": crontab(hour=3, minute=0, day_of_week=0),
    },
    # ── Idea & Solution Hub: Daily at 01:00 UTC ────────────────────────────
    "impact-snapshot-daily": {
        "task": "workers.impact_snapshot_daily",
        "schedule": crontab(hour=1, minute=0),
    },
}


# ============================================================================
# HELPER: get TechIT brain (one per task execution)
# ============================================================================

def _get_brain():
    """
    Each Celery task creates its own TechITAIBrain instance.
    The singleton pattern applies per-process -- workers each get their own.
    """
    from integration_guide import TechITAIBrain
    return TechITAIBrain()


# ============================================================================
# TASK 1: Daily Tour Guide
# ============================================================================

@celery.task(name="workers.daily_tour_guide", bind=True, max_retries=3)
def daily_tour_guide(self):
    """Daily check-in for all active users. Runs at 06:00 UTC."""
    try:
        from integration_guide import TourGuideService
        brain = _get_brain()
        svc = TourGuideService(brain)
        users = _fetch_active_users()
        logger.info("daily_tour_guide_start", user_count=len(users))
        for user in users:
            asyncio.run(svc.daily_check_in(user))
        logger.info("daily_tour_guide_complete", processed=len(users))
    except Exception as exc:
        logger.error("daily_tour_guide_failed", error=str(exc))
        raise self.retry(exc=exc, countdown=300)

# (rest remains unchanged...)
