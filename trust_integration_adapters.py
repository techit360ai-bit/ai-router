"""
Trust Engine Lite integration adapter contracts.

Wave 38 does not call GitHub, LinkedIn, DNS, deployment providers, Firebase, or
Supabase. These adapters define the metadata-only boundary future provider
clients must satisfy before data reaches the TrustVerificationService.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List, Optional

from trust_engine_lite import TrustEngineComputer, VerificationSource, VerificationStatus


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _iso(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def _parse_dt(value: Any) -> Optional[datetime]:
    if isinstance(value, datetime):
        return value
    if isinstance(value, str) and value:
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).replace(tzinfo=None)
        except ValueError:
            return None
    return None


def _interval_seconds(source: str) -> int:
    interval = TrustEngineComputer.SYNC_INTERVALS.get(source, timedelta(days=7))
    return int(interval.total_seconds())


class UnsupportedTrustProvider(ValueError):
    """Raised when a provider is not registered for Trust Engine Lite."""


@dataclass(frozen=True)
class TrustIntegrationManifest:
    provider: str
    source: str
    display_name: str
    auth_method: str
    scopes: List[str]
    sync_frequency_seconds: int
    stored_fields: List[str]
    forbidden_fields: List[str]
    access_description: str
    storage_description: str
    token_policy: str = "Store only an encrypted secret-manager reference; never expose tokens to clients."
    revocation_supported: bool = True
    manual_reverification_supported: bool = True
    raw_payload_stored: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "provider": self.provider,
            "source": self.source,
            "display_name": self.display_name,
            "auth_method": self.auth_method,
            "scopes": list(self.scopes),
            "sync_frequency_seconds": self.sync_frequency_seconds,
            "stored_fields": list(self.stored_fields),
            "forbidden_fields": list(self.forbidden_fields),
            "access_description": self.access_description,
            "storage_description": self.storage_description,
            "token_policy": self.token_policy,
            "revocation_supported": self.revocation_supported,
            "manual_reverification_supported": self.manual_reverification_supported,
            "raw_payload_stored": self.raw_payload_stored,
        }


@dataclass(frozen=True)
class TrustAdapterResult:
    provider: str
    source: str
    status: str
    confidence: float
    metadata: Dict[str, Any]
    dropped_fields: List[str]
    metadata_hash: str
    expires_at: datetime
    next_sync_at: datetime
    raw_payload_stored: bool = False
    tokens_stored: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "provider": self.provider,
            "source": self.source,
            "status": self.status,
            "confidence": self.confidence,
            "metadata": dict(self.metadata),
            "dropped_fields": list(self.dropped_fields),
            "metadata_hash": self.metadata_hash,
            "expires_at": self.expires_at.isoformat(),
            "next_sync_at": self.next_sync_at.isoformat(),
            "raw_payload_stored": self.raw_payload_stored,
            "tokens_stored": self.tokens_stored,
        }


class BaseTrustIntegrationAdapter:
    provider = ""
    source = ""
    display_name = ""
    auth_method = "oauth2"
    scopes: List[str] = []
    stored_fields: set[str] = set()
    aliases: Dict[str, str] = {}
    access_description = "Read-only verification metadata."
    storage_description = "Only normalized verification metadata is stored."
    supported_values: Dict[str, set[str]] = {}
    default_values: Dict[str, Any] = {}

    FORBIDDEN_TERMS = (
        "token",
        "secret",
        "password",
        "raw",
        "payload",
        "source_code",
        "repository_content",
        "repo_content",
        "contact",
        "message",
        "document_blob",
        "analytics_event",
        "session",
        "user_email",
        "user_id",
        "environment",
        "log",
        "build_artifact",
    )

    def manifest(self) -> TrustIntegrationManifest:
        return TrustIntegrationManifest(
            provider=self.provider,
            source=self.source,
            display_name=self.display_name or self.provider,
            auth_method=self.auth_method,
            scopes=list(self.scopes),
            sync_frequency_seconds=_interval_seconds(self.source),
            stored_fields=sorted(self.stored_fields),
            forbidden_fields=list(self.FORBIDDEN_TERMS),
            access_description=self.access_description,
            storage_description=self.storage_description,
        )

    def normalize(self, payload: Optional[Dict[str, Any]], now: Optional[datetime] = None) -> TrustAdapterResult:
        now = now or _utcnow()
        payload = payload or {}
        dropped: List[str] = []
        metadata: Dict[str, Any] = dict(self.default_values)

        for key, value in payload.items():
            key_lower = str(key).strip().lower()
            dest = self.aliases.get(key_lower, key_lower)
            if self._should_drop(key_lower, dest, value):
                dropped.append(str(key))
                continue
            metadata[dest] = self._scalar(value)

        self._postprocess(metadata, dropped)
        status = self._status(metadata)
        confidence = self._confidence(status, metadata)
        metadata["confidence"] = confidence

        metadata_hash = TrustEngineComputer.hash_metadata(metadata)
        expires_at = TrustEngineComputer.expiry_for(self.source, now)

        return TrustAdapterResult(
            provider=self.provider,
            source=self.source,
            status=status.value,
            confidence=confidence,
            metadata=metadata,
            dropped_fields=sorted(set(dropped)),
            metadata_hash=metadata_hash,
            expires_at=expires_at,
            next_sync_at=expires_at,
        )

    def _should_drop(self, key: str, dest: str, value: Any) -> bool:
        if dest not in self.stored_fields:
            return True
        if any(term in key or term in dest for term in self.FORBIDDEN_TERMS):
            return True
        if not self._safe_value(value):
            return True
        if dest in self.supported_values and value is not None:
            return str(value).lower() not in self.supported_values[dest]
        return False

    @staticmethod
    def _safe_value(value: Any) -> bool:
        return isinstance(value, (str, int, float, bool, datetime)) or value is None

    @staticmethod
    def _scalar(value: Any) -> Any:
        return _iso(value)

    def _postprocess(self, metadata: Dict[str, Any], dropped: List[str]) -> None:
        return None

    def _status(self, metadata: Dict[str, Any]) -> VerificationStatus:
        if str(metadata.get("business_verification_status", "")).lower() in {"failed", "rejected"}:
            return VerificationStatus.FAILED
        if metadata.get("verified") is True:
            return VerificationStatus.VERIFIED
        if metadata.get("deployment_live") is True:
            return VerificationStatus.VERIFIED
        if str(metadata.get("approval_status", "")).lower() == "approved":
            return VerificationStatus.VERIFIED
        return VerificationStatus.PENDING

    @staticmethod
    def _confidence(status: VerificationStatus, metadata: Dict[str, Any]) -> float:
        try:
            supplied = float(metadata.get("confidence"))
        except (TypeError, ValueError):
            supplied = 0.0
        if supplied:
            return round(max(0.0, min(1.0, supplied)), 4)
        if status == VerificationStatus.VERIFIED:
            return 0.95
        if status == VerificationStatus.FAILED:
            return 0.1
        return 0.5


class GitHubTrustAdapter(BaseTrustIntegrationAdapter):
    provider = "github"
    source = VerificationSource.GITHUB.value
    display_name = "GitHub"
    scopes = ["read-only metadata"]
    stored_fields = {
        "github_repo_count",
        "github_commit_count",
        "github_contributor_count",
        "github_last_activity_at",
        "verified",
        "confidence",
    }
    aliases = {
        "repo_count": "github_repo_count",
        "commit_count": "github_commit_count",
        "contributor_count": "github_contributor_count",
        "last_activity": "github_last_activity_at",
        "connected": "verified",
    }
    access_description = "Read repository metadata counts and last public activity only."
    storage_description = "Stores repo count, commit count, contributor count, last activity, and confidence only."

    def _postprocess(self, metadata: Dict[str, Any], dropped: List[str]) -> None:
        if "verified" not in metadata and any(k.startswith("github_") for k in metadata):
            metadata["verified"] = True
        for key in ("github_repo_count", "github_commit_count", "github_contributor_count"):
            if key in metadata:
                metadata[key] = max(0, int(metadata[key] or 0))


class OAuthConnectionTrustAdapter(BaseTrustIntegrationAdapter):
    auth_method = "oauth2"
    scopes = ["read-only connection status"]
    stored_fields = {"connected", "verified", "confidence"}
    aliases = {"connected": "verified"}
    access_description = "Confirm that the external account is connected; no private profile fields are stored."
    storage_description = "Stores connected/verified status and confidence only."

    def _postprocess(self, metadata: Dict[str, Any], dropped: List[str]) -> None:
        if metadata.get("connected") is True:
            metadata["verified"] = True


class LinkedInTrustAdapter(OAuthConnectionTrustAdapter):
    provider = "linkedin"
    source = VerificationSource.LINKEDIN.value
    display_name = "LinkedIn"


class EmailTrustAdapter(BaseTrustIntegrationAdapter):
    provider = "email"
    source = VerificationSource.EMAIL.value
    display_name = "Email"
    auth_method = "otp"
    scopes = ["email verification challenge"]
    stored_fields = {"verified", "verified_at", "confidence"}
    access_description = "Verify challenge completion only."
    storage_description = "Stores verified status, verification timestamp, and confidence only."


class PhoneTrustAdapter(BaseTrustIntegrationAdapter):
    provider = "phone"
    source = VerificationSource.PHONE.value
    display_name = "Phone"
    auth_method = "otp"
    scopes = ["phone verification challenge"]
    stored_fields = {"verified", "verified_at", "confidence"}
    access_description = "Verify OTP completion only."
    storage_description = "Stores verified status, verification timestamp, and confidence only."


class DomainTrustAdapter(BaseTrustIntegrationAdapter):
    provider = "domain"
    source = VerificationSource.DOMAIN.value
    display_name = "Domain"
    auth_method = "dns_or_site_challenge"
    scopes = ["dns txt", "meta tag", "verification file"]
    stored_fields = {"domain", "method", "verified", "verified_at", "expires_at", "confidence"}
    aliases = {"verification_method": "method"}
    supported_values = {"method": {"dns_txt", "meta_tag", "verification_file"}}
    default_values = {"method": "dns_txt"}
    access_description = "Check DNS TXT, meta tag, or verification file challenge result."
    storage_description = "Stores domain, verification method, status, verification time, expiry, and confidence only."


class WebsiteTrustAdapter(DomainTrustAdapter):
    provider = "website"
    source = VerificationSource.WEBSITE.value
    display_name = "Website"
    stored_fields = {"website", "method", "verified", "verified_at", "expires_at", "confidence"}
    aliases = {"url": "website", "verification_method": "method"}
    default_values = {"method": "meta_tag"}


class OrganizationTrustAdapter(BaseTrustIntegrationAdapter):
    provider = "organization"
    source = VerificationSource.ORGANIZATION.value
    display_name = "Organization"
    auth_method = "business_registry_metadata"
    scopes = ["business verification metadata"]
    stored_fields = {
        "organization_id",
        "company_name",
        "country",
        "verified",
        "business_verification_status",
        "confidence",
    }
    aliases = {"registration_status": "business_verification_status", "status": "business_verification_status"}
    access_description = "Read business verification status where available; documents are not retained."
    storage_description = "Stores organization identifiers, country, verification status, and confidence only."

    def _postprocess(self, metadata: Dict[str, Any], dropped: List[str]) -> None:
        status = str(metadata.get("business_verification_status", "")).lower()
        if status in {"verified", "active", "registered"}:
            metadata["verified"] = True


class DeploymentTrustAdapter(BaseTrustIntegrationAdapter):
    source = VerificationSource.DEPLOYMENT.value
    auth_method = "provider_read_only"
    scopes = ["deployment metadata"]
    stored_fields = {
        "platform",
        "deployment_status",
        "deployment_live",
        "deployments_30d",
        "last_deployment_at",
        "success_rate",
        "verified",
        "confidence",
    }
    aliases = {"last_deployment": "last_deployment_at", "deployments_this_month": "deployments_30d"}
    supported_values = {
        "platform": {"vercel", "render", "railway", "cloudflare"},
        "deployment_status": {"ready", "live", "success", "failed", "pending", "building"},
    }
    access_description = "Read deployment status, frequency, last deployment, and success-rate metadata only."
    storage_description = "Stores deployment status aggregates only; logs, secrets, env vars, and artifacts are dropped."

    def _postprocess(self, metadata: Dict[str, Any], dropped: List[str]) -> None:
        metadata.setdefault("platform", self.provider)
        status = str(metadata.get("deployment_status", "")).lower()
        if status in {"ready", "live", "success"}:
            metadata["deployment_live"] = True
            metadata["verified"] = True
        if "deployments_30d" in metadata:
            metadata["deployments_30d"] = max(0, int(metadata["deployments_30d"] or 0))


class VercelTrustAdapter(DeploymentTrustAdapter):
    provider = "vercel"
    display_name = "Vercel"


class RenderTrustAdapter(DeploymentTrustAdapter):
    provider = "render"
    display_name = "Render"


class RailwayTrustAdapter(DeploymentTrustAdapter):
    provider = "railway"
    display_name = "Railway"


class CloudflareTrustAdapter(DeploymentTrustAdapter):
    provider = "cloudflare"
    display_name = "Cloudflare"


class ProductAnalyticsTrustAdapter(BaseTrustIntegrationAdapter):
    source = VerificationSource.PRODUCT_ANALYTICS.value
    auth_method = "provider_read_only"
    scopes = ["aggregate product analytics"]
    stored_fields = {
        "provider",
        "mau",
        "dau",
        "growth_rate_pct",
        "retention_rate_pct",
        "verified",
        "confidence",
    }
    aliases = {"growth_pct": "growth_rate_pct", "retention_pct": "retention_rate_pct"}
    supported_values = {"provider": {"firebase", "supabase"}}
    access_description = "Read aggregate product activity only."
    storage_description = "Stores MAU, DAU, growth rate, retention rate, provider, and confidence only."

    def _postprocess(self, metadata: Dict[str, Any], dropped: List[str]) -> None:
        metadata.setdefault("provider", self.provider)
        for key in ("mau", "dau"):
            if key in metadata:
                metadata[key] = max(0, int(metadata[key] or 0))
        if "verified" not in metadata and (metadata.get("mau") or metadata.get("dau")):
            metadata["verified"] = True


class FirebaseTrustAdapter(ProductAnalyticsTrustAdapter):
    provider = "firebase"
    display_name = "Firebase"


class SupabaseTrustAdapter(ProductAnalyticsTrustAdapter):
    provider = "supabase"
    display_name = "Supabase"


class TeamTrustAdapter(BaseTrustIntegrationAdapter):
    provider = "team"
    source = VerificationSource.TEAM.value
    display_name = "Team"
    auth_method = "member_invitation"
    scopes = ["team verification status"]
    stored_fields = {"verified_team_count", "pending_invitations", "verified", "confidence"}
    access_description = "Read teammate verification status only."
    storage_description = "Stores verified teammate count, pending invitation count, and confidence only."

    def _postprocess(self, metadata: Dict[str, Any], dropped: List[str]) -> None:
        for key in ("verified_team_count", "pending_invitations"):
            if key in metadata:
                metadata[key] = max(0, int(metadata[key] or 0))
        if metadata.get("verified_team_count", 0) > 0 and "verified" not in metadata:
            metadata["verified"] = True


class TrustIntegrationAdapterRegistry:
    def __init__(self, adapters: Optional[Iterable[BaseTrustIntegrationAdapter]] = None) -> None:
        adapters = adapters or self._default_adapters()
        self._adapters = {adapter.provider: adapter for adapter in adapters}
        self._aliases = {
            "github_oauth": "github",
            "linkedin_oauth": "linkedin",
            "dns_txt": "domain",
            "meta_tag": "domain",
            "verification_file": "domain",
            "domain_dns": "domain",
            "domain_meta": "domain",
            "cloudflare_pages": "cloudflare",
            "product": "firebase",
            "analytics": "firebase",
        }

    @classmethod
    def default(cls) -> "TrustIntegrationAdapterRegistry":
        return cls()

    @staticmethod
    def _default_adapters() -> List[BaseTrustIntegrationAdapter]:
        return [
            EmailTrustAdapter(),
            PhoneTrustAdapter(),
            GitHubTrustAdapter(),
            LinkedInTrustAdapter(),
            DomainTrustAdapter(),
            WebsiteTrustAdapter(),
            OrganizationTrustAdapter(),
            VercelTrustAdapter(),
            RenderTrustAdapter(),
            RailwayTrustAdapter(),
            CloudflareTrustAdapter(),
            FirebaseTrustAdapter(),
            SupabaseTrustAdapter(),
            TeamTrustAdapter(),
        ]

    def get(self, provider: str) -> BaseTrustIntegrationAdapter:
        key = (provider or "").strip().lower()
        key = self._aliases.get(key, key)
        try:
            return self._adapters[key]
        except KeyError as exc:
            raise UnsupportedTrustProvider(f"Unsupported trust integration provider: {provider}") from exc

    def normalize(
        self,
        provider: str,
        payload: Optional[Dict[str, Any]] = None,
        now: Optional[datetime] = None,
    ) -> TrustAdapterResult:
        return self.get(provider).normalize(payload, now=now)

    def manifest(self, provider: str) -> Dict[str, Any]:
        return self.get(provider).manifest().to_dict()

    def manifests(self) -> List[Dict[str, Any]]:
        return [adapter.manifest().to_dict() for adapter in sorted(self._adapters.values(), key=lambda a: a.provider)]


@dataclass(frozen=True)
class TrustRefreshPlanEntry:
    source: str
    provider: str
    verification_state: str
    connected: bool
    last_sync_at: Optional[datetime]
    next_sync_at: datetime
    expires_at: datetime
    should_refresh: bool
    notification_type: Optional[str]
    confidence_multiplier: float
    reason: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source": self.source,
            "provider": self.provider,
            "verification_state": self.verification_state,
            "connected": self.connected,
            "last_sync_at": self.last_sync_at.isoformat() if self.last_sync_at else None,
            "next_sync_at": self.next_sync_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "should_refresh": self.should_refresh,
            "notification_type": self.notification_type,
            "confidence_multiplier": self.confidence_multiplier,
            "reason": self.reason,
        }


class TrustRefreshPlanner:
    """
    Computes continuous-verification work without mutating existing data.

    Failure, expiry, and disconnect states are represented as new plan states.
    The planner never deletes or rewrites existing verification metadata.
    """

    def plan(self, connections: Iterable[Dict[str, Any]], now: Optional[datetime] = None) -> Dict[str, Any]:
        now = now or _utcnow()
        items = [self._entry(conn, now).to_dict() for conn in connections]
        return {
            "generated_at": now.isoformat(),
            "items": items,
            "due_count": sum(1 for item in items if item["should_refresh"]),
            "expired_count": sum(1 for item in items if item["verification_state"] == VerificationStatus.EXPIRED.value),
            "privacy": {
                "metadata_only": True,
                "raw_payload_stored": False,
                "failure_deletes_existing_data": False,
            },
        }

    def _entry(self, connection: Dict[str, Any], now: datetime) -> TrustRefreshPlanEntry:
        source = str(connection.get("source") or "").strip().lower()
        provider = str(connection.get("provider") or source).strip().lower()
        status = str(connection.get("status") or VerificationStatus.PENDING.value).strip().lower()
        connected = bool(connection.get("connected", status != VerificationStatus.DISCONNECTED.value))
        last_sync_at = _parse_dt(connection.get("last_sync_at"))
        interval = TrustEngineComputer.SYNC_INTERVALS.get(source, timedelta(days=7))

        if not connected or status == VerificationStatus.DISCONNECTED.value:
            timestamp = last_sync_at or now
            return TrustRefreshPlanEntry(
                source=source,
                provider=provider,
                verification_state=VerificationStatus.DISCONNECTED.value,
                connected=False,
                last_sync_at=last_sync_at,
                next_sync_at=timestamp,
                expires_at=timestamp,
                should_refresh=False,
                notification_type="trust_integration_disconnected",
                confidence_multiplier=0.0,
                reason="Integration is disconnected. Existing verification history remains append-only.",
            )

        if not last_sync_at:
            return TrustRefreshPlanEntry(
                source=source,
                provider=provider,
                verification_state=VerificationStatus.PENDING.value,
                connected=True,
                last_sync_at=None,
                next_sync_at=now,
                expires_at=now,
                should_refresh=True,
                notification_type="trust_verification_pending",
                confidence_multiplier=0.5,
                reason="No successful sync has been recorded yet.",
            )

        next_sync_at = last_sync_at + interval
        expires_at = _parse_dt(connection.get("expires_at")) or next_sync_at

        if status == VerificationStatus.FAILED.value:
            return TrustRefreshPlanEntry(
                source=source,
                provider=provider,
                verification_state=VerificationStatus.FAILED.value,
                connected=True,
                last_sync_at=last_sync_at,
                next_sync_at=now,
                expires_at=expires_at,
                should_refresh=True,
                notification_type="trust_verification_failed",
                confidence_multiplier=0.25,
                reason="Last verification failed; schedule a retry without deleting previous metadata.",
            )

        if now > expires_at:
            return TrustRefreshPlanEntry(
                source=source,
                provider=provider,
                verification_state=VerificationStatus.EXPIRED.value,
                connected=True,
                last_sync_at=last_sync_at,
                next_sync_at=now,
                expires_at=expires_at,
                should_refresh=True,
                notification_type="trust_verification_expired",
                confidence_multiplier=0.5,
                reason="Verification is past its refresh interval and must not remain silently badged.",
            )

        return TrustRefreshPlanEntry(
            source=source,
            provider=provider,
            verification_state=VerificationStatus.VERIFIED.value,
            connected=True,
            last_sync_at=last_sync_at,
            next_sync_at=next_sync_at,
            expires_at=expires_at,
            should_refresh=False,
            notification_type=None,
            confidence_multiplier=1.0,
            reason="Verification is within its current refresh interval.",
        )
