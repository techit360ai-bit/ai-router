"""Evidence-based product-stage inference for FastTrack and incubation.

FastTrack accepts startups at wildly different maturity: a founder may paste an
idea and a doc, a half-built prototype repo, or a live product that already has
beta users. Previously the product stage was a free-text field the founder set
by hand, so nothing distinguished "MVP code" from "already launched" and the
agents could not calibrate.

This module derives a normalized stage from observable evidence and keeps the
founder's explicit choice as an override. It is deterministic, has no LLM call,
and never invents a stage it cannot support with a signal.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Mapping, Optional

# Ordered maturity ladder. Higher index == more mature.
STAGE_LADDER = ["idea", "prototype", "mvp", "beta", "launched", "growth"]

# Founder-supplied stage strings mapped onto the ladder (manual override).
_STAGE_ALIASES = {
    "idea": "idea",
    "concept": "idea",
    "research": "idea",
    "validation": "prototype",
    "prototype": "prototype",
    "design": "prototype",
    "mvp": "mvp",
    "building_mvp": "mvp",
    "build": "mvp",
    "pre_seed": "mvp",
    "preseed": "mvp",
    "beta": "beta",
    "private_beta": "beta",
    "launched": "launched",
    "live": "launched",
    "seed": "launched",
    "growth": "growth",
    "scaling": "growth",
    "scale": "growth",
    "series_a": "growth",
    "series-a": "growth",
    "seriesa": "growth",
}

RECENT_PUSH_DAYS = 120


def _norm(value: Any) -> str:
    return str(value or "").strip().lower().replace(" ", "_")


def _recent_push(pushed_at: Any) -> bool:
    text = str(pushed_at or "").strip()
    if not text:
        return False
    try:
        moment = datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return False
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - moment).days <= RECENT_PUSH_DAYS


def infer_product_stage(
    venture_data: Mapping[str, Any],
    codebase_context: Optional[Mapping[str, Any]] = None,
    *,
    has_revenue: bool = False,
    beta_users_count: int = 0,
) -> Dict[str, Any]:
    """Return ``{stage, inferred, source, confidence, signals, rationale}``.

    ``stage`` is what downstream agents should calibrate to (the manual value
    when the founder set one, otherwise the inferred value); ``inferred`` is
    always the evidence-derived stage so a mismatch is visible.
    """
    context = codebase_context or {}
    signals: Dict[str, Any] = {}
    reasons = []

    has_repo = bool(venture_data.get("repo_url") or context)
    recent_push = _recent_push(context.get("pushed_at"))
    file_count = int(context.get("file_count") or 0)
    stars = int(context.get("stars") or 0)
    languages = str(context.get("languages") or "").strip()
    has_doc = bool(venture_data.get("document_id"))
    users = max(0, int(beta_users_count or 0))

    signals.update({
        "has_repo": has_repo,
        "recent_push": recent_push,
        "has_document": has_doc,
        "has_revenue": bool(has_revenue),
        "beta_users": users,
        "languages": languages or None,
        "stars": stars,
        "file_count": file_count,
    })

    if has_revenue:
        inferred = "growth" if users >= 1000 else "launched"
        reasons.append("revenue is active")
    elif users >= 100:
        inferred = "launched"
        reasons.append(f"{users} beta users reported")
    elif users >= 10:
        inferred = "beta"
        reasons.append(f"{users} beta users reported")
    elif has_repo and (recent_push or stars > 0):
        inferred = "mvp"
        reasons.append("codebase present with recent activity")
    elif has_repo or has_doc:
        inferred = "prototype"
        reasons.append("prototype/codebase or design document present")
    else:
        inferred = "idea"
        reasons.append("no codebase, document or traction signals")

    # An explicit "is this already launched?" answer is the strongest manual
    # signal; otherwise prefer the product-stage field over the funding stage.
    if venture_data.get("already_launched") is True:
        manual_raw = "launched"
    else:
        manual_raw = _norm(venture_data.get("product_stage") or venture_data.get("stage"))
    manual = _STAGE_ALIASES.get(manual_raw)
    source = "auto"
    stage = inferred
    confidence = "high" if (has_repo or users or has_revenue or has_doc) else "low"
    if manual:
        stage = manual
        source = "manual"
        if manual != inferred:
            reasons.append(f"founder selected '{manual}' (evidence suggests '{inferred}')")
        else:
            reasons.append(f"founder selection '{manual}' matches the evidence")
    else:
        reasons.append(f"auto-detected '{inferred}' from FastTrack inputs")

    return {
        "stage": stage,
        "inferred": inferred,
        "source": source,
        "manual": manual,
        "mismatch": bool(manual and manual != inferred),
        "confidence": confidence,
        "signals": signals,
        "rationale": "; ".join(reasons),
    }
