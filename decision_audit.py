"""Privacy-safe audit events for consequential ranking decisions."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, Mapping
from uuid import uuid4

from policy_registry import policy_metadata


logger = logging.getLogger("techit.decision_audit")


class DecisionAuditError(RuntimeError):
    """Raised when privacy-safe decision auditing cannot be performed."""


def _audit_key() -> bytes:
    configured = os.getenv("DECISION_AUDIT_HMAC_KEY", "").strip()
    environment = os.getenv("ENVIRONMENT", "development").strip().lower()
    if not configured and environment in {"production", "staging"}:
        raise DecisionAuditError("DECISION_AUDIT_HMAC_KEY is required for production decision auditing")
    return (configured or "development-decision-audit-key").encode("utf-8")


def privacy_safe_ref(value: Any) -> str:
    digest = hmac.new(_audit_key(), str(value).encode("utf-8"), hashlib.sha256).hexdigest()
    return f"ref_{digest[:20]}"


def _evidence_band(candidate: Mapping[str, Any]) -> str:
    completeness = candidate.get("profile_signals", {}).get("profile_completeness_pct")
    try:
        score = float(completeness)
    except (TypeError, ValueError):
        return "unknown"
    if score >= 80:
        return "high"
    if score >= 50:
        return "medium"
    return "low"


def build_ranking_audit(
    candidates: Iterable[Mapping[str, Any]],
    evidence_status: str,
) -> Dict[str, Any]:
    ranked = list(candidates)
    exposure = [
        {
            "rank": index,
            "candidate_ref": privacy_safe_ref(candidate.get("user_id")),
            "evidence_quality_band": _evidence_band(candidate),
        }
        for index, candidate in enumerate(ranked, start=1)
    ]
    return {
        "event_id": str(uuid4()),
        "event_type": "collaborator_ranking",
        "occurred_at": datetime.now(timezone.utc).isoformat(),
        "policy": policy_metadata(),
        "evidence_status": evidence_status,
        "candidates_returned": len(ranked),
        "ranking_exposure": exposure,
        "outcome_parity": {
            "status": "insufficient_outcome_evidence",
            "observed_outcomes": 0,
        },
        "protected_attributes_used": False,
        "sensitive_profile_fields_recorded": False,
    }


class DecisionAuditRecorder:
    """Default structured-log sink; production log export owns persistence."""

    def record(self, event: Mapping[str, Any]) -> None:
        logger.info("decision_audit %s", json.dumps(dict(event), sort_keys=True))
