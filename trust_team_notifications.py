"""
Trust Engine Lite team verification and notification intent contracts.

Wave 41 keeps team onboarding metadata-only. Teammate email addresses may be
used transiently to derive hashes/domains for invitation routing, but raw email,
HR records, contracts, payroll data, provider payloads, and secrets are never
returned or persisted by these contracts.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
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


def _safe_int(value: Any, default: int = 0, minimum: Optional[int] = None) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    if minimum is not None:
        return max(minimum, parsed)
    return parsed


def _email_domain(email: Any) -> Optional[str]:
    if not isinstance(email, str) or "@" not in email:
        return None
    domain = email.rsplit("@", 1)[-1].strip().lower()
    return domain or None


@dataclass(frozen=True)
class TrustTeamInvitation:
    invitation_id: str
    invitee_ref: str
    email_domain: Optional[str]
    status: str
    invited_by: Optional[str]
    metadata: Dict[str, Any]
    metadata_hash: str
    notification_intent: Dict[str, Any]
    dropped_fields: List[str]
    raw_email_stored: bool = False
    raw_payload_stored: bool = False
    hr_data_stored: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "invitation_id": self.invitation_id,
            "invitee_ref": self.invitee_ref,
            "email_domain": self.email_domain,
            "status": self.status,
            "invited_by": self.invited_by,
            "metadata": dict(self.metadata),
            "metadata_hash": self.metadata_hash,
            "notification_intent": dict(self.notification_intent),
            "dropped_fields": list(self.dropped_fields),
            "raw_email_stored": self.raw_email_stored,
            "raw_payload_stored": self.raw_payload_stored,
            "hr_data_stored": self.hr_data_stored,
        }


@dataclass(frozen=True)
class TrustTeamVerification:
    member_ref: str
    verification_status: str
    verified_team_count_delta: int
    pending_invitation_delta: int
    confidence: float
    metadata: Dict[str, Any]
    metadata_hash: str
    verification_metadata: Dict[str, Any]
    notification_intent: Dict[str, Any]
    dropped_fields: List[str]
    raw_email_stored: bool = False
    raw_payload_stored: bool = False
    hr_data_stored: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "member_ref": self.member_ref,
            "verification_status": self.verification_status,
            "verified_team_count_delta": self.verified_team_count_delta,
            "pending_invitation_delta": self.pending_invitation_delta,
            "confidence": self.confidence,
            "metadata": dict(self.metadata),
            "metadata_hash": self.metadata_hash,
            "verification_metadata": dict(self.verification_metadata),
            "notification_intent": dict(self.notification_intent),
            "dropped_fields": list(self.dropped_fields),
            "raw_email_stored": self.raw_email_stored,
            "raw_payload_stored": self.raw_payload_stored,
            "hr_data_stored": self.hr_data_stored,
        }


class TrustTeamVerificationService:
    """Builds metadata-only team invitation and teammate verification payloads."""

    INVITE_ALLOWED_FIELDS = {
        "teammate_email",
        "email",
        "invitee_email",
        "invited_by",
        "role",
        "teammate_role",
        "invitation_id",
        "team_size",
        "pending_invitations",
    }
    VERIFY_ALLOWED_FIELDS = {
        "teammate_email",
        "email",
        "invitee_email",
        "team_member_id",
        "invitation_id",
        "email_verified",
        "github_connected",
        "linkedin_connected",
        "verified",
        "confidence",
        "verified_team_count",
        "pending_invitations",
    }
    FORBIDDEN_TERMS = (
        "token",
        "secret",
        "password",
        "raw",
        "payload",
        "contract",
        "salary",
        "payroll",
        "hr_record",
        "document_blob",
        "file",
        "attachment",
        "message",
        "contact_list",
        "source_code",
    )

    def invite(self, body: Optional[Dict[str, Any]] = None, now: Optional[datetime] = None) -> Dict[str, Any]:
        now = now or _utcnow()
        body = body or {}
        metadata, dropped = self._sanitize(body, self.INVITE_ALLOWED_FIELDS)
        email = body.get("teammate_email") or body.get("invitee_email") or body.get("email")
        domain = _email_domain(email)
        invitee_ref = self._reference("team_invitee", email or body.get("invitation_id") or uuid4().hex)
        invitation_id = str(metadata.get("invitation_id") or f"trust_team_invite_{uuid4().hex}")

        normalized = {
            "invitee_ref": invitee_ref,
            "email_domain": domain,
            "status": VerificationStatus.PENDING.value,
            "invited_by": metadata.get("invited_by"),
            "teammate_role": metadata.get("teammate_role") or metadata.get("role"),
            "pending_invitations": _safe_int(metadata.get("pending_invitations"), default=1, minimum=1),
            "created_at": now.isoformat(),
        }
        normalized = {key: value for key, value in normalized.items() if value is not None}
        notification = self._notification(
            notification_type="trust_team_invitation_pending",
            source=VerificationSource.TEAM.value,
            severity="info",
            message="Team invitation is pending verification.",
            metadata=normalized,
            now=now,
        )
        return TrustTeamInvitation(
            invitation_id=invitation_id,
            invitee_ref=invitee_ref,
            email_domain=domain,
            status=VerificationStatus.PENDING.value,
            invited_by=metadata.get("invited_by"),
            metadata=normalized,
            metadata_hash=TrustEngineComputer.hash_metadata(normalized),
            notification_intent=notification,
            dropped_fields=dropped,
        ).to_dict()

    def verify(self, body: Optional[Dict[str, Any]] = None, now: Optional[datetime] = None) -> Dict[str, Any]:
        now = now or _utcnow()
        body = body or {}
        metadata, dropped = self._sanitize(body, self.VERIFY_ALLOWED_FIELDS)
        email = body.get("teammate_email") or body.get("invitee_email") or body.get("email")
        member_seed = body.get("team_member_id") or body.get("invitation_id") or email or uuid4().hex
        member_ref = self._reference("team_member", member_seed)

        status = self._status(metadata)
        confidence = self._confidence(status, metadata)
        verified_delta = 1 if status == VerificationStatus.VERIFIED.value else 0
        pending_delta = -1 if status == VerificationStatus.VERIFIED.value else 0
        verified_count = max(
            verified_delta,
            _safe_int(metadata.get("verified_team_count"), default=verified_delta),
        )
        pending_count = max(0, _safe_int(metadata.get("pending_invitations"), default=0) + pending_delta)

        normalized = {
            "member_ref": member_ref,
            "email_domain": _email_domain(email),
            "email_verified": bool(metadata.get("email_verified")) or status == VerificationStatus.VERIFIED.value,
            "github_connected": bool(metadata.get("github_connected")),
            "linkedin_connected": bool(metadata.get("linkedin_connected")),
            "verification_status": status,
            "confidence": confidence,
            "verified_team_count": verified_count,
            "pending_invitations": pending_count,
            "verified_at": now.isoformat() if status == VerificationStatus.VERIFIED.value else None,
        }
        normalized = {key: value for key, value in normalized.items() if value is not None}
        verification_metadata = {
            "verified": status == VerificationStatus.VERIFIED.value,
            "confidence": confidence,
            "verified_team_count": verified_count,
            "pending_invitations": pending_count,
        }
        notification = self._notification(
            notification_type="trust_team_member_verified"
            if status == VerificationStatus.VERIFIED.value
            else "trust_team_verification_pending",
            source=VerificationSource.TEAM.value,
            severity="info" if status == VerificationStatus.VERIFIED.value else "warning",
            message="Team member verification updated.",
            metadata=normalized,
            now=now,
        )
        return TrustTeamVerification(
            member_ref=member_ref,
            verification_status=status,
            verified_team_count_delta=verified_delta,
            pending_invitation_delta=pending_delta,
            confidence=confidence,
            metadata=normalized,
            metadata_hash=TrustEngineComputer.hash_metadata(normalized),
            verification_metadata=verification_metadata,
            notification_intent=notification,
            dropped_fields=dropped,
        ).to_dict()

    def _sanitize(self, body: Dict[str, Any], allowed: set[str]) -> tuple[Dict[str, Any], List[str]]:
        clean: Dict[str, Any] = {}
        dropped: List[str] = []
        for key, value in body.items():
            key_lower = str(key).strip().lower()
            if self._drop(key_lower, value, allowed):
                dropped.append(str(key))
                continue
            if key_lower in {"teammate_email", "invitee_email", "email"}:
                continue
            clean[key_lower] = _scalar(value)
        return clean, sorted(set(dropped))

    def _drop(self, key: str, value: Any, allowed: set[str]) -> bool:
        if key not in allowed:
            return True
        if any(term in key for term in self.FORBIDDEN_TERMS):
            return True
        return not _safe_scalar(value)

    @staticmethod
    def _reference(prefix: str, value: Any) -> str:
        digest = TrustEngineComputer.hash_metadata({"value": str(value).strip().lower()})[:24]
        return f"{prefix}_{digest}"

    @staticmethod
    def _status(metadata: Dict[str, Any]) -> str:
        if metadata.get("verified") is True or metadata.get("email_verified") is True:
            return VerificationStatus.VERIFIED.value
        return VerificationStatus.PENDING.value

    @staticmethod
    def _confidence(status: str, metadata: Dict[str, Any]) -> float:
        try:
            supplied = float(metadata.get("confidence"))
        except (TypeError, ValueError):
            supplied = 0.0
        if supplied:
            return round(max(0.0, min(1.0, supplied)), 4)
        return 0.9 if status == VerificationStatus.VERIFIED.value else 0.5

    @staticmethod
    def _notification(
        *,
        notification_type: str,
        source: str,
        severity: str,
        message: str,
        metadata: Dict[str, Any],
        now: datetime,
    ) -> Dict[str, Any]:
        notification_metadata = {
            "notification_type": notification_type,
            "source": source,
            "severity": severity,
            "created_at": now.isoformat(),
            "metadata_hash": TrustEngineComputer.hash_metadata(metadata),
        }
        return {
            "notification_id": f"trust_note_{uuid4().hex}",
            "notification_type": notification_type,
            "source": source,
            "severity": severity,
            "message": message,
            "action_required": severity in {"warning", "critical"},
            "created_at": now.isoformat(),
            "metadata_hash": TrustEngineComputer.hash_metadata(notification_metadata),
            "founder_visible": True,
            "investor_visible": False,
            "raw_payload_stored": False,
        }


class TrustNotificationPreviewService:
    """Builds founder-only Trust notification intents from safe event metadata."""

    ALLOWED_FIELDS = {
        "notification_type",
        "source",
        "provider",
        "status",
        "severity",
        "message",
        "action_required",
        "created_at",
    }
    FORBIDDEN_TERMS = TrustTeamVerificationService.FORBIDDEN_TERMS + (
        "email",
        "phone",
        "user_id",
        "subject_id",
        "reference_id",
        "metadata_hash",
    )

    def preview(
        self,
        events: Optional[Iterable[Dict[str, Any]]] = None,
        now: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        now = now or _utcnow()
        event_list = [event for event in events or [] if isinstance(event, dict)]
        intents = []
        dropped_fields: List[str] = []
        for event in event_list:
            clean, dropped = self._sanitize_event(event)
            dropped_fields.extend(dropped)
            if not clean:
                continue
            intents.append(self._intent(clean, now))

        return {
            "generated_at": now.isoformat(),
            "notification_intents": intents,
            "summary": {
                "events_seen": len(event_list),
                "notifications_prepared": len(intents),
            },
            "dropped_fields": sorted(set(dropped_fields)),
            "privacy": {
                "metadata_only": True,
                "founder_notifications_only": True,
                "investor_notifications": False,
                "delivery_executed": False,
                "raw_payload_stored": False,
            },
        }

    def _sanitize_event(self, event: Dict[str, Any]) -> tuple[Dict[str, Any], List[str]]:
        clean: Dict[str, Any] = {}
        dropped: List[str] = []
        for key, value in event.items():
            key_lower = str(key).strip().lower()
            if key_lower not in self.ALLOWED_FIELDS:
                dropped.append(str(key))
                continue
            if any(term in key_lower for term in self.FORBIDDEN_TERMS) or not _safe_scalar(value):
                dropped.append(str(key))
                continue
            clean[key_lower] = _scalar(value)
        return clean, dropped

    def _intent(self, event: Dict[str, Any], now: datetime) -> Dict[str, Any]:
        notification_type = str(event.get("notification_type") or self._type_for(event))
        severity = str(event.get("severity") or self._severity(notification_type))
        metadata = {
            "notification_type": notification_type,
            "source": event.get("source"),
            "provider": event.get("provider"),
            "status": event.get("status"),
            "created_at": event.get("created_at") or now.isoformat(),
        }
        return {
            "notification_id": f"trust_note_{uuid4().hex}",
            "notification_type": notification_type,
            "source": event.get("source"),
            "provider": event.get("provider"),
            "severity": severity,
            "message": str(event.get("message") or self._message(notification_type)),
            "action_required": bool(event.get("action_required")) or severity in {"warning", "critical"},
            "created_at": now.isoformat(),
            "metadata_hash": TrustEngineComputer.hash_metadata(metadata),
            "founder_visible": True,
            "investor_visible": False,
            "raw_payload_stored": False,
        }

    @staticmethod
    def _type_for(event: Dict[str, Any]) -> str:
        status = str(event.get("status") or "").lower()
        if status == VerificationStatus.EXPIRED.value:
            return "trust_verification_expired"
        if status == VerificationStatus.FAILED.value:
            return "trust_verification_failed"
        if status == VerificationStatus.DISCONNECTED.value:
            return "trust_integration_disconnected"
        return "trust_verification_pending"

    @staticmethod
    def _severity(notification_type: str) -> str:
        if notification_type == "trust_verification_expired":
            return "critical"
        if notification_type in {"trust_verification_failed", "trust_integration_disconnected"}:
            return "warning"
        return "info"

    @staticmethod
    def _message(notification_type: str) -> str:
        messages = {
            "trust_verification_expired": "A Trust verification expired and needs refresh.",
            "trust_verification_failed": "A Trust verification failed and needs review.",
            "trust_integration_disconnected": "A Trust integration was disconnected.",
            "trust_badge_changed": "A Trust badge changed.",
            "trust_manual_review_required": "A Trust item requires manual review.",
        }
        return messages.get(notification_type, "Trust verification update.")
