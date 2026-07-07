"""
Investor-safe Trust Dashboard read contracts.

Wave 45 exposes read-only Trust Engine metadata for investor dashboards. The
service deliberately builds a new outward-facing shape instead of returning raw
Trust rows: no owner ids, metadata hashes, provider payloads, repository names,
customer records, analytics events, tokens, secrets, or private founder notes.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, Iterable, List, Optional

from ai_router_core import UserContext, UserRole
from trust_engine_lite import FounderTrustProfile, TrustEngineComputer, VerificationSource, VerificationStatus


class InvestorTrustReadService:
    """Builds investor-facing Trust read models from existing metadata rows."""

    PRIVACY: Dict[str, bool] = {
        "metadataOnly": True,
        "approvedEvidenceOnly": True,
        "rawPayloadsExposed": False,
        "customerDataExposed": False,
        "sourceCodeExposed": False,
        "investorNotesPrivate": True,
        "founderVisible": False,
    }

    SOURCE_LABELS: Dict[str, Dict[str, str]] = {
        VerificationSource.EMAIL.value: {
            "label": "Founder Identity",
            "provider": "Identity Verification",
            "origin": "Identity Verification",
        },
        VerificationSource.PHONE.value: {
            "label": "Founder Identity",
            "provider": "Identity Verification",
            "origin": "Identity Verification",
        },
        VerificationSource.LINKEDIN.value: {
            "label": "Founder Identity",
            "provider": "Professional Profile",
            "origin": "LinkedIn Metadata",
        },
        VerificationSource.ORGANIZATION.value: {
            "label": "Organization",
            "provider": "Business Registry",
            "origin": "Business Registry",
        },
        VerificationSource.DOMAIN.value: {
            "label": "Domain",
            "provider": "DNS Challenge",
            "origin": "DNS Challenge",
        },
        VerificationSource.WEBSITE.value: {
            "label": "Website",
            "provider": "Website Check",
            "origin": "Website Metadata",
        },
        VerificationSource.GITHUB.value: {
            "label": "GitHub",
            "provider": "GitHub Metadata",
            "origin": "GitHub Metadata",
        },
        VerificationSource.TEAM.value: {
            "label": "Team",
            "provider": "Member Verification",
            "origin": "Member Verification",
        },
        VerificationSource.DEPLOYMENT.value: {
            "label": "Deployment",
            "provider": "Deployment Platform",
            "origin": "Deployment Metadata",
        },
        VerificationSource.PRODUCT_ANALYTICS.value: {
            "label": "Product Activity",
            "provider": "Analytics Aggregate",
            "origin": "Aggregate Analytics",
        },
        VerificationSource.MILESTONE.value: {
            "label": "Milestone",
            "provider": "Admin Review",
            "origin": "Admin Review",
        },
    }

    ORDERED_VERIFICATION_SOURCES = [
        VerificationSource.EMAIL.value,
        VerificationSource.ORGANIZATION.value,
        VerificationSource.DOMAIN.value,
        VerificationSource.GITHUB.value,
        VerificationSource.TEAM.value,
        VerificationSource.DEPLOYMENT.value,
        VerificationSource.PRODUCT_ANALYTICS.value,
    ]

    def get_startups(self, investor_context: UserContext, db: Any = None, limit: int = 50) -> Dict[str, Any]:
        """GET /api/v1/investor/trust/startups -- read-only investor contract."""
        self._require_investor(investor_context)
        projects = self._load_projects(db, limit)
        profiles = self._load_profiles(db)
        watchlist_ids = self._watchlist_project_ids(investor_context, db)

        project_ids = self._ordered_project_ids(projects, profiles, watchlist_ids)
        startups = [
            self._startup_summary(
                project=self._project_for(projects, project_id),
                profile=self._profile_for(profiles, project_id),
                project_id=project_id,
                watchlist_ids=watchlist_ids,
            )
            for project_id in project_ids[: max(1, min(int(limit or 50), 100))]
        ]

        return {
            "startups": startups,
            "watchlistStartupIds": [project_id for project_id in watchlist_ids if project_id in project_ids],
            "privacy": dict(self.PRIVACY),
        }

    def get_dashboard(self, investor_context: UserContext, startup_id: str, db: Any = None) -> Dict[str, Any]:
        """GET /api/v1/investor/trust/{startupId} -- selected startup read model."""
        self._require_investor(investor_context)
        startup_id = str(startup_id)
        projects = self._load_projects(db, 100)
        profiles = self._load_profiles(db)
        histories = self._load_history(db, startup_id, 100)
        badges = self._load_badges(db, startup_id)
        milestones = self._load_project_milestones(db, startup_id)
        timelines = self._load_timeline(db, startup_id, 25)
        watchlist_ids = self._watchlist_project_ids(investor_context, db)

        project = self._project_for(projects, startup_id)
        profile_row = self._profile_for(profiles, startup_id)
        profile = self._profile_from_row(profile_row)
        computed = TrustEngineComputer.compute(profile)
        active_badges = self._badge_records(profile, badges)
        summary = self._startup_summary(project, profile_row, startup_id, watchlist_ids, computed)
        verification_items = self._verification_items(profile, histories)
        risk = self._risk_status(verification_items)
        latest_history = histories[0] if histories else None

        return {
            "startup": {
                **summary,
                "founded": self._year(getattr(project, "created_at", None)),
                "website": self._website(project),
                "verifiedStatus": summary["overallStatus"],
            },
            "trustSummary": {
                "overallStatus": summary["overallStatus"],
                "verificationConfidence": summary["confidence"],
                "verificationFreshness": summary["lastVerified"],
                "evidenceSources": summary["evidenceSourcesConnected"],
                "verificationHealth": self._health_label(summary["verificationHealth"]),
            },
            "badges": [self._badge_detail(badge) for badge in active_badges],
            "verificationItems": verification_items,
            "founderOverview": self._founder_overview(profile, project),
            "productDevelopment": self._product_development(profile),
            "productVerification": self._product_verification(profile),
            "productActivity": self._product_activity(profile),
            "teamOverview": self._team_overview(profile),
            "timeline": self._timeline_events(histories, timelines),
            "milestones": self._milestones(milestones, histories),
            "verificationSources": self._verification_sources(verification_items),
            "riskStatus": risk,
            "continuousVerification": self._continuous_verification(profile, histories, summary),
            "investmentReadiness": self._investment_readiness(profile, summary),
            "evidenceExplorer": self._evidence_explorer(verification_items),
            "investorNotes": self._empty_private_notes(summary["watchlistIncluded"]),
            "privacy": dict(self.PRIVACY),
            "sourceContract": {
                "metadataOnly": True,
                "rawProviderPayloadsDiscarded": True,
                "latestVerificationIdExposed": False,
                "ownerIdsExposed": False,
                "metadataHashesExposed": False,
                "latestEventAt": self._iso(getattr(latest_history, "created_at", None)),
            },
        }

    @staticmethod
    def _require_investor(user_context: UserContext) -> None:
        if user_context.role != UserRole.INVESTOR:
            raise PermissionError("Investor Trust Dashboard requires investor role.")

    def _load_projects(self, db: Any, limit: int = 50) -> List[Any]:
        if db is None:
            return []
        try:
            from database_schema import Project

            query = db.query(Project).order_by(Project.updated_at.desc()).limit(max(1, min(int(limit), 100)))
            return list(query.all())
        except Exception:
            return []

    def _load_profiles(self, db: Any) -> List[Any]:
        return self._load_all(db, "TrustProfile")

    def _load_history(self, db: Any, project_id: str, limit: int) -> List[Any]:
        rows = [
            row for row in self._load_all(db, "TrustVerificationHistory")
            if self._id(getattr(row, "project_id", None)) == str(project_id)
        ]
        rows.sort(key=lambda row: getattr(row, "created_at", datetime.min) or datetime.min, reverse=True)
        return rows[: max(1, min(int(limit or 100), 100))]

    def _load_badges(self, db: Any, project_id: str) -> List[Any]:
        return [
            row for row in self._load_all(db, "TrustBadgeSnapshot")
            if self._id(getattr(row, "project_id", None)) == str(project_id)
        ]

    def _load_project_milestones(self, db: Any, project_id: str) -> List[Any]:
        return [
            row for row in self._load_all(db, "ProjectMilestone")
            if self._id(getattr(row, "project_id", None)) == str(project_id)
        ]

    def _load_timeline(self, db: Any, project_id: str, limit: int) -> List[Any]:
        rows = [
            row for row in self._load_all(db, "TrustTimelineEvent")
            if self._id(getattr(row, "project_id", None)) == str(project_id)
        ]
        rows.sort(key=lambda row: getattr(row, "created_at", datetime.min) or datetime.min, reverse=True)
        return rows[: max(1, min(int(limit or 25), 100))]

    def _watchlist_project_ids(self, investor_context: UserContext, db: Any) -> List[str]:
        rows = [
            row for row in self._load_all(db, "InvestorWatchlist")
            if self._id(getattr(row, "investor_id", None)) == str(investor_context.user_id)
        ]
        return self._unique([self._id(getattr(row, "project_id", None)) for row in rows if getattr(row, "project_id", None)])

    def _load_all(self, db: Any, model_name: str) -> List[Any]:
        if db is None:
            return []
        try:
            import database_schema

            model = getattr(database_schema, model_name)
            return list(db.query(model).all())
        except Exception:
            return []

    def _ordered_project_ids(self, projects: List[Any], profiles: List[Any], watchlist_ids: List[str]) -> List[str]:
        ids = list(watchlist_ids)
        ids.extend(self._id(getattr(project, "id", None)) for project in projects if getattr(project, "id", None))
        ids.extend(self._id(getattr(profile, "project_id", None)) for profile in profiles if getattr(profile, "project_id", None))
        return self._unique([project_id for project_id in ids if project_id])

    def _project_for(self, projects: List[Any], project_id: str) -> Any:
        for project in projects:
            if self._id(getattr(project, "id", None)) == str(project_id):
                return project
        return None

    def _profile_for(self, profiles: List[Any], project_id: str) -> Any:
        for profile in profiles:
            if self._id(getattr(profile, "project_id", None)) == str(project_id):
                return profile
        return None

    def _startup_summary(
        self,
        project: Any,
        profile: Any,
        project_id: str,
        watchlist_ids: List[str],
        computed: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        profile_model = self._profile_from_row(profile)
        computed = computed or TrustEngineComputer.compute(profile_model)
        score = int(round(float(computed.get("trust_score", 0.0) or 0.0)))
        name = str(getattr(project, "title", None) or f"Startup {str(project_id)[:8]}")
        health = self._health(score, profile_model, computed)
        return {
            "startupId": str(project_id),
            "name": name,
            "logoText": self._logo_text(name),
            "industry": str(getattr(project, "industry", None) or "Not specified"),
            "country": self._project_metadata(project, "country", "Not specified"),
            "stage": self._value(getattr(project, "stage", None)) or "Not specified",
            "fundingStage": self._project_metadata(project, "funding_stage", "Not specified"),
            "overallStatus": self._overall_status(score, profile_model.verification_status),
            "verificationHealth": health,
            "confidence": score,
            "lastVerified": self._freshness_label(profile_model.last_sync_at),
            "evidenceSourcesConnected": self._evidence_source_count(profile_model),
            "activeBadges": [badge.label for badge in TrustEngineComputer.compute_badges(profile_model) if badge.is_active],
            "watchlistIncluded": str(project_id) in set(watchlist_ids),
            "trustTrend": "needs_attention" if health == "needs_attention" else ("improving" if score >= 80 else "stable"),
        }

    def _profile_from_row(self, row: Any) -> FounderTrustProfile:
        if row is None:
            return FounderTrustProfile(founder_id="investor_view")
        return FounderTrustProfile(
            founder_id="investor_view",
            email_verified=bool(getattr(row, "email_verified", False)),
            phone_verified=bool(getattr(row, "phone_verified", False)),
            github_connected=bool(getattr(row, "github_connected", False)),
            linkedin_connected=bool(getattr(row, "linkedin_connected", False)),
            domain_verified=bool(getattr(row, "domain_verified", False)),
            organization_verified=bool(getattr(row, "organization_verified", False)),
            deployment_live=bool(getattr(row, "deployment_live", False)),
            product_activity_verified=bool(getattr(row, "product_activity_verified", False)),
            team_verified_count=int(getattr(row, "verified_team_count", 0) or 0),
            milestone_count=int(getattr(row, "milestone_count", 0) or 0),
            github_repo_count=int(getattr(row, "github_repo_count", 0) or 0),
            github_commit_count=int(getattr(row, "github_commit_count", 0) or 0),
            github_contributor_count=int(getattr(row, "github_contributor_count", 0) or 0),
            github_last_activity_at=getattr(row, "github_last_activity_at", None),
            deployments_30d=int(getattr(row, "deployments_30d", 0) or 0),
            last_deployment_at=getattr(row, "last_deployment_at", None),
            mau=int(getattr(row, "mau", 0) or 0),
            dau=int(getattr(row, "dau", 0) or 0),
            growth_rate_pct=float(getattr(row, "growth_rate_pct", 0.0) or 0.0),
            retention_rate_pct=float(getattr(row, "retention_rate_pct", 0.0) or 0.0),
            last_sync_at=getattr(row, "last_sync_at", None),
            verification_status=self._value(getattr(row, "verification_status", VerificationStatus.UNVERIFIED.value)),
            trust_score=float(getattr(row, "trust_score", 0.0) or 0.0),
        )

    def _badge_records(self, profile: FounderTrustProfile, snapshot_rows: List[Any]) -> List[Any]:
        if snapshot_rows:
            return [
                row for row in snapshot_rows
                if self._value(getattr(row, "status", "")) == VerificationStatus.VERIFIED.value
            ]
        return [badge for badge in TrustEngineComputer.compute_badges(profile) if badge.is_active]

    def _badge_detail(self, badge: Any) -> Dict[str, Any]:
        source = self._value(getattr(badge, "source", "trust"))
        return {
            "badgeType": str(getattr(badge, "badge_type", "trust_badge")),
            "label": str(getattr(badge, "label", "Trust Badge")),
            "source": source,
            "status": self._value(getattr(badge, "status", VerificationStatus.VERIFIED.value)),
            "confidence": 100,
            "lastUpdated": self._freshness_label(getattr(badge, "issued_at", None)),
            "expiresAt": self._iso(getattr(badge, "expires_at", None)),
        }

    def _verification_items(self, profile: FounderTrustProfile, histories: List[Any]) -> List[Dict[str, Any]]:
        latest = self._latest_by_source(histories)

        def item(source: str, verified: bool, confidence: int = 90) -> Dict[str, Any]:
            row = latest.get(source)
            status = self._value(getattr(row, "status", None)) if row else (VerificationStatus.VERIFIED.value if verified else VerificationStatus.PENDING.value)
            label_meta = self.SOURCE_LABELS[source]
            return {
                "label": label_meta["label"],
                "source": source,
                "provider": label_meta["provider"],
                "status": status,
                "confidence": int(round((float(getattr(row, "confidence", confidence / 100) or confidence / 100) * 100))) if row else confidence,
                "lastUpdated": self._freshness_label(getattr(row, "created_at", None)),
                "freshness": self._freshness_state(status),
                "action": "Reconnect required" if status in {VerificationStatus.EXPIRED.value, VerificationStatus.DISCONNECTED.value} else None,
            }

        founder_verified = profile.email_verified or profile.phone_verified or profile.linkedin_connected
        return [
            item(VerificationSource.EMAIL.value, founder_verified, 100 if founder_verified else 50),
            item(VerificationSource.ORGANIZATION.value, profile.organization_verified, 92),
            item(VerificationSource.DOMAIN.value, profile.domain_verified, 98),
            item(VerificationSource.GITHUB.value, profile.github_connected, 94),
            item(VerificationSource.TEAM.value, profile.team_verified_count > 0, 88),
            item(VerificationSource.DEPLOYMENT.value, profile.deployment_live, 96),
            item(VerificationSource.PRODUCT_ANALYTICS.value, profile.product_activity_verified or profile.mau > 0 or profile.dau > 0, 91),
        ]

    def _founder_overview(self, profile: FounderTrustProfile, project: Any) -> Dict[str, Any]:
        founder_verified = profile.email_verified or profile.phone_verified or profile.linkedin_connected
        return {
            "founders": 1,
            "verificationStatus": "Verified" if founder_verified else "Pending",
            "professionalProfilesConnected": int(profile.linkedin_connected) + int(profile.github_connected),
            "githubConnected": profile.github_connected,
            "linkedinConnected": profile.linkedin_connected,
            "companyEmailVerified": profile.email_verified,
            "yearsBuildingStartup": self._years_since(getattr(project, "created_at", None)),
            "previousVentures": "Not disclosed",
            "responseRate": "Not measured",
        }

    def _product_development(self, profile: FounderTrustProfile) -> Dict[str, Any]:
        activity = "Daily" if profile.github_commit_count >= 30 else ("Weekly" if profile.github_connected else "Not connected")
        return {
            "developmentStatus": "Active" if profile.github_connected else "Pending verification",
            "repositoryConnected": profile.github_connected,
            "recentActivity": activity,
            "contributorsVerified": profile.github_contributor_count,
            "deploymentFrequency": "Weekly" if profile.deployments_30d else "Not verified",
            "latestDeployment": self._freshness_label(profile.last_deployment_at),
            "developmentConsistency": "High" if profile.github_commit_count >= 30 else ("Moderate" if profile.github_connected else "Not verified"),
            "activityTrend": self._activity_trend(profile),
        }

    def _product_verification(self, profile: FounderTrustProfile) -> Dict[str, Any]:
        return {
            "productStatus": "Live" if profile.deployment_live else "Pending verification",
            "websiteVerified": profile.domain_verified,
            "deploymentsVerified": profile.deployment_live,
            "latestDeployment": self._freshness_label(profile.last_deployment_at),
            "supportedPlatforms": self._platforms(profile),
            "verificationFreshness": self._freshness_label(profile.last_sync_at),
        }

    def _product_activity(self, profile: FounderTrustProfile) -> Dict[str, Any]:
        verified = profile.product_activity_verified or profile.mau > 0 or profile.dau > 0
        return {
            "monthlyActiveUsers": "Verified" if verified else "Not connected",
            "dailyActiveUsers": "Verified" if verified else "Not connected",
            "growthTrend": "Positive" if profile.growth_rate_pct > 0 else "Not verified",
            "retention": "Verified" if profile.retention_rate_pct > 0 else "Not connected",
            "dataFreshness": self._freshness_label(profile.last_sync_at),
        }

    @staticmethod
    def _team_overview(profile: FounderTrustProfile) -> Dict[str, Any]:
        verified = profile.team_verified_count
        return {
            "teamMembers": max(verified, 1),
            "verifiedMembers": verified,
            "pendingVerification": 0,
            "averageVerificationAge": "Not measured",
            "technicalContributors": profile.github_contributor_count,
            "activeThisMonth": profile.github_connected or profile.deployment_live,
        }

    def _timeline_events(self, histories: List[Any], timelines: List[Any]) -> List[Dict[str, Any]]:
        events: List[Dict[str, Any]] = []
        for row in timelines:
            events.append({
                "id": f"timeline_{self._id(getattr(row, 'id', 'event'))}",
                "when": self._freshness_label(getattr(row, "created_at", None)),
                "title": self._title_from_event(getattr(row, "event_type", "Trust event")),
                "source": self._value(getattr(row, "source", "trust")),
                "status": VerificationStatus.VERIFIED.value,
                "confidence": 100,
            })
        for row in histories:
            events.append({
                "id": f"history_{self._id(getattr(row, 'id', getattr(row, 'verification_id', 'event')))}",
                "when": self._freshness_label(getattr(row, "created_at", None)),
                "title": self._title_from_event(getattr(row, "event_type", "Verification updated")),
                "source": self._value(getattr(row, "source", "trust")),
                "status": self._value(getattr(row, "status", VerificationStatus.PENDING.value)),
                "confidence": int(round(float(getattr(row, "confidence", 0.0) or 0.0) * 100)),
            })
        return events[:10]

    def _milestones(self, milestones: List[Any], histories: List[Any]) -> List[Dict[str, Any]]:
        rows: List[Dict[str, Any]] = []
        for milestone in milestones[:8]:
            completed = bool(getattr(milestone, "is_completed", False) or getattr(milestone, "completed_at", None))
            rows.append({
                "id": self._id(getattr(milestone, "id", getattr(milestone, "title", "milestone"))),
                "title": str(getattr(milestone, "title", "Milestone")),
                "status": "verified" if completed else "pending_review",
                "evidence": "Approved milestone metadata" if completed else "Evidence pending review",
                "approvalDate": self._iso(getattr(milestone, "completed_at", None)),
                "verifier": "TechIT Review" if completed else None,
            })
        if rows:
            return rows
        milestone_history = [row for row in histories if self._value(getattr(row, "source", "")) == VerificationSource.MILESTONE.value]
        return [
            {
                "id": self._id(getattr(row, "id", getattr(row, "verification_id", "milestone"))),
                "title": self._title_from_event(getattr(row, "event_type", "Milestone reviewed")),
                "status": "verified" if self._value(getattr(row, "status", "")) == VerificationStatus.VERIFIED.value else "pending_review",
                "evidence": "Approved evidence metadata",
                "approvalDate": self._iso(getattr(row, "created_at", None)),
                "verifier": "TechIT Review",
            }
            for row in milestone_history[:5]
        ]

    def _verification_sources(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [
            {
                "label": item["label"],
                "status": item["status"],
                "origin": self.SOURCE_LABELS.get(item["source"], {}).get("origin", item["provider"]),
                "lastSync": item["lastUpdated"],
            }
            for item in items
        ]

    def _risk_status(self, items: List[Dict[str, Any]]) -> Dict[str, Any]:
        expired = [item for item in items if item["status"] == VerificationStatus.EXPIRED.value]
        failed = [item for item in items if item["status"] == VerificationStatus.FAILED.value]
        disconnected = [item for item in items if item["status"] == VerificationStatus.DISCONNECTED.value]
        missing = [item for item in items if item["status"] == VerificationStatus.PENDING.value]
        issues = [
            {"title": item["label"], "detail": item.get("action") or "Verification requires attention", "lastSync": item["lastUpdated"]}
            for item in expired + failed + disconnected
        ]
        return {
            "verificationFreshness": "Needs attention" if issues else "Excellent",
            "missingIntegrations": len(missing),
            "expiredVerification": ", ".join(item["label"] for item in expired) if expired else "None",
            "recentVerificationFailures": ", ".join(item["label"] for item in failed) if failed else "None",
            "trustTrend": "Needs attention" if issues else "Stable",
            "issues": issues,
        }

    @staticmethod
    def _continuous_verification(profile: FounderTrustProfile, histories: List[Any], summary: Dict[str, Any]) -> Dict[str, Any]:
        failures = [
            row for row in histories
            if InvestorTrustReadService._value(getattr(row, "status", "")) in {VerificationStatus.FAILED.value, VerificationStatus.EXPIRED.value}
        ]
        total = max(len(histories), 1)
        success_rate = int(round(((total - len(failures)) / total) * 100))
        return {
            "status": "running",
            "lastVerification": summary["lastVerified"],
            "nextVerification": "Scheduled by Trust worker",
            "connectedServices": summary["evidenceSourcesConnected"],
            "successRate": f"{success_rate}%",
        }

    @staticmethod
    def _investment_readiness(profile: FounderTrustProfile, summary: Dict[str, Any]) -> Dict[str, Any]:
        founder_verified = profile.email_verified or profile.phone_verified or profile.linkedin_connected
        return {
            "founderVerified": founder_verified,
            "organizationVerified": profile.organization_verified,
            "productLive": profile.deployment_live,
            "developmentActive": profile.github_connected and profile.github_commit_count > 0,
            "teamVerifiedPct": 100 if profile.team_verified_count else 0,
            "operationalEvidence": "Strong" if summary["confidence"] >= 80 else ("Moderate" if summary["confidence"] >= 50 else "Limited"),
            "verificationFreshness": InvestorTrustReadService._health_label(summary["verificationHealth"]),
        }

    def _evidence_explorer(self, items: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [
            {
                "id": item["source"],
                "metric": item["label"],
                "status": item["status"],
                "evidenceSource": item["provider"],
                "verifiedAt": item["lastUpdated"],
                "confidence": item["confidence"],
                "details": "Verified metadata only; raw provider payloads and sensitive records are not exposed.",
            }
            for item in items
        ]

    @staticmethod
    def _empty_private_notes(bookmarked: bool) -> Dict[str, Any]:
        return {
            "note": "",
            "internalRating": "none",
            "followUpReminder": "",
            "checklist": [
                {"item": "Review verification sources", "done": False},
                {"item": "Check milestone evidence", "done": False},
                {"item": "Confirm continuous verification status", "done": False},
                {"item": "Add partner notes", "done": False},
            ],
            "bookmarked": bookmarked,
        }

    @staticmethod
    def _latest_by_source(histories: List[Any]) -> Dict[str, Any]:
        latest: Dict[str, Any] = {}
        for row in histories:
            source = InvestorTrustReadService._value(getattr(row, "source", ""))
            latest.setdefault(source, row)
        return latest

    @staticmethod
    def _evidence_source_count(profile: FounderTrustProfile) -> int:
        return sum([
            profile.email_verified or profile.phone_verified or profile.linkedin_connected,
            profile.organization_verified,
            profile.domain_verified,
            profile.github_connected,
            profile.team_verified_count > 0,
            profile.deployment_live,
            profile.product_activity_verified or profile.mau > 0 or profile.dau > 0,
            profile.milestone_count > 0,
        ])

    @staticmethod
    def _activity_trend(profile: FounderTrustProfile) -> List[Dict[str, int | str]]:
        base = max(0, min(profile.github_commit_count, 100))
        deployments = max(0, profile.deployments_30d)
        return [
            {"label": f"W{index}", "activity": max(0, base - ((6 - index) * 4)), "deployments": max(0, deployments - (6 - index))}
            for index in range(1, 7)
        ]

    @staticmethod
    def _platforms(profile: FounderTrustProfile) -> List[str]:
        platforms = []
        if profile.github_connected:
            platforms.append("GitHub")
        if profile.deployment_live:
            platforms.append("Deployment Platform")
        if profile.product_activity_verified or profile.mau or profile.dau:
            platforms.append("Analytics")
        return platforms or ["Not connected"]

    @staticmethod
    def _project_metadata(project: Any, key: str, default: str) -> str:
        for attr in ("transparency_items", "compliance_items"):
            value = getattr(project, attr, None)
            if isinstance(value, dict) and value.get(key):
                return str(value[key])
        return default

    @staticmethod
    def _website(project: Any) -> str:
        for attr in ("transparency_items", "compliance_items"):
            value = getattr(project, attr, None)
            if isinstance(value, dict) and value.get("website"):
                return str(value["website"])
        return "Not disclosed"

    @staticmethod
    def _overall_status(score: int, status: str) -> str:
        if status == VerificationStatus.VERIFIED.value or score >= 60:
            return "Verified"
        if score > 0:
            return "Partially Verified"
        return "Pending Verification"

    @staticmethod
    def _health(score: int, profile: FounderTrustProfile, computed: Dict[str, Any]) -> str:
        if profile.verification_status in {VerificationStatus.EXPIRED.value, VerificationStatus.FAILED.value, VerificationStatus.DISCONNECTED.value}:
            return "needs_attention"
        if score >= 85:
            return "excellent"
        if score >= 50:
            return "good"
        return "needs_attention"

    @staticmethod
    def _health_label(health: str) -> str:
        return "Needs attention" if health == "needs_attention" else str(health).capitalize()

    @staticmethod
    def _freshness_state(status: str) -> str:
        if status == VerificationStatus.EXPIRED.value:
            return "Reconnect required"
        if status == VerificationStatus.DISCONNECTED.value:
            return "Disconnected"
        if status == VerificationStatus.FAILED.value:
            return "Failed"
        if status == VerificationStatus.PENDING.value:
            return "Pending"
        return "Fresh"

    @staticmethod
    def _freshness_label(value: Any) -> str:
        if not value:
            return "Not verified"
        if isinstance(value, datetime):
            return value.isoformat()
        return str(value)

    @staticmethod
    def _years_since(value: Any) -> int:
        if not isinstance(value, datetime):
            return 0
        return max(0, datetime.utcnow().year - value.year)

    @staticmethod
    def _year(value: Any) -> str:
        if isinstance(value, datetime):
            return str(value.year)
        return "Not disclosed"

    @staticmethod
    def _title_from_event(value: Any) -> str:
        text = str(value or "Trust event").replace("_", " ").strip()
        return text[:1].upper() + text[1:]

    @staticmethod
    def _logo_text(name: str) -> str:
        parts = [part for part in name.replace("-", " ").split(" ") if part]
        if len(parts) >= 2:
            return f"{parts[0][0]}{parts[1][0]}".upper()
        return name[:2].upper() if name else "ST"

    @staticmethod
    def _id(value: Any) -> str:
        return str(value) if value is not None else ""

    @staticmethod
    def _value(value: Any) -> Any:
        return value.value if hasattr(value, "value") else value

    @staticmethod
    def _iso(value: Any) -> Optional[str]:
        if isinstance(value, datetime):
            return value.isoformat()
        if value is None:
            return None
        return str(value)

    @staticmethod
    def _unique(values: Iterable[str]) -> List[str]:
        seen = set()
        result: List[str] = []
        for value in values:
            if value and value not in seen:
                seen.add(value)
                result.append(value)
        return result
