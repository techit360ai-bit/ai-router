"""Durable AI job submission helpers backed by the existing Celery/Redis stack."""

from __future__ import annotations

import json
import os
from typing import Any, Dict, Optional


def async_jobs_enabled() -> bool:
    return os.getenv("AI_ASYNC_JOBS_ENABLED", "false").lower() in {"1", "true", "yes", "on"}


def _redis_client():
    if not os.getenv("REDIS_URL"):
        return None
    try:
        import redis
        client = redis.Redis.from_url(os.environ["REDIS_URL"], decode_responses=True, socket_timeout=1)
        client.ping()
        return client
    except Exception:
        return None


def submit_incubation_job(*, user_id: str, payload: Dict[str, Any], idempotency_key: Optional[str] = None) -> Dict[str, Any]:
    if not async_jobs_enabled():
        raise RuntimeError("asynchronous AI jobs are disabled")
    redis = _redis_client()
    if redis is None:
        raise RuntimeError("asynchronous AI jobs require Redis")
    if idempotency_key:
        key = f"techit:ai:job:idempotency:{user_id}:{idempotency_key}"
        prior = redis.get(key)
        if prior:
            return {"job_id": prior, "idempotent": True}
    from workers.workers import celery
    task = celery.send_task("workers.incubation_pipeline", args=[payload])
    job_id = str(task.id)
    try:
        from hardening_metrics import METRICS
        METRICS.increment("incubation_jobs_submitted")
    except Exception:
        pass
    redis.setex(f"techit:ai:job:owner:{job_id}", int(os.getenv("AI_JOB_OWNER_TTL_SECONDS", "86400")), user_id)
    if idempotency_key:
        redis.setex(key, int(os.getenv("AI_JOB_IDEMPOTENCY_TTL_SECONDS", "86400")), job_id)
    return {"job_id": job_id, "status": "queued", "idempotent": False}


def job_status(*, user_id: str, job_id: str) -> Dict[str, Any]:
    redis = _redis_client()
    if redis is None:
        raise RuntimeError("asynchronous AI jobs require Redis")
    owner = redis.get(f"techit:ai:job:owner:{job_id}")
    if owner != user_id:
        raise PermissionError("job is outside the authenticated user's scope")
    from workers.workers import celery
    result = celery.AsyncResult(job_id)
    response: Dict[str, Any] = {"job_id": job_id, "status": result.status.lower()}
    if result.successful():
        response["result"] = result.result
    elif result.failed():
        response["error"] = str(result.result)
    elif isinstance(result.info, dict):
        response["progress"] = result.info
    return response
