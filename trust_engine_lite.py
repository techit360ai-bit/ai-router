"""
TECHIT TRUST ENGINE LITE
========================

Privacy-first verification foundation for TechIT.

This module deliberately verifies metadata instead of owning raw source data.
It is safe to import without live OAuth providers, secret managers, or a
database connection. Later waves will add API adapters and provider-specific
refresh flows on top of these contracts.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


def _utcnow() -> datetime:
    """Return a naive UTC timestamp to match the existing schema style."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


class VerificationStatus(str, Enum):
    """Lifecycle states for metadata-only verification."""

    UNVERIFIED = "unverified"
    PENDING = "pending"
    VERIFIED = "verified"
    EXPIRED = "expired"
    FAILED = "failed"
    DISCONNECTED = "disconnected"


class VerificationSource(str, Enum):
    """Supported v1 verification sources."""

    EMAIL = "email"
    PHONE = "phone"
    GITHUB = "github"
    LINKEDIN = "linkedin"
    DOMAIN = "domain"
    WEBSITE = "website"
    ORGANIZATION = "organization"
    DEPLOYMENT = "deployment"
    PRODUCT_ANALYTICS = "product_analytics"
    TEAM = "team"
    MILESTONE = "milestone"


@dataclass(frozen=True)
class VerificationRecord:
    """
    Immutable verification history item.

    Raw provider payloads are never stored here. `metadata_hash` lets the
    platform detect tampering or material source changes without retaining the
    underlying data.
    """

    verification_id: str
    subject_id: str
    subject_type: str
    source: str
    status: str
    confidence: float
    metadata_hash: str
    expires_at: datetime
    created_at: datetime
    event_type: str
    reference_id: Optional[str] = None

    def __post_init__(self) -> None:
        if not 0 <= self.confidence <= 1:
            raise ValueError("confidence must be between 0 and 1")
        if not self.metadata_hash:
            raise ValueError("metadata_hash is required")


@dataclass(frozen=True)
class TrustBadge:
    """A non-permanent badge derived from current verification metadata."""

    badge_type: str
    label: str
    source: str
    issued_at: datetime
    expires_at: datetime
    status: str = VerificationStatus.VERIFIED.value

    @property
    def is_active(self) -> bool:
        return self.status == VerificationStatus.VERIFIED.value and self.expires_at > _utcnow()


@dataclass
class FounderTrustProfile:
    """
    Metadata-only founder trust profile.

    No email addresses, phone numbers, GitHub repositories, LinkedIn private
    details, tokens, source code, analytics events, or user lists belong here.
    """

    founder_id: str
    email_verified: bool = False
    phone_verified: bool = False
    github_connected: bool = False
    linkedin_connected: bool = False
    domain_verified: bool = False
    organization_verified: bool = False
    deployment_live: bool = False
    product_activity_verified: bool = False
    team_verified_count: int = 0
    milestone_count: int = 0
    github_repo_count: int = 0
    github_commit_count: int = 0
    github_contributor_count: int = 0
    github_last_activity_at: Optional[datetime] = None
    deployments_30d: int = 0
    last_deployment_at: Optional[datetime] = None
    mau: int = 0
    dau: int = 0
    growth_rate_pct: float = 0.0
    retention_rate_pct: float = 0.0
    last_sync_at: Optional[datetime] = None
    verification_status: str = VerificationStatus.UNVERIFIED.value
    trust_score: float = 0.0
    verification_history: List[VerificationRecord] = field(default_factory=list)


class TrustEngineComputer:
    """
    Computes Trust Engine Lite scores and expiring badges.

    Inputs are booleans, counts, timestamps, and aggregate metrics. The computer
    must never receive secrets or raw provider responses.
    """

    WEIGHTS = {
        "email_verified": 10.0,
        "phone_verified": 10.0,
        "github_connected": 15.0,
        "linkedin_connected": 10.0,
        "domain_verified": 15.0,
        "organization_verified": 10.0,
        "deployment_live": 15.0,
        "product_activity": 10.0,
        "team_verified": 10.0,
        "milestones": 5.0,
    }

    SYNC_INTERVALS = {
        VerificationSource.EMAIL.value: timedelta(days=365),
        VerificationSource.PHONE.value: timedelta(days=365),
        VerificationSource.GITHUB.value: timedelta(days=1),
        VerificationSource.LINKEDIN.value: timedelta(days=30),
        VerificationSource.DOMAIN.value: timedelta(days=7),
        VerificationSource.WEBSITE.value: timedelta(days=7),
        VerificationSource.ORGANIZATION.value: timedelta(days=90),
        VerificationSource.DEPLOYMENT.value: timedelta(hours=12),
        VerificationSource.PRODUCT_ANALYTICS.value: timedelta(days=1),
        VerificationSource.TEAM.value: timedelta(days=30),
        VerificationSource.MILESTONE.value: timedelta(days=180),
    }

    BADGE_EXPIRY = {
        "verified_founder": timedelta(days=365),
        "verified_organization": timedelta(days=90),
        "verified_domain": timedelta(days=90),
        "active_development": timedelta(days=30),
        "team_verified": timedelta(days=30),
        "product_live": timedelta(days=30),
        "milestone_builder": timedelta(days=180),
    }

    @classmethod
    def compute(cls, profile: FounderTrustProfile, now: Optional[datetime] = None) -> Dict[str, Any]:
        now = now or _utcnow()
        score = 0.0
        signals: List[str] = []
        breakdown: Dict[str, float] = {}

        def add_signal(name: str, points: float) -> None:
            nonlocal score
            score += points
            signals.append(name)
            breakdown[name] = round(points, 2)

        if profile.email_verified:
            add_signal("email_verified", cls.WEIGHTS["email_verified"])
        if profile.phone_verified:
            add_signal("phone_verified", cls.WEIGHTS["phone_verified"])
        if profile.github_connected:
            activity_bonus = min(
                5.0,
                profile.github_repo_count * 0.5
                + profile.github_commit_count * 0.01
                + profile.github_contributor_count * 0.25,
            )
            add_signal("github_connected", cls.WEIGHTS["github_connected"] + activity_bonus)
        if profile.linkedin_connected:
            add_signal("linkedin_connected", cls.WEIGHTS["linkedin_connected"])
        if profile.domain_verified:
            add_signal("domain_verified", cls.WEIGHTS["domain_verified"])
        if profile.organization_verified:
            add_signal("organization_verified", cls.WEIGHTS["organization_verified"])
        if profile.deployment_live:
            deploy_bonus = min(5.0, profile.deployments_30d * 0.5)
            add_signal("deployment_live", cls.WEIGHTS["deployment_live"] + deploy_bonus)
        if profile.product_activity_verified or profile.mau or profile.dau:
            product_points = min(cls.WEIGHTS["product_activity"], (max(profile.mau, profile.dau) / 500) * 10)
            add_signal("product_activity", product_points)
        if profile.team_verified_count:
            add_signal("team_verified", min(cls.WEIGHTS["team_verified"], profile.team_verified_count * 2.5))
        if profile.milestone_count:
            add_signal("milestones", min(cls.WEIGHTS["milestones"], profile.milestone_count * 1.25))

        trust_score = round(min(100.0, score), 2)
        badges = cls.compute_badges(profile, now=now)
        status = VerificationStatus.VERIFIED.value if trust_score > 0 else VerificationStatus.UNVERIFIED.value

        return {
            "trust_score": trust_score,
            "tier": cls.classify_trust(trust_score),
            "verification_status": status,
            "badges": [badge.label for badge in badges if badge.is_active],
            "badge_records": badges,
            "signals": signals,
            "breakdown": breakdown,
            "computed_at": now.isoformat(),
        }

    @classmethod
    def compute_badges(cls, profile: FounderTrustProfile, now: Optional[datetime] = None) -> List[TrustBadge]:
        now = now or _utcnow()
        badges: List[TrustBadge] = []

        def badge(badge_type: str, label: str, source: str) -> None:
            badges.append(
                TrustBadge(
                    badge_type=badge_type,
                    label=label,
                    source=source,
                    issued_at=now,
                    expires_at=now + cls.BADGE_EXPIRY[badge_type],
                )
            )

        if profile.email_verified:
            badge("verified_founder", "Verified Founder", VerificationSource.EMAIL.value)
        elif profile.phone_verified:
            badge("verified_founder", "Verified Founder", VerificationSource.PHONE.value)
        elif profile.linkedin_connected:
            badge("verified_founder", "Verified Founder", VerificationSource.LINKEDIN.value)
        if profile.organization_verified:
            badge("verified_organization", "Verified Organization", VerificationSource.ORGANIZATION.value)
        if profile.domain_verified:
            badge("verified_domain", "Verified Domain", VerificationSource.DOMAIN.value)
        if profile.github_connected and profile.github_commit_count >= 10:
            badge("active_development", "Active Development", VerificationSource.GITHUB.value)
        if profile.team_verified_count >= 2:
            badge("team_verified", "Team Verified", VerificationSource.TEAM.value)
        if profile.deployment_live:
            badge("product_live", "Product Live", VerificationSource.DEPLOYMENT.value)
        if profile.milestone_count >= 3:
            badge("milestone_builder", "Milestone Builder", VerificationSource.MILESTONE.value)

        return badges

    @classmethod
    def classify_trust(cls, score: float) -> str:
        if score >= 80:
            return "Highly Trusted"
        if score >= 60:
            return "Verified"
        if score >= 40:
            return "Partially Verified"
        if score >= 20:
            return "Early Stage"
        return "Unverified"

    @classmethod
    def is_verification_stale(
        cls,
        source: str,
        last_sync_at: Optional[datetime],
        now: Optional[datetime] = None,
    ) -> bool:
        if not last_sync_at:
            return True
        now = now or _utcnow()
        interval = cls.SYNC_INTERVALS.get(source, timedelta(days=7))
        return now - last_sync_at > interval

    @classmethod
    def expiry_for(cls, source: str, verified_at: Optional[datetime] = None) -> datetime:
        verified_at = verified_at or _utcnow()
        return verified_at + cls.SYNC_INTERVALS.get(source, timedelta(days=7))

    @classmethod
    def hash_metadata(cls, metadata: Dict[str, Any]) -> str:
        """
        Hash raw metadata and discard it. The hash is stable for equivalent
        JSON dictionaries and does not expose the underlying provider payload.
        """
        canonical = json.dumps(metadata, sort_keys=True, separators=(",", ":"), default=str)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    @classmethod
    def build_verification_record(
        cls,
        *,
        verification_id: str,
        subject_id: str,
        subject_type: str,
        source: str,
        status: VerificationStatus,
        confidence: float,
        metadata: Dict[str, Any],
        created_at: Optional[datetime] = None,
        reference_id: Optional[str] = None,
    ) -> VerificationRecord:
        created_at = created_at or _utcnow()
        return VerificationRecord(
            verification_id=verification_id,
            subject_id=subject_id,
            subject_type=subject_type,
            source=source,
            status=status.value,
            confidence=confidence,
            metadata_hash=cls.hash_metadata(metadata),
            expires_at=cls.expiry_for(source, created_at),
            created_at=created_at,
            event_type=f"{source}_{status.value}",
            reference_id=reference_id,
        )
