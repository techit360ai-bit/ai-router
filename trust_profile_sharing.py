"""
Trust Engine Lite milestone review and profile sharing contracts.

Wave 40 keeps these flows metadata-only. Milestone evidence is represented by
URLs and scalar review metadata. Shared Trust Profiles are investor-safe views
that appear only after explicit founder opt-in.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional
from uuid import uuid4

from trust_engine_lite import TrustEngineComputer, VerificationSource, VerificationStatus


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _safe_scalar(value: Any) -> bool:
    return isinstance(value, (str, int, float, bool, datetime)) or value is None


def _scalar(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    return value


class TrustMilestoneReviewDecision(str):
    APPROVED = "approved"
    REJECTED = "rejected"
    PENDING = "pending"


@dataclass(frozen=True)
class TrustMilestoneReview:
    review_id: str
    milestone: str
    evidence_url: Optional[str]
    approval_status: str
    approved_by: Optional[str]
    confidence: float
    reason_code: str
    metadata: Dict[str, Any]
    metadata_hash: str
    dropped_fields: List[str]
    timeline_event: Dict[str, Any]
    raw_payload_stored: bool = False
    uploaded_file_stored: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "review_id": self.review_id,
            "milestone": self.milestone,
            "evidence_url": self.evidence_url,
            "approval_status": self.approval_status,
            "approved_by": self.approved_by,
            "confidence": self.confidence,
            "reason_code": self.reason_code,
            "metadata": dict(self.metadata),
            "metadata_hash": self.metadata_hash,
            "dropped_fields": list(self.dropped_fields),
            "timeline_event": dict(self.timeline_event),
            "raw_payload_stored": self.raw_payload_stored,
            "uploaded_file_stored": self.uploaded_file_stored,
        }


class TrustMilestoneReviewService:
    """Normalizes milestone admin review decisions without retaining raw evidence."""

    ALLOWED_FIELDS = {
        "milestone",
        "title",
        "evidence_url",
        "url",
        "approval_status",
        "approved_by",
        "confidence",
        "reason_code",
        "reference_id",
        "milestone_id",
        "visibility",
    }
    FORBIDDEN_TERMS = (
        "token",
        "secret",
        "password",
        "raw",
        "payload",
        "screenshot",
        "document_blob",
        "file",
        "attachment",
        "message",
        "contact",
    )

    def review(self, body: Optional[Dict[str, Any]] = None, now: Optional[datetime] = None) -> Dict[str, Any]:
        now = now or _utcnow()
        body = body or {}
        metadata: Dict[str, Any] = {}
        dropped: List[str] = []

        for key, value in body.items():
            key_lower = str(key).strip().lower()
            if self._drop(key_lower, value):
                dropped.append(str(key))
                continue
            metadata[key_lower] = _scalar(value)

        milestone = str(metadata.get("milestone") or metadata.get("title") or "Untitled milestone")
        evidence_url = metadata.get("evidence_url") or metadata.get("url")
        approval_status = self._status(metadata)
        confidence = self._confidence(approval_status, metadata)
        approved_by = metadata.get("approved_by") if approval_status == TrustMilestoneReviewDecision.APPROVED else None
        reason_code = str(metadata.get("reason_code") or self._reason(approval_status, evidence_url))

        normalized = {
            "milestone": milestone,
            "evidence_url": evidence_url,
            "approval_status": approval_status,
            "approved_by": approved_by,
            "verified": approval_status == TrustMilestoneReviewDecision.APPROVED,
            "confidence": confidence,
            "reason_code": reason_code,
        }
        timeline_event = {
            "event_type": f"milestone_{approval_status}",
            "source": VerificationSource.MILESTONE.value,
            "visibility": "public" if approval_status == TrustMilestoneReviewDecision.APPROVED else "private",
            "created_at": now.isoformat(),
            "reference_id": metadata.get("reference_id") or metadata.get("milestone_id"),
            "content_hash": TrustEngineComputer.hash_metadata(normalized),
        }
        return TrustMilestoneReview(
            review_id=f"trust_review_{uuid4().hex}",
            milestone=milestone,
            evidence_url=evidence_url,
            approval_status=approval_status,
            approved_by=approved_by,
            confidence=confidence,
            reason_code=reason_code,
            metadata=normalized,
            metadata_hash=TrustEngineComputer.hash_metadata(normalized),
            dropped_fields=sorted(set(dropped)),
            timeline_event=timeline_event,
        ).to_dict()

    def _drop(self, key: str, value: Any) -> bool:
        if key not in self.ALLOWED_FIELDS:
            return True
        if any(term in key for term in self.FORBIDDEN_TERMS):
            return True
        return not _safe_scalar(value)

    @staticmethod
    def _status(metadata: Dict[str, Any]) -> str:
        status = str(metadata.get("approval_status") or TrustMilestoneReviewDecision.PENDING).lower()
        if status in {
            TrustMilestoneReviewDecision.APPROVED,
            TrustMilestoneReviewDecision.REJECTED,
            TrustMilestoneReviewDecision.PENDING,
        }:
            return status
        return TrustMilestoneReviewDecision.PENDING

    @staticmethod
    def _confidence(status: str, metadata: Dict[str, Any]) -> float:
        try:
            supplied = float(metadata.get("confidence"))
        except (TypeError, ValueError):
            supplied = 0.0
        if supplied:
            return round(max(0.0, min(1.0, supplied)), 4)
        if status == TrustMilestoneReviewDecision.APPROVED:
            return 0.95
        if status == TrustMilestoneReviewDecision.REJECTED:
            return 0.2
        return 0.5

    @staticmethod
    def _reason(status: str, evidence_url: Any) -> str:
        if not evidence_url:
            return "missing_public_evidence"
        if status == TrustMilestoneReviewDecision.APPROVED:
            return "public_evidence_confirmed"
        if status == TrustMilestoneReviewDecision.REJECTED:
            return "evidence_not_confirmed"
        return "admin_review_required"


@dataclass(frozen=True)
class TrustShareProfile:
    share_id: str
    investor_visible: bool
    expires_at: datetime
    profile: Dict[str, Any]
    badges: List[Dict[str, Any]]
    timeline: List[Dict[str, Any]]
    metadata_hash: str
    privacy: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "share_id": self.share_id,
            "investor_visible": self.investor_visible,
            "expires_at": self.expires_at.isoformat(),
            "profile": dict(self.profile),
            "badges": list(self.badges),
            "timeline": list(self.timeline),
            "metadata_hash": self.metadata_hash,
            "privacy": dict(self.privacy),
        }


class TrustProfileSharingService:
    """Builds investor-safe Trust Profile previews after explicit founder opt-in."""

    PUBLIC_PROFILE_FIELDS = {
        "verification_status",
        "trust_score",
        "tier",
        "confidence_score",
        "signals",
        "breakdown",
        "last_sync_at",
        "computed_at",
    }
    PUBLIC_BADGE_FIELDS = {
        "badge_type",
        "label",
        "source",
        "status",
        "issued_at",
        "expires_at",
        "active",
    }
    PUBLIC_HISTORY_FIELDS = {
        "source",
        "status",
        "event_type",
        "expires_at",
        "created_at",
    }
    FORBIDDEN_TERMS = (
        "user_id",
        "email",
        "phone",
        "token",
        "secret",
        "raw",
        "payload",
        "metadata_hash",
        "reference_id",
        "subject_id",
    )

    def build(
        self,
        *,
        profile: Dict[str, Any],
        badges: Iterable[Dict[str, Any]],
        history: Iterable[Dict[str, Any]],
        settings: Optional[Dict[str, Any]] = None,
        now: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        now = now or _utcnow()
        settings = settings or {}
        share_enabled = settings.get("share_enabled") is True
        expiry_days = int(settings.get("expiry_days") or 30)
        expires_at = now + timedelta(days=max(1, min(expiry_days, 90)))

        public_profile = self._filter_dict(profile, self.PUBLIC_PROFILE_FIELDS)
        public_badges = [
            self._filter_dict(badge, self.PUBLIC_BADGE_FIELDS)
            for badge in badges
            if self._share_badge(badge, now)
        ]
        public_history = [
            self._filter_dict(item, self.PUBLIC_HISTORY_FIELDS)
            for item in history
            if item.get("status") in {VerificationStatus.VERIFIED.value, VerificationStatus.EXPIRED.value}
        ][: int(settings.get("timeline_limit") or 10)]

        payload = {
            "profile": public_profile if share_enabled else {},
            "badges": public_badges if share_enabled else [],
            "timeline": public_history if share_enabled else [],
            "expires_at": expires_at.isoformat(),
        }
        privacy = {
            "metadata_only": True,
            "founder_opt_in_required": True,
            "investor_visible_only_when_shared": share_enabled,
            "raw_payload_stored": False,
            "internal_ids_exposed": False,
            "expired_badges_hidden": True,
        }
        return TrustShareProfile(
            share_id=f"trust_share_{TrustEngineComputer.hash_metadata(payload)[:16]}",
            investor_visible=share_enabled,
            expires_at=expires_at,
            profile=payload["profile"],
            badges=payload["badges"],
            timeline=payload["timeline"],
            metadata_hash=TrustEngineComputer.hash_metadata(payload),
            privacy=privacy,
        ).to_dict()

    def _filter_dict(self, data: Dict[str, Any], allowed: set[str]) -> Dict[str, Any]:
        filtered = {}
        for key, value in (data or {}).items():
            key_lower = str(key).lower()
            if key not in allowed:
                continue
            if any(term in key_lower for term in self.FORBIDDEN_TERMS):
                continue
            keep, clean_value = self._public_value(value)
            if not keep:
                continue
            filtered[key] = clean_value
        return filtered

    def _share_badge(self, badge: Dict[str, Any], now: datetime) -> bool:
        if badge.get("status") != VerificationStatus.VERIFIED.value:
            return False
        if badge.get("active") is False:
            return False
        expires_at = self._parse_datetime(badge.get("expires_at"))
        return expires_at is None or expires_at > now

    @staticmethod
    def _parse_datetime(value: Any) -> Optional[datetime]:
        if isinstance(value, datetime):
            return value.replace(tzinfo=None)
        if isinstance(value, str) and value:
            try:
                return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
            except ValueError:
                return None
        return None

    def _public_value(self, value: Any) -> tuple[bool, Any]:
        if _safe_scalar(value):
            return True, _scalar(value)
        if isinstance(value, list):
            clean = []
            for item in value[:50]:
                keep, clean_item = self._public_value(item)
                if keep:
                    clean.append(clean_item)
            return True, clean
        if isinstance(value, dict):
            clean_dict = {}
            for key, item in list(value.items())[:50]:
                key_text = str(key)
                key_lower = key_text.lower()
                if any(term in key_lower for term in self.FORBIDDEN_TERMS):
                    continue
                keep, clean_item = self._public_value(item)
                if keep:
                    clean_dict[key_text] = clean_item
            return True, clean_dict
        return False, None
