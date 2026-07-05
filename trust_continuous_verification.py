"""
Trust Engine Lite continuous verification runner contracts.

This module turns refresh-plan entries into metadata-only verification actions
and founder notification intents. It performs no provider network calls and
stores no raw payloads, tokens, logs, source code, analytics events, or files.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional
from uuid import uuid4

from trust_engine_lite import TrustEngineComputer, VerificationStatus
from trust_integration_adapters import TrustIntegrationAdapterRegistry, TrustRefreshPlanner


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


@dataclass(frozen=True)
class TrustNotificationIntent:
    notification_id: str
    user_id: str
    project_id: Optional[str]
    notification_type: str
    source: str
    provider: str
    severity: str
    title: str
    message: str
    action_required: bool
    created_at: datetime
    metadata_hash: str
    investor_visible: bool = False
    raw_payload_stored: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "notification_id": self.notification_id,
            "user_id": self.user_id,
            "project_id": self.project_id,
            "notification_type": self.notification_type,
            "source": self.source,
            "provider": self.provider,
            "severity": self.severity,
            "title": self.title,
            "message": self.message,
            "action_required": self.action_required,
            "created_at": self.created_at.isoformat(),
            "metadata_hash": self.metadata_hash,
            "investor_visible": self.investor_visible,
            "raw_payload_stored": self.raw_payload_stored,
        }


@dataclass(frozen=True)
class TrustVerificationAction:
    action_id: str
    action_type: str
    source: str
    provider: str
    status: str
    confidence: float
    metadata: Dict[str, Any]
    metadata_hash: str
    reason: str
    dropped_fields: List[str]
    execute_recommended: bool
    raw_payload_stored: bool = False
    tokens_stored: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "action_id": self.action_id,
            "action_type": self.action_type,
            "source": self.source,
            "provider": self.provider,
            "status": self.status,
            "confidence": self.confidence,
            "metadata": dict(self.metadata),
            "metadata_hash": self.metadata_hash,
            "reason": self.reason,
            "dropped_fields": list(self.dropped_fields),
            "execute_recommended": self.execute_recommended,
            "raw_payload_stored": self.raw_payload_stored,
            "tokens_stored": self.tokens_stored,
        }


class TrustContinuousVerificationRunner:
    """
    Prepares continuous-verification work from existing metadata.

    The runner never fetches provider data. If a future scheduler has already
    collected provider metadata, it can pass it in through `adapter_payloads`.
    Otherwise the runner emits explicit pending/expired/failed marker actions.
    """

    def __init__(self, registry: Optional[TrustIntegrationAdapterRegistry] = None) -> None:
        self.registry = registry or TrustIntegrationAdapterRegistry.default()
        self.planner = TrustRefreshPlanner()

    def prepare(
        self,
        *,
        user_id: str,
        project_id: Optional[str],
        connections: Iterable[Dict[str, Any]],
        adapter_payloads: Optional[Dict[str, Dict[str, Any]]] = None,
        now: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        now = now or _utcnow()
        adapter_payloads = adapter_payloads or {}
        connection_list = [dict(conn) for conn in connections if isinstance(conn, dict)]
        plan = self.planner.plan(connection_list, now=now)
        notifications: List[Dict[str, Any]] = []
        actions: List[Dict[str, Any]] = []
        badge_notifications = 0

        for item in plan["items"]:
            if item.get("notification_type"):
                notifications.append(self._notification(user_id, project_id, item, now).to_dict())

            source_connection = self._connection_for_item(item, connection_list)
            badge_change_notes = self._badge_change_notifications(
                user_id,
                project_id,
                item,
                source_connection,
                now,
            )
            badge_notifications += len(badge_change_notes)
            notifications.extend(note.to_dict() for note in badge_change_notes)

            action = self._action_for_item(item, adapter_payloads, now)
            if action:
                actions.append(action.to_dict())

        return {
            "generated_at": now.isoformat(),
            "user_id": user_id,
            "project_id": project_id,
            "plan": plan,
            "verification_actions": actions,
            "notification_intents": notifications,
            "summary": {
                "connections_seen": len(plan["items"]),
                "actions_prepared": len(actions),
                "notifications_prepared": len(notifications),
                "badge_notifications_prepared": badge_notifications,
                "due_count": plan["due_count"],
                "expired_count": plan["expired_count"],
            },
            "privacy": {
                "metadata_only": True,
                "raw_payload_stored": False,
                "tokens_stored": False,
                "provider_calls_executed": False,
                "failure_deletes_existing_data": False,
                "investor_notifications": False,
            },
        }

    @staticmethod
    def _connection_for_item(item: Dict[str, Any], connections: List[Dict[str, Any]]) -> Dict[str, Any]:
        source = str(item.get("source") or "")
        provider = str(item.get("provider") or "")
        for connection in connections:
            if (
                str(connection.get("source") or "") == source
                and str(connection.get("provider") or connection.get("source") or "") == provider
            ):
                return connection
        for connection in connections:
            if str(connection.get("source") or "") == source:
                return connection
        return {}

    def _action_for_item(
        self,
        item: Dict[str, Any],
        adapter_payloads: Dict[str, Dict[str, Any]],
        now: datetime,
    ) -> Optional[TrustVerificationAction]:
        if not item.get("should_refresh"):
            return None
        if item["verification_state"] == VerificationStatus.DISCONNECTED.value:
            return None

        provider = item["provider"]
        source = item["source"]
        payload = self._payload_for(provider, source, adapter_payloads)
        if payload is not None:
            adapter_result = self.registry.normalize(provider, payload, now=now)
            return TrustVerificationAction(
                action_id=f"trust_action_{uuid4().hex}",
                action_type="adapter_metadata",
                source=adapter_result.source,
                provider=adapter_result.provider,
                status=adapter_result.status,
                confidence=adapter_result.confidence,
                metadata=dict(adapter_result.metadata),
                metadata_hash=adapter_result.metadata_hash,
                reason="Provider metadata was supplied by a scheduler adapter and normalized before verification.",
                dropped_fields=list(adapter_result.dropped_fields),
                execute_recommended=True,
                raw_payload_stored=adapter_result.raw_payload_stored,
                tokens_stored=adapter_result.tokens_stored,
            )

        status = self._marker_status(item)
        confidence = float(item.get("confidence_multiplier") or 0.5)
        metadata = {
            "verified": False,
            "confidence": round(max(0.0, min(1.0, confidence)), 4),
        }
        return TrustVerificationAction(
            action_id=f"trust_action_{uuid4().hex}",
            action_type=f"mark_{status}",
            source=source,
            provider=provider,
            status=status,
            confidence=metadata["confidence"],
            metadata=metadata,
            metadata_hash=TrustEngineComputer.hash_metadata(metadata),
            reason=item["reason"],
            dropped_fields=[],
            execute_recommended=True,
        )

    @staticmethod
    def _payload_for(provider: str, source: str, payloads: Dict[str, Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        for key in (provider, source):
            payload = payloads.get(key)
            if isinstance(payload, dict):
                return payload
        return None

    @staticmethod
    def _marker_status(item: Dict[str, Any]) -> str:
        state = item["verification_state"]
        if state in {
            VerificationStatus.EXPIRED.value,
            VerificationStatus.FAILED.value,
            VerificationStatus.PENDING.value,
        }:
            return state
        return VerificationStatus.PENDING.value

    def _notification(
        self,
        user_id: str,
        project_id: Optional[str],
        item: Dict[str, Any],
        now: datetime,
    ) -> TrustNotificationIntent:
        notification_type = item["notification_type"]
        severity = self._severity(notification_type)
        title = self._title(notification_type)
        message = self._message(item)
        notification_metadata = {
            "notification_type": notification_type,
            "source": item["source"],
            "provider": item["provider"],
            "verification_state": item["verification_state"],
            "created_at": now.isoformat(),
        }
        return TrustNotificationIntent(
            notification_id=f"trust_note_{uuid4().hex}",
            user_id=user_id,
            project_id=project_id,
            notification_type=notification_type,
            source=item["source"],
            provider=item["provider"],
            severity=severity,
            title=title,
            message=message,
            action_required=severity in {"warning", "critical"},
            created_at=now,
            metadata_hash=TrustEngineComputer.hash_metadata(notification_metadata),
        )

    def _badge_change_notifications(
        self,
        user_id: str,
        project_id: Optional[str],
        item: Dict[str, Any],
        connection: Dict[str, Any],
        now: datetime,
    ) -> List[TrustNotificationIntent]:
        badges = self._badge_refs(connection)
        if not badges:
            return []

        state = item["verification_state"]
        if state == VerificationStatus.VERIFIED.value and not item.get("should_refresh"):
            return []
        if state not in {
            VerificationStatus.EXPIRED.value,
            VerificationStatus.FAILED.value,
            VerificationStatus.DISCONNECTED.value,
            VerificationStatus.PENDING.value,
        }:
            return []

        badge_labels = [badge["label"] for badge in badges]
        badge_types = [badge["badge_type"] for badge in badges]
        notification_metadata = {
            "notification_type": "trust_badge_status_changed",
            "source": item["source"],
            "provider": item["provider"],
            "verification_state": state,
            "badge_types": badge_types,
            "created_at": now.isoformat(),
        }
        severity = "critical" if state == VerificationStatus.EXPIRED.value else "warning"
        return [
            TrustNotificationIntent(
                notification_id=f"trust_note_{uuid4().hex}",
                user_id=user_id,
                project_id=project_id,
                notification_type="trust_badge_status_changed",
                source=item["source"],
                provider=item["provider"],
                severity=severity,
                title="Trust badge status changed",
                message=self._badge_change_message(item, badge_labels),
                action_required=True,
                created_at=now,
                metadata_hash=TrustEngineComputer.hash_metadata(notification_metadata),
            )
        ]

    @staticmethod
    def _badge_refs(connection: Dict[str, Any]) -> List[Dict[str, str]]:
        raw_badges = connection.get("badges") or connection.get("active_badges") or []
        if isinstance(raw_badges, dict):
            raw_badges = [raw_badges]
        if not isinstance(raw_badges, list):
            raw_badges = []

        refs: List[Dict[str, str]] = []
        for badge in raw_badges:
            if isinstance(badge, str) and badge.strip():
                refs.append({"badge_type": badge.strip(), "label": badge.strip()})
            elif isinstance(badge, dict):
                badge_type = str(badge.get("badge_type") or badge.get("type") or "").strip()
                label = str(badge.get("label") or badge_type).strip()
                if badge_type or label:
                    refs.append({"badge_type": badge_type or label, "label": label or badge_type})

        badge_types = connection.get("badge_types") or []
        badge_labels = connection.get("badge_labels") or []
        if isinstance(badge_types, str):
            badge_types = [badge_types]
        if isinstance(badge_labels, str):
            badge_labels = [badge_labels]
        if isinstance(badge_types, list):
            for index, badge_type in enumerate(badge_types):
                badge_type_text = str(badge_type or "").strip()
                if not badge_type_text:
                    continue
                label = ""
                if isinstance(badge_labels, list) and index < len(badge_labels):
                    label = str(badge_labels[index] or "").strip()
                refs.append({"badge_type": badge_type_text, "label": label or badge_type_text})

        unique: Dict[str, Dict[str, str]] = {}
        for ref in refs:
            unique.setdefault(ref["badge_type"], ref)
        return list(unique.values())

    @staticmethod
    def _badge_change_message(item: Dict[str, Any], badge_labels: List[str]) -> str:
        provider = item["provider"]
        state = item["verification_state"]
        labels = ", ".join(badge_labels[:3]) or "Trust badge"
        if len(badge_labels) > 3:
            labels += f" and {len(badge_labels) - 3} more"
        if state == VerificationStatus.EXPIRED.value:
            return f"{labels} changed because {provider} verification expired. Refresh the source before showing it as active."
        if state == VerificationStatus.FAILED.value:
            return f"{labels} changed because {provider} verification failed. Retry verification or reconnect the integration."
        if state == VerificationStatus.DISCONNECTED.value:
            return f"{labels} changed because {provider} is disconnected. Reconnect it to resume badge refresh."
        return f"{labels} changed because {provider} verification is pending a metadata refresh."

    @staticmethod
    def _severity(notification_type: str) -> str:
        if notification_type == "trust_verification_expired":
            return "critical"
        if notification_type in {"trust_verification_failed", "trust_integration_disconnected"}:
            return "warning"
        return "info"

    @staticmethod
    def _title(notification_type: str) -> str:
        titles = {
            "trust_verification_expired": "Verification expired",
            "trust_verification_failed": "Verification failed",
            "trust_integration_disconnected": "Integration disconnected",
            "trust_verification_pending": "Verification pending",
        }
        return titles.get(notification_type, "Trust verification update")

    @staticmethod
    def _message(item: Dict[str, Any]) -> str:
        provider = item["provider"]
        state = item["verification_state"]
        if state == VerificationStatus.EXPIRED.value:
            return f"{provider} verification has expired. Refresh it before showing active badges."
        if state == VerificationStatus.FAILED.value:
            return f"{provider} verification failed. Retry verification or reconnect the integration."
        if state == VerificationStatus.DISCONNECTED.value:
            return f"{provider} is disconnected. Reconnect it to resume continuous verification."
        return f"{provider} verification is pending and needs a metadata refresh."
