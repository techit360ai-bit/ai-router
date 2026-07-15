"""DB-backed read/write helpers for live app domain sections.

The ai-router service layer historically returned well-shaped demo records from
``integration_guide.py``. This repository centralises durable access for those
same contracts. Production and staging require ``DATABASE_URL``; local tests may
use the empty in-memory store so contract tests do not need Postgres.
"""

from __future__ import annotations

from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime
from decimal import Decimal
import os
import uuid
from typing import Any, Callable, Dict, Iterator, List, Optional

from sqlalchemy import func, or_
from sqlalchemy.orm import sessionmaker

from runtime_config import PROD_ENVS, database_engine_options
from database_schema import (
    CapTableEntry,
    CapitalPool,
    CollaboratorEarning,
    DataRoom,
    DataRoomAccess,
    DealDocument,
    DealRoom,
    DilutionEvent,
    EquityGrant,
    FeedPost,
    Hackathon,
    HackathonBrief,
    HackathonCheckIn,
    HackathonScore,
    HackathonTeam,
    HackathonTeamReport,
    InvestorEVISnapshot,
    InvestorReputation,
    InvestorReview,
    InvestorWatchlist,
    Organization,
    OrgMember,
    Payout,
    PoolMilestoneRelease,
    Project,
    ProjectAnalysis,
    ProjectStageEnum,
    TermSheet,
    VentureIntake,
    VenturePipelineRun,
    Workspace,
)


_ENGINE = None
_SESSION_FACTORY: Optional[sessionmaker] = None

_MEMORY: Dict[str, List[Dict[str, Any]]] = {
    "projects": [],
    "projectAnalyses": [],
    "ventureIntakes": [],
    "venturePipelineRuns": [],
    "workspaces": [],
    "equityGrants": [],
    "dilutionEvents": [],
    "collaboratorEarnings": [],
    "payouts": [],
    "capitalPools": [],
    "poolReleases": [],
    "dealRooms": [],
    "termSheets": [],
    "dealDocuments": [],
    "dataRooms": [],
    "dataRoomAccess": [],
    "investorReputation": [],
    "investorReviews": [],
    "feedPosts": [],
    "organizations": [],
    "orgMembers": [],
    "hackathons": [],
    "hackathonTeams": [],
    "hackathonBriefs": [],
    "hackathonCheckIns": [],
    "hackathonScores": [],
    "hackathonTeamReports": [],
}


class LiveDomainDatabaseUnavailable(RuntimeError):
    """Raised when live domain persistence is required but unavailable."""


def _is_prod_env() -> bool:
    return os.getenv("ENVIRONMENT", "development").strip().lower() in PROD_ENVS


def _database_url() -> str:
    return os.getenv("DATABASE_URL", "").strip()


def _get_session_factory() -> sessionmaker:
    global _ENGINE, _SESSION_FACTORY
    if _SESSION_FACTORY is None:
        from sqlalchemy import create_engine

        database_url = _database_url()
        if not database_url:
            raise LiveDomainDatabaseUnavailable("DATABASE_URL is required for live domain persistence")
        _ENGINE = create_engine(database_url, **database_engine_options(database_url))
        _SESSION_FACTORY = sessionmaker(bind=_ENGINE, expire_on_commit=False)
    return _SESSION_FACTORY


def _uuid(value: Any) -> Optional[uuid.UUID]:
    if value is None or value == "":
        return None
    try:
        return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))
    except (TypeError, ValueError, AttributeError):
        return None


def _new_uuid(value: Any = None) -> uuid.UUID:
    return _uuid(value) or uuid.uuid4()


def _str_id(value: Any) -> Optional[str]:
    if value is None:
        return None
    return str(value)


def _now() -> datetime:
    return datetime.utcnow()


def _num(value: Any, default: float = 0.0) -> float:
    if isinstance(value, Decimal):
        return float(value)
    try:
        return float(value if value is not None else default)
    except (TypeError, ValueError):
        return default


def _int(value: Any, default: int = 0) -> int:
    try:
        return int(value if value is not None else default)
    except (TypeError, ValueError):
        return default


def _iso(value: Any) -> Optional[str]:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return str(value)


def _stage(value: Any) -> ProjectStageEnum:
    if isinstance(value, ProjectStageEnum):
        return value
    raw = str(value or "idea").strip().lower()
    try:
        return ProjectStageEnum(raw)
    except ValueError:
        return ProjectStageEnum.IDEA


def _stage_value(value: Any) -> str:
    if hasattr(value, "value"):
        return str(value.value)
    raw = str(value or "idea")
    return raw.lower()


def _crs_band(score10: float) -> str:
    return ">7" if score10 > 7 else "4-6" if score10 >= 4 else "<4"


def _sort_newest(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return sorted(rows, key=lambda r: str(r.get("updatedAt") or r.get("createdAt") or ""), reverse=True)


def reset_memory_store_for_tests() -> None:
    for rows in _MEMORY.values():
        rows.clear()


class LiveDomainRepository:
    def __init__(self, db: Any = None) -> None:
        self.db = db
        self.database_backed = db is not None or bool(_database_url())
        if not self.database_backed and _is_prod_env():
            raise LiveDomainDatabaseUnavailable("DATABASE_URL is required outside local development")

    @contextmanager
    def _session(self, *, write: bool = False) -> Iterator[Any]:
        if not self.database_backed:
            yield None
            return

        if self.db is not None:
            try:
                yield self.db
                if write and hasattr(self.db, "commit"):
                    self.db.commit()
            except Exception:
                if write and hasattr(self.db, "rollback"):
                    self.db.rollback()
                raise
            return

        Session = _get_session_factory()
        session = Session()
        try:
            yield session
            if write:
                session.commit()
        except Exception:
            if write:
                session.rollback()
            raise
        finally:
            session.close()

    def _memory_insert(self, name: str, row: Dict[str, Any]) -> Dict[str, Any]:
        now = _now().isoformat()
        next_row = {"id": row.get("id") or f"{name}_{uuid.uuid4().hex[:12]}", **row}
        next_row.setdefault("createdAt", now)
        next_row["updatedAt"] = now
        _MEMORY[name].append(next_row)
        return deepcopy(next_row)

    # ------------------------------------------------------------------
    # Founder projects, dashboard scores, incubation persistence
    # ------------------------------------------------------------------
    def list_founder_projects(self, user_id: str) -> List[Dict[str, Any]]:
        if not self.database_backed:
            return _sort_newest([deepcopy(p) for p in _MEMORY["projects"] if p.get("ownerId") == user_id])

        uid = _uuid(user_id)
        if uid is None:
            return []
        with self._session() as db:
            projects = (
                db.query(Project)
                .filter(Project.owner_id == uid)
                .order_by(Project.updated_at.desc().nullslast(), Project.created_at.desc().nullslast())
                .all()
            )
            workspace_project_ids = {
                str(row.project_id)
                for row in db.query(Workspace.project_id).filter(Workspace.owner_id == uid).all()
            }
            return [self._project_dict(project, str(project.id) in workspace_project_ids) for project in projects]

    def create_project(self, user_id: str, body: Dict[str, Any]) -> Dict[str, Any]:
        title = str(body.get("title") or "").strip()
        if not title:
            return {"ok": False, "error": "title_required"}
        origin = body.get("origin")
        hackathon_id = body.get("hackathonId") or body.get("hackathon_id")
        team_id = body.get("teamId") or body.get("team_id")
        if origin is None and hackathon_id and team_id:
            origin = {"kind": "hackathon_promote", "hackathonId": hackathon_id, "teamId": team_id}

        if not self.database_backed:
            project = self._memory_insert("projects", {
                "ownerId": user_id,
                "title": title,
                "tagline": body.get("tagline", ""),
                "industry": body.get("industry", ""),
                "stage": _stage_value(body.get("stage")),
                "isPrimary": False,
                "gsisScore": 0,
                "hasWorkspace": False,
                "origin": origin,
            })
            return {"ok": True, "project": project}

        uid = _uuid(user_id)
        if uid is None:
            return {"ok": False, "error": "invalid_user_id"}
        with self._session(write=True) as db:
            project = Project(
                id=_new_uuid(body.get("id")),
                owner_id=uid,
                title=title,
                tagline=body.get("tagline", ""),
                industry=body.get("industry", ""),
                stage=_stage(body.get("stage")),
                origin=origin,
                gsis_score=0,
            )
            db.add(project)
            db.flush()
            return {"ok": True, "project": self._project_dict(project, False)}

    def persist_intake(self, user_id: str, submission: Dict[str, Any], structured_profile: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if not self.database_backed:
            intake = self._memory_insert("ventureIntakes", {
                "ownerId": user_id,
                "status": "diagnosed",
                "submission": deepcopy(submission),
                "structuredProfile": deepcopy(structured_profile or {}),
            })
            return {"intake": intake}

        uid = _uuid(user_id)
        if uid is None:
            return {"intake": None}
        with self._session(write=True) as db:
            intake = VentureIntake(
                id=uuid.uuid4(),
                owner_id=uid,
                status="diagnosed",
                submission=submission,
                structured_profile=structured_profile or {},
            )
            db.add(intake)
            db.flush()
            return {"intake": self._intake_dict(intake)}

    def persist_analysis(self, user_id: str, venture_data: Dict[str, Any], blueprint: Dict[str, Any], module: str = "pipeline") -> str:
        project_id = venture_data.get("project_id") or venture_data.get("projectId")

        if not self.database_backed:
            if not project_id:
                created = self.create_project(user_id, {
                    "title": venture_data.get("startup_name") or venture_data.get("title") or "Untitled venture",
                    "tagline": venture_data.get("tagline", ""),
                    "industry": venture_data.get("industry", ""),
                    "stage": venture_data.get("stage", "idea"),
                    "origin": {"kind": "incubation_pipeline"},
                })
                project_id = created.get("project", {}).get("id")
            self._memory_insert("projectAnalyses", {
                "ownerId": user_id,
                "projectId": project_id,
                "module": module,
                "ventureName": blueprint.get("venture_name") or venture_data.get("startup_name"),
                "blueprint": deepcopy(blueprint),
                "investmentScore": _num(blueprint.get("investment_score")),
                "unicornPotentialScore": _num(blueprint.get("unicorn_potential_score")),
                "pivotNeeded": bool(blueprint.get("pivot_needed")),
            })
            self._memory_insert("venturePipelineRuns", {
                "ownerId": user_id,
                "projectId": project_id,
                "module": module,
                "input": deepcopy(venture_data),
                "blueprint": deepcopy(blueprint),
                "status": "completed",
            })
            return str(project_id)

        uid = _uuid(user_id)
        if uid is None:
            return str(project_id or "")
        with self._session(write=True) as db:
            project_uuid = _uuid(project_id)
            project = db.get(Project, project_uuid) if project_uuid else None
            if project is None:
                project = Project(
                    id=uuid.uuid4(),
                    owner_id=uid,
                    title=venture_data.get("startup_name") or venture_data.get("title") or "Untitled venture",
                    tagline=venture_data.get("tagline", ""),
                    industry=venture_data.get("industry", ""),
                    stage=_stage(venture_data.get("stage")),
                    origin={"kind": "incubation_pipeline"},
                )
                db.add(project)
                db.flush()

            project.gsis_score = _num(blueprint.get("gsis_score"), _num(getattr(project, "gsis_score", 0)))
            project.unicorn_potential_score = _num(blueprint.get("unicorn_potential_score"), _num(getattr(project, "unicorn_potential_score", 0)))
            project.investment_score = _num(blueprint.get("investment_score"), _num(getattr(project, "investment_score", 0)))
            project.evi_i_score = _num(blueprint.get("evi_i"), _num(getattr(project, "evi_i_score", 0)))

            analysis = ProjectAnalysis(
                id=uuid.uuid4(),
                project_id=project.id,
                owner_id=uid,
                venture_name=blueprint.get("venture_name") or venture_data.get("startup_name"),
                blueprint=blueprint,
                unicorn_potential_score=_num(blueprint.get("unicorn_potential_score")),
                investment_score=_num(blueprint.get("investment_score")),
                pivot_needed=bool(blueprint.get("pivot_needed")),
            )
            db.add(analysis)
            db.add(VenturePipelineRun(
                id=uuid.uuid4(),
                owner_id=uid,
                project_id=project.id,
                module=module,
                input_payload=venture_data,
                blueprint=blueprint,
                status="completed",
            ))
            db.flush()
            return str(project.id)

    def dashboard_intelligence(self, user_id: str) -> Dict[str, Any]:
        projects = self.list_founder_projects(user_id)
        primary = projects[0] if projects else None
        score = _num(primary.get("gsisScore") if primary else 0)
        return {
            "gsis": score,
            "score_card": {
                "projectCount": len(projects),
                "primaryProject": primary.get("title") if primary else None,
                "averageGsis": round(sum(_num(p.get("gsisScore")) for p in projects) / len(projects), 2) if projects else 0,
            },
            "alerts": [] if projects else [{"type": "empty_state", "message": "No projects have been created yet."}],
            "insights": [],
            "top_action": "Create or import a venture to begin live tracking." if not projects else None,
        }

    # ------------------------------------------------------------------
    # Workspaces
    # ------------------------------------------------------------------
    def list_workspaces(self, user_id: str) -> List[Dict[str, Any]]:
        if not self.database_backed:
            return _sort_newest([deepcopy(w) for w in _MEMORY["workspaces"] if w.get("ownerId") == user_id])
        uid = _uuid(user_id)
        if uid is None:
            return []
        with self._session() as db:
            rows = db.query(Workspace).filter(Workspace.owner_id == uid).order_by(Workspace.updated_at.desc().nullslast()).all()
            return [self._workspace_dict(row) for row in rows]

    def provision_workspace(self, user_id: str, body: Dict[str, Any]) -> Dict[str, Any]:
        project_id = body.get("projectId") or body.get("project_id")
        if not project_id:
            return {"ok": False, "error": "projectId_required"}

        if not self.database_backed:
            existing = next((w for w in _MEMORY["workspaces"] if w.get("ownerId") == user_id and w.get("projectId") == project_id), None)
            if existing:
                return {"ok": True, "workspace": deepcopy(existing)}
            analysis = next((a for a in reversed(_MEMORY["projectAnalyses"]) if a.get("projectId") == project_id), None)
            workspace = self._memory_insert("workspaces", {
                "ownerId": user_id,
                "projectId": project_id,
                "name": body.get("name") or analysis.get("ventureName") if analysis else body.get("name", "Venture Workspace"),
                "status": "active",
                "seededFromAnalysis": bool(analysis),
                "seedAnalysisId": analysis.get("id") if analysis else None,
            })
            return {"ok": True, "workspace": workspace}

        uid = _uuid(user_id)
        pid = _uuid(project_id)
        if uid is None or pid is None:
            return {"ok": False, "error": "invalid_project_id"}
        with self._session(write=True) as db:
            existing = db.query(Workspace).filter(Workspace.owner_id == uid, Workspace.project_id == pid).first()
            if existing:
                return {"ok": True, "workspace": self._workspace_dict(existing)}
            analysis = (
                db.query(ProjectAnalysis)
                .filter(ProjectAnalysis.project_id == pid, ProjectAnalysis.owner_id == uid)
                .order_by(ProjectAnalysis.created_at.desc())
                .first()
            )
            workspace = Workspace(
                id=uuid.uuid4(),
                owner_id=uid,
                project_id=pid,
                name=body.get("name") or analysis.venture_name if analysis else body.get("name", "Venture Workspace"),
                status="active",
                seed_analysis_id=getattr(analysis, "id", None),
            )
            db.add(workspace)
            db.flush()
            return {"ok": True, "workspace": self._workspace_dict(workspace)}

    def workspace_context(self, user_id: str, workspace_id: str, project_id: Optional[str] = None) -> Dict[str, Any]:
        if not self.database_backed:
            workspace = next((w for w in _MEMORY["workspaces"] if w.get("ownerId") == user_id and w.get("id") == workspace_id), None)
            if not workspace:
                return {"workspaceId": workspace_id, "projectId": project_id, "venture": None, "blueprintAvailable": False}
            pid = project_id or workspace.get("projectId")
            analysis = next((a for a in reversed(_MEMORY["projectAnalyses"]) if a.get("projectId") == pid), None)
            return {"workspaceId": workspace_id, "projectId": pid, "venture": analysis.get("blueprint") if analysis else None, "blueprintAvailable": bool(analysis)}

        uid = _uuid(user_id)
        wid = _uuid(workspace_id)
        if uid is None or wid is None:
            return {"workspaceId": workspace_id, "projectId": project_id, "venture": None, "blueprintAvailable": False}
        with self._session() as db:
            workspace = db.query(Workspace).filter(Workspace.id == wid, Workspace.owner_id == uid).first()
            if workspace is None:
                return {"workspaceId": workspace_id, "projectId": project_id, "venture": None, "blueprintAvailable": False}
            pid = _uuid(project_id) or workspace.project_id
            analysis = (
                db.query(ProjectAnalysis)
                .filter(ProjectAnalysis.project_id == pid, ProjectAnalysis.owner_id == uid)
                .order_by(ProjectAnalysis.created_at.desc())
                .first()
            )
            return {
                "workspaceId": str(workspace.id),
                "projectId": str(pid),
                "venture": analysis.blueprint if analysis else None,
                "blueprintAvailable": analysis is not None,
            }

    # ------------------------------------------------------------------
    # Collaborator equity and earnings
    # ------------------------------------------------------------------
    def collaborator_equity(self, user_id: str) -> Dict[str, Any]:
        holdings = self._equity_holdings(user_id)
        return {
            "holdings": holdings,
            "totals": self._equity_totals(holdings),
            "vestingTimeline": [self._vesting_series(h) for h in holdings],
        }

    def record_dilution_event(self, user_id: str, event: Dict[str, Any]) -> Dict[str, Any]:
        project_id = event.get("projectId") or event.get("project_id")
        holdings = self._equity_holdings(user_id)
        holding = next((h for h in holdings if h.get("projectId") == project_id), None)
        equity = _num(holding.get("equityPercent") if holding else 0)
        vested_pct = _num(holding.get("vestedPercent") if holding else 0)
        new_shares = _num(event.get("newSharesPercent"))
        consent = bool(event.get("consentGiven"))
        vested_equity = equity * (vested_pct / 100)
        unvested_equity = equity - vested_equity
        diluted = equity * (new_shares / 100) if consent else unvested_equity * (new_shares / 100)
        result = {
            "projectId": project_id,
            "newSharesPercent": new_shares,
            "consentGiven": consent,
            "protectedApplied": not consent,
            "equityBefore": round(equity, 4),
            "equityAfter": round(max(0, equity - diluted), 4),
            "shieldedEquity": round(vested_equity, 4),
        }
        if not self.database_backed:
            self._memory_insert("dilutionEvents", {"userId": user_id, **result})
            return result

        uid = _uuid(user_id)
        pid = _uuid(project_id)
        if uid is not None and pid is not None:
            with self._session(write=True) as db:
                db.add(DilutionEvent(
                    id=uuid.uuid4(),
                    project_id=pid,
                    new_shares_percent=new_shares,
                    affected_user_id=uid,
                    consent_given=consent,
                    protected_applied=not consent,
                    description=event.get("description"),
                ))
        return result

    def collaborator_earnings(self, user_id: str) -> Dict[str, Any]:
        earnings, payouts = self._earnings_and_payouts(user_id)
        return {"cashEarnings": earnings, "payouts": payouts, "totals": self._cash_totals(earnings, payouts)}

    def request_withdrawal(self, user_id: str, body: Dict[str, Any]) -> Dict[str, Any]:
        earnings, payouts = self._earnings_and_payouts(user_id)
        totals = self._cash_totals(earnings, payouts)
        amount = _num(body.get("amount"))
        if amount <= 0 or amount > totals["pendingUSD"]:
            return {"ok": False, "error": "invalid_amount", "available": totals["pendingUSD"]}

        if not self.database_backed:
            payout = self._memory_insert("payouts", {
                "userId": user_id,
                "monthIso": body.get("monthIso") or _now().strftime("%Y-%m"),
                "amount": amount,
                "status": "processing",
                "destination": body.get("destination"),
            })
            return {"ok": True, "payout": payout, "destination": payout.get("destination"), "newPendingUSD": round(totals["pendingUSD"] - amount, 2)}

        uid = _uuid(user_id)
        if uid is None:
            return {"ok": False, "error": "invalid_user_id", "available": totals["pendingUSD"]}
        with self._session(write=True) as db:
            payout = Payout(
                id=uuid.uuid4(),
                user_id=uid,
                month_iso=body.get("monthIso") or _now().strftime("%Y-%m"),
                amount_usd=amount,
                status="processing",
                destination=body.get("destination"),
            )
            db.add(payout)
            db.flush()
            return {"ok": True, "payout": self._payout_dict(payout), "destination": payout.destination, "newPendingUSD": round(totals["pendingUSD"] - amount, 2)}

    # ------------------------------------------------------------------
    # Investor sections
    # ------------------------------------------------------------------
    def investor_deal_flow(self, investor_id: str, filters: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if not self.database_backed:
            projects = [deepcopy(p) for p in _MEMORY["projects"]]
            watchlist = {w.get("projectId") for w in _MEMORY["dealRooms"] if w.get("investorId") == investor_id}
            return {"deal_flow": self._rank_projects(projects, watchlist), "ranking_formula": self._ranking_formula(), "filters_applied": filters or {}}

        iid = _uuid(investor_id)
        if iid is None:
            return {"deal_flow": [], "ranking_formula": self._ranking_formula(), "filters_applied": filters or {}}
        with self._session() as db:
            watchlist = {str(row.project_id) for row in db.query(InvestorWatchlist).filter(InvestorWatchlist.investor_id == iid).all()}
            snapshots = {
                str(row.project_id): row
                for row in (
                    db.query(InvestorEVISnapshot)
                    .order_by(InvestorEVISnapshot.project_id, InvestorEVISnapshot.computed_at.desc())
                    .all()
                )
            }
            rows = db.query(Project).order_by(Project.gsis_score.desc().nullslast()).limit(100).all()
            ranked = []
            for project in rows:
                item = self._project_dict(project, False)
                snapshot = snapshots.get(str(project.id))
                item.update({
                    "eviI": _num(getattr(snapshot, "adjusted_evi_i", None), _num(project.evi_i_score)),
                    "signal": getattr(snapshot, "signal", None),
                    "watchlisted": str(project.id) in watchlist,
                    "rankScore": _num(project.gsis_score) + _num(getattr(snapshot, "adjusted_evi_i", None)) * 0.4,
                })
                ranked.append(item)
            ranked.sort(key=lambda row: row.get("rankScore", 0), reverse=True)
            return {"deal_flow": ranked, "ranking_formula": self._ranking_formula(), "filters_applied": filters or {}}

    def capital_pools(self, investor_id: str) -> List[Dict[str, Any]]:
        if not self.database_backed:
            return _sort_newest([deepcopy(p) for p in _MEMORY["capitalPools"] if p.get("investorId") == investor_id])
        iid = _uuid(investor_id)
        if iid is None:
            return []
        with self._session() as db:
            rows = db.query(CapitalPool).filter(CapitalPool.investor_id == iid).order_by(CapitalPool.created_at.desc()).all()
            return [self._pool_dict(row) for row in rows]

    def create_capital_pool(self, investor_id: str, body: Dict[str, Any]) -> Dict[str, Any]:
        rules = body.get("rules") or {}
        if not self.database_backed:
            pool = self._memory_insert("capitalPools", {
                "investorId": investor_id,
                "name": body.get("name", "Untitled Pool"),
                "totalCapital": _num(body.get("totalCapital")),
                "deployed": 0,
                "startups": 0,
                "milestonesHit": 0,
                "fundsReleased": 0,
                "roiSimulation": 0,
                "rules": {
                    "minReadiness": _int(rules.get("minReadiness"), 80),
                    "maxPerStartup": _num(rules.get("maxPerStartup"), 20),
                    "milestoneTrigger": bool(rules.get("milestoneTrigger", True)),
                },
            })
            return {"ok": True, "pool": pool}

        iid = _uuid(investor_id)
        if iid is None:
            return {"ok": False, "error": "invalid_investor_id"}
        with self._session(write=True) as db:
            pool = CapitalPool(
                id=uuid.uuid4(),
                investor_id=iid,
                name=body.get("name", "Untitled Pool"),
                total_capital_usd=_num(body.get("totalCapital")),
                min_readiness=_int(rules.get("minReadiness"), 80),
                max_per_startup_percent=_num(rules.get("maxPerStartup"), 20),
                milestone_trigger=bool(rules.get("milestoneTrigger", True)),
            )
            db.add(pool)
            db.flush()
            return {"ok": True, "pool": self._pool_dict(pool)}

    def release_pool_milestone(self, investor_id: str, body: Dict[str, Any]) -> Dict[str, Any]:
        amount = _num(body.get("amount"))
        if amount <= 0:
            return {"ok": False, "error": "invalid_amount", "amountReleased": 0}
        pool_id = body.get("poolId")
        project_id = body.get("projectId")
        if not self.database_backed:
            self._memory_insert("poolReleases", {"investorId": investor_id, **body, "amountReleased": amount, "released": True})
            return {"ok": True, "poolId": pool_id, "projectId": project_id, "milestone": body.get("milestone"), "amountReleased": amount, "released": True}

        pool_uuid = _uuid(pool_id)
        project_uuid = _uuid(project_id)
        if pool_uuid is None or project_uuid is None:
            return {"ok": False, "error": "invalid_ids", "amountReleased": 0}
        with self._session(write=True) as db:
            release = PoolMilestoneRelease(
                id=uuid.uuid4(),
                pool_id=pool_uuid,
                project_id=project_uuid,
                milestone=body.get("milestone"),
                amount_usd=amount,
                released=True,
                triggered_at=_now(),
            )
            db.add(release)
            pool = db.get(CapitalPool, pool_uuid)
            if pool:
                pool.funds_released_usd = _num(pool.funds_released_usd) + amount
                pool.milestones_hit = _int(pool.milestones_hit) + 1
            return {"ok": True, "poolId": pool_id, "projectId": project_id, "milestone": body.get("milestone"), "amountReleased": amount, "released": True}

    def deal_rooms(self, investor_id: str) -> Dict[str, Any]:
        stage_order = ["Intro Call", "NDA Signed", "Due Diligence", "Term Sheet", "Negotiation", "Deal Closed"]
        if not self.database_backed:
            meta = {str(r.get("projectId")): deepcopy(r) for r in _MEMORY["dealRooms"] if r.get("investorId") == investor_id}
            return {"dealMeta": meta, "stageOrder": stage_order}
        iid = _uuid(investor_id)
        if iid is None:
            return {"dealMeta": {}, "stageOrder": stage_order}
        with self._session() as db:
            rows = db.query(DealRoom).filter(DealRoom.investor_id == iid).all()
            return {"dealMeta": {str(row.project_id): self._deal_meta(row) for row in rows}, "stageOrder": stage_order}

    def deal_room_detail(self, investor_id: str, project_id: str, startup: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        stage_order = ["Intro Call", "NDA Signed", "Due Diligence", "Term Sheet", "Negotiation", "Deal Closed"]
        valuation = _num((startup or {}).get("mrr")) * 12 * 8
        if not self.database_backed:
            room = next((r for r in _MEMORY["dealRooms"] if r.get("investorId") == investor_id and r.get("projectId") == project_id), None)
            if room is None:
                room = self._memory_insert("dealRooms", {"investorId": investor_id, "projectId": project_id, "status": "pending", "stage": "Intro Call", "daysOpen": 0, "messages": 0, "docs": 0})
            return {"projectId": project_id, "meta": room, "valuationUSD": valuation, "termSheet": None, "milestones": [], "documents": [], "negotiation": [], "stageOrder": stage_order}

        iid = _uuid(investor_id)
        pid = _uuid(project_id)
        if iid is None or pid is None:
            return {"projectId": project_id, "meta": None, "valuationUSD": valuation, "termSheet": None, "milestones": [], "documents": [], "negotiation": [], "stageOrder": stage_order}
        with self._session(write=True) as db:
            room = db.query(DealRoom).filter(DealRoom.investor_id == iid, DealRoom.project_id == pid).first()
            if room is None:
                room = DealRoom(id=uuid.uuid4(), investor_id=iid, project_id=pid, status="pending", stage="Intro Call", days_open=0, messages=0, docs=0, last_activity="just now")
                db.add(room)
                db.flush()
            term = db.query(TermSheet).filter(TermSheet.deal_room_id == room.id).first()
            documents = db.query(DealDocument).filter(DealDocument.deal_room_id == room.id).all()
            return {
                "projectId": project_id,
                "meta": self._deal_meta(room),
                "valuationUSD": valuation,
                "termSheet": self._term_sheet_dict(term) if term else None,
                "milestones": [],
                "documents": [self._deal_document_dict(doc) for doc in documents],
                "negotiation": [],
                "stageOrder": stage_order,
            }

    def data_rooms(self, investor_id: str) -> Dict[str, Any]:
        sections = DataRoomServiceSections
        if not self.database_backed:
            rooms = [deepcopy(r) for r in _MEMORY["dataRooms"] if any(a.get("dataRoomId") == r.get("id") and a.get("investorId") == investor_id for a in _MEMORY["dataRoomAccess"])]
            return self._data_rooms_payload(rooms, sections)
        iid = _uuid(investor_id)
        if iid is None:
            return self._data_rooms_payload([], sections)
        with self._session() as db:
            rows = (
                db.query(DataRoom)
                .join(DataRoomAccess, DataRoomAccess.data_room_id == DataRoom.id)
                .filter(DataRoomAccess.investor_id == iid, DataRoomAccess.revoked_at.is_(None))
                .all()
            )
            return self._data_rooms_payload([self._data_room_dict(row) for row in rows], sections)

    def grant_data_room_access(self, user_id: str, body: Dict[str, Any]) -> Dict[str, Any]:
        project_id = body.get("projectId") or body.get("project_id")
        investor_id = body.get("investorId") or body.get("investor_id") or user_id
        can_download = bool(body.get("canDownload", False))
        if not self.database_backed:
            room = next((r for r in _MEMORY["dataRooms"] if r.get("projectId") == project_id), None)
            if room is None:
                room = self._memory_insert("dataRooms", {"projectId": project_id, "sections": DataRoomServiceSections, "docCount": 0, "complianceVerified": False, "aiGovernanceVerified": False, "updatedLabel": "today"})
            access = self._memory_insert("dataRoomAccess", {"dataRoomId": room["id"], "investorId": investor_id, "canDownload": can_download, "granted": True})
            return {"ok": True, "projectId": project_id, "investorId": investor_id, "canDownload": can_download, "granted": access["granted"]}

        pid = _uuid(project_id)
        iid = _uuid(investor_id)
        if pid is None or iid is None:
            return {"ok": False, "error": "invalid_ids", "projectId": project_id, "investorId": investor_id}
        with self._session(write=True) as db:
            room = db.query(DataRoom).filter(DataRoom.project_id == pid).first()
            if room is None:
                room = DataRoom(id=uuid.uuid4(), project_id=pid, sections=DataRoomServiceSections, doc_count=0, compliance_verified=False, ai_governance_verified=False)
                db.add(room)
                db.flush()
            access = db.query(DataRoomAccess).filter(DataRoomAccess.data_room_id == room.id, DataRoomAccess.investor_id == iid).first()
            if access is None:
                access = DataRoomAccess(id=uuid.uuid4(), data_room_id=room.id, investor_id=iid)
                db.add(access)
            access.can_download = can_download
            access.granted = True
            access.revoked_at = None
            return {"ok": True, "projectId": project_id, "investorId": investor_id, "canDownload": can_download, "granted": True}

    def investor_reputation(self, investor_id: str) -> Dict[str, Any]:
        if not self.database_backed:
            rep = next((r for r in _MEMORY["investorReputation"] if r.get("investorId") == investor_id), None)
            reviews = [deepcopy(r) for r in _MEMORY["investorReviews"] if r.get("investorId") == investor_id]
            return self._reputation_payload(rep, reviews)
        iid = _uuid(investor_id)
        if iid is None:
            return self._reputation_payload(None, [])
        with self._session() as db:
            rep = db.query(InvestorReputation).filter(InvestorReputation.investor_id == iid).first()
            reviews = db.query(InvestorReview).filter(InvestorReview.investor_id == iid).order_by(InvestorReview.review_date.desc()).limit(20).all()
            return self._reputation_payload(self._reputation_dict(rep) if rep else None, [self._review_dict(row) for row in reviews])

    def heatmap(self) -> Dict[str, Any]:
        if not self.database_backed:
            return {"regions": [], "sectors": self._sector_rows([deepcopy(p) for p in _MEMORY["projects"]])}
        with self._session() as db:
            rows = db.query(Project.industry, func.count(Project.id), func.avg(Project.market_readiness_score)).group_by(Project.industry).all()
            sectors = [{"sector": industry or "Unspecified", "avgGrowth": round(_num(avg), 2), "startupCount": _int(count)} for industry, count, avg in rows]
            return {"regions": [], "sectors": sectors}

    # ------------------------------------------------------------------
    # Organization, feed, hackathons
    # ------------------------------------------------------------------
    def organization_dashboard(self, user_id: str) -> Dict[str, Any]:
        if not self.database_backed:
            orgs = [o for o in _MEMORY["organizations"] if o.get("ownerId") == user_id]
            hackathons = [h for h in _MEMORY["hackathons"] if h.get("ownerId") == user_id or h.get("orgOwnerId") == user_id]
            return {"dashboard": None, "metrics": {"organizations": len(orgs), "activePrograms": len(hackathons), "members": 0, "opportunities": 0}, "activity": [], "charts": {}}
        uid = _uuid(user_id)
        if uid is None:
            return {"dashboard": None, "metrics": {"organizations": 0, "activePrograms": 0, "members": 0, "opportunities": 0}, "activity": [], "charts": {}}
        with self._session() as db:
            orgs = db.query(Organization).filter(Organization.owner_id == uid).all()
            org_ids = [org.id for org in orgs]
            members = db.query(func.count(OrgMember.id)).filter(OrgMember.org_id.in_(org_ids)).scalar() if org_ids else 0
            hackathons = db.query(func.count(Hackathon.id)).filter(Hackathon.org_id.in_(org_ids)).scalar() if org_ids else 0
            return {
                "dashboard": None,
                "metrics": {
                    "organizations": len(orgs),
                    "activePrograms": _int(hackathons),
                    "members": _int(members),
                    "opportunities": 0,
                },
                "activity": [],
                "charts": {},
            }

    def feed_posts(self, user_id: str, limit: int = 30) -> Dict[str, Any]:
        limit = max(1, min(_int(limit, 30), 100))
        if not self.database_backed:
            posts = _sort_newest(deepcopy(_MEMORY["feedPosts"]))[:limit]
            return {"curated_feed": posts, "total_items": len(posts), "next_refresh_secs": 1800}
        with self._session() as db:
            rows = db.query(FeedPost).order_by(FeedPost.is_pinned.desc().nullslast(), FeedPost.ai_relevance_score.desc().nullslast(), FeedPost.created_at.desc()).limit(limit).all()
            posts = [self._feed_post_dict(row) for row in rows]
            return {"curated_feed": posts, "total_items": len(posts), "next_refresh_secs": 1800}

    def list_hackathons(self, user_id: str) -> List[Dict[str, Any]]:
        if not self.database_backed:
            return _sort_newest(deepcopy(_MEMORY["hackathons"]))
        uid = _uuid(user_id)
        with self._session() as db:
            rows = db.query(Hackathon).order_by(Hackathon.created_at.desc()).all()
            return [self._hackathon_dict(row, db) for row in rows if uid is None or True]

    def create_hackathon(self, user_id: str, body: Dict[str, Any]) -> Dict[str, Any]:
        if not self.database_backed:
            hackathon = self._memory_insert("hackathons", {"ownerId": user_id, "name": body.get("name") or body.get("title") or "Untitled hackathon", "theme": body.get("theme", ""), "status": body.get("status", "upcoming")})
            return {"ok": True, "hackathon": hackathon}
        uid = _uuid(user_id)
        with self._session(write=True) as db:
            org = db.query(Organization).filter(Organization.owner_id == uid).first() if uid else None
            hackathon = Hackathon(id=uuid.uuid4(), org_id=getattr(org, "id", None), name=body.get("name") or body.get("title") or "Untitled hackathon", theme=body.get("theme", ""), status=body.get("status", "upcoming"))
            db.add(hackathon)
            db.flush()
            return {"ok": True, "hackathon": self._hackathon_dict(hackathon, db)}

    def hackathon_overview(self, hackathon_id: str) -> Optional[Dict[str, Any]]:
        if not self.database_backed:
            teams = [t for t in _MEMORY["hackathonTeams"] if t.get("hackathonId") == hackathon_id]
            briefs = [b for b in _MEMORY["hackathonBriefs"] if b.get("hackathonId") == hackathon_id]
            members = sum(len(t.get("members") or []) for t in teams)
            velocity = self.hackathon_velocity(hackathon_id)["teams"]
            return {"hackathonId": hackathon_id, "status": "live", "registrants": members, "teamsFormed": sum(1 for t in teams if not t.get("isSolo")), "stillSolo": sum(1 for t in teams if t.get("isSolo")), "ideaSubmissions": len(briefs), "totalTeams": len(teams), "avgBuildVelocity": round(sum(v["activity"] for v in velocity) / len(velocity), 1) if velocity else 0}
        hid = _uuid(hackathon_id)
        if hid is None:
            return None
        with self._session() as db:
            hack = db.get(Hackathon, hid)
            if hack is None:
                return None
            teams = db.query(HackathonTeam).filter(HackathonTeam.hackathon_id == hid).all()
            briefs_count = db.query(func.count(HackathonBrief.id)).filter(HackathonBrief.hackathon_id == hid).scalar()
            velocity = self._hackathon_velocity_db(db, hid, teams)
            registrants = sum(len(team.members or []) for team in teams)
            return {"hackathonId": hackathon_id, "status": hack.status, "registrants": registrants, "teamsFormed": sum(1 for t in teams if not t.is_solo), "stillSolo": sum(1 for t in teams if t.is_solo), "ideaSubmissions": _int(briefs_count), "totalTeams": len(teams), "avgBuildVelocity": round(sum(v["activity"] for v in velocity) / len(velocity), 1) if velocity else 0}

    def hackathon_velocity(self, hackathon_id: str) -> Dict[str, Any]:
        if not self.database_backed:
            teams = [t for t in _MEMORY["hackathonTeams"] if t.get("hackathonId") == hackathon_id]
            checks = [c for c in _MEMORY["hackathonCheckIns"] if c.get("hackathonId") == hackathon_id]
            cells = []
            for team in teams:
                team_checks = [c for c in checks if c.get("teamId") == team.get("id")]
                activity = round(sum(_num(c.get("activityScore")) for c in team_checks) / len(team_checks), 1) if team_checks else 0
                cells.append({"teamId": team.get("id"), "name": team.get("name"), "activity": activity})
            return {"hackathonId": hackathon_id, "teams": cells}
        hid = _uuid(hackathon_id)
        if hid is None:
            return {"hackathonId": hackathon_id, "teams": []}
        with self._session() as db:
            teams = db.query(HackathonTeam).filter(HackathonTeam.hackathon_id == hid).all()
            return {"hackathonId": hackathon_id, "teams": self._hackathon_velocity_db(db, hid, teams)}

    def hackathon_leaderboard(self, hackathon_id: str) -> Dict[str, Any]:
        if not self.database_backed:
            teams = [t for t in _MEMORY["hackathonTeams"] if t.get("hackathonId") == hackathon_id]
            scores = {s.get("teamId"): s for s in _MEMORY["hackathonScores"] if s.get("hackathonId") == hackathon_id}
            board = [{"teamId": t.get("id"), "name": t.get("name"), "composite": _num(scores.get(t.get("id"), {}).get("composite")), "crsBand": _crs_band(_num(scores.get(t.get("id"), {}).get("composite")) / 10)} for t in teams]
            board.sort(key=lambda row: row["composite"], reverse=True)
            return {"hackathonId": hackathon_id, "leaderboard": board}
        hid = _uuid(hackathon_id)
        if hid is None:
            return {"hackathonId": hackathon_id, "leaderboard": []}
        with self._session() as db:
            teams = db.query(HackathonTeam).filter(HackathonTeam.hackathon_id == hid).all()
            scores = {str(row.team_id): row for row in db.query(HackathonScore).filter(HackathonScore.hackathon_id == hid).order_by(HackathonScore.updated_at.desc()).all()}
            board = [{"teamId": str(team.id), "name": team.name, "composite": _num(getattr(scores.get(str(team.id)), "composite", 0)), "crsBand": _crs_band(_num(getattr(scores.get(str(team.id)), "composite", 0)) / 10)} for team in teams]
            board.sort(key=lambda row: row["composite"], reverse=True)
            return {"hackathonId": hackathon_id, "leaderboard": board}

    def hackathon_pipeline(self, hackathon_id: str) -> Dict[str, Any]:
        board = self.hackathon_leaderboard(hackathon_id)["leaderboard"]
        crs = [_num(row.get("composite")) / 10 for row in board]
        return {"hackathonId": hackathon_id, "buckets": {"incubationInvites": sum(1 for v in crs if v > 7), "prototypeTrack": sum(1 for v in crs if 4 <= v <= 7), "backToLearning": sum(1 for v in crs if v < 4)}}

    def register_hackathon_team(self, user_id: str, body: Dict[str, Any]) -> Dict[str, Any]:
        hackathon_id = body.get("hackathonId")
        members = body.get("members") if isinstance(body.get("members"), list) else []
        is_solo = len(members) <= 1
        if not self.database_backed:
            team = self._memory_insert("hackathonTeams", {"hackathonId": hackathon_id, "leaderId": user_id, "name": body.get("name") or body.get("teamName") or "Untitled team", "members": members, "isSolo": is_solo, "status": "registered"})
            return {"ok": True, "team": team}
        uid = _uuid(user_id)
        hid = _uuid(hackathon_id)
        if uid is None or hid is None:
            return {"ok": False, "error": "invalid_ids"}
        with self._session(write=True) as db:
            team = HackathonTeam(id=uuid.uuid4(), hackathon_id=hid, captain_id=uid, name=body.get("name") or body.get("teamName") or "Untitled team", members=members, is_solo=is_solo, status="registered")
            db.add(team)
            db.flush()
            return {"ok": True, "team": self._hackathon_team_dict(team)}

    def submit_hackathon_brief(self, user_id: str, body: Dict[str, Any], score: Dict[str, Any], critiques: List[str]) -> Dict[str, Any]:
        hackathon_id = body.get("hackathonId")
        team_id = body.get("teamId")
        if not self.database_backed:
            brief = self._memory_insert("hackathonBriefs", {"hackathonId": hackathon_id, "teamId": team_id, "problem": body.get("problem", ""), "solution": body.get("solution", ""), "fields": body.get("fields") or {}, "score": score, "critiques": critiques})
            score_row = self._memory_insert("hackathonScores", {"hackathonId": hackathon_id, "teamId": team_id, "composite": score.get("composite"), **score})
            for team in _MEMORY["hackathonTeams"]:
                if team.get("id") == team_id and team.get("hackathonId") == hackathon_id:
                    team["hasBrief"] = True
                    team["status"] = "building" if team.get("status") == "registered" else team.get("status")
            return {"ok": True, "brief": brief, "score": score_row, "critiques": critiques}
        hid = _uuid(hackathon_id)
        tid = _uuid(team_id)
        if hid is None or tid is None:
            return {"ok": False, "error": "invalid_ids", "score": score, "critiques": critiques}
        with self._session(write=True) as db:
            team = db.get(HackathonTeam, tid)
            if team is None:
                return {"ok": False, "error": "team_not_found", "score": score, "critiques": critiques}
            brief = HackathonBrief(id=uuid.uuid4(), team_id=tid, hackathon_id=hid, problem=body.get("problem", ""), solution=body.get("solution", ""), fields=body.get("fields") or {}, problem_clarity_score=score.get("problemClarityScore", 0), team_momentum_score=score.get("teamMomentumScore", 0), demo_readiness_hours=score.get("demoReadinessHours", 0), composite_score=score.get("composite", 0), critiques=critiques)
            db.add(brief)
            db.add(HackathonScore(id=uuid.uuid4(), team_id=tid, hackathon_id=hid, judge_scores=body.get("judgeScores") or {}, platform_avg=score.get("platformAvg", 0), judge_avg_pct=score.get("judgePct", 0), composite=score.get("composite", 0), crs_band=score.get("crsBand")))
            team.status = "building" if team.status == "registered" else team.status
            db.flush()
            return {"ok": True, "brief": self._hackathon_brief_dict(brief), "score": score, "critiques": critiques}

    def log_hackathon_check_in(self, user_id: str, body: Dict[str, Any], activity: float) -> Dict[str, Any]:
        hackathon_id = body.get("hackathonId")
        team_id = body.get("teamId")
        if not self.database_backed:
            check = self._memory_insert("hackathonCheckIns", {"hackathonId": hackathon_id, "teamId": team_id, "note": body.get("note", ""), "progressDelta": _num(body.get("progressDelta"), 10), "activityScore": round(activity)})
            return {"ok": True, "checkIn": check}
        hid = _uuid(hackathon_id)
        tid = _uuid(team_id)
        if hid is None or tid is None:
            return {"ok": False, "error": "invalid_ids"}
        with self._session(write=True) as db:
            check = HackathonCheckIn(id=uuid.uuid4(), team_id=tid, hackathon_id=hid, note=body.get("note", ""), progress_delta=_num(body.get("progressDelta"), 10), activity_score=round(activity))
            db.add(check)
            team = db.get(HackathonTeam, tid)
            if team and team.status == "registered":
                team.status = "building"
            db.flush()
            return {"ok": True, "checkIn": self._hackathon_check_dict(check)}

    def hackathon_team_status(self, hackathon_id: str, team_id: str) -> Optional[Dict[str, Any]]:
        if not self.database_backed:
            team = next((t for t in _MEMORY["hackathonTeams"] if t.get("hackathonId") == hackathon_id and t.get("id") == team_id), None)
            if not team:
                return None
            scores = [s for s in _MEMORY["hackathonScores"] if s.get("teamId") == team_id]
            checks = [c for c in _MEMORY["hackathonCheckIns"] if c.get("teamId") == team_id]
            latest = scores[-1] if scores else {}
            return {"hackathonId": hackathon_id, "teamId": team_id, "name": team.get("name"), "status": team.get("status"), "hasBrief": bool(scores), "composite": _num(latest.get("composite")), "checkIns": len(checks), "hasWorkspace": bool(team.get("workspaceId"))}
        hid = _uuid(hackathon_id)
        tid = _uuid(team_id)
        if hid is None or tid is None:
            return None
        with self._session() as db:
            team = db.query(HackathonTeam).filter(HackathonTeam.id == tid, HackathonTeam.hackathon_id == hid).first()
            if team is None:
                return None
            score = db.query(HackathonScore).filter(HackathonScore.team_id == tid).order_by(HackathonScore.updated_at.desc()).first()
            checks = db.query(func.count(HackathonCheckIn.id)).filter(HackathonCheckIn.team_id == tid).scalar()
            return {"hackathonId": hackathon_id, "teamId": team_id, "name": team.name, "status": team.status, "hasBrief": score is not None, "composite": _num(getattr(score, "composite", 0)), "checkIns": _int(checks), "hasWorkspace": team.workspace_id is not None}

    def provision_hackathon_workspace(self, user_id: str, hackathon_id: str, team_id: str, body: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        project_id = body.get("projectId")
        if not project_id:
            created = self.create_project(user_id, {"title": body.get("projectTitle") or body.get("name") or "Hackathon Team", "origin": {"kind": "hackathon", "hackathonId": hackathon_id, "teamId": team_id}})
            project_id = created.get("project", {}).get("id")
        workspace_result = self.provision_workspace(user_id, {"projectId": project_id, "name": body.get("name", "Hackathon Team")})
        if not workspace_result.get("ok"):
            return None
        if not self.database_backed:
            for team in _MEMORY["hackathonTeams"]:
                if team.get("id") == team_id and team.get("hackathonId") == hackathon_id:
                    team["projectId"] = project_id
                    team["workspaceId"] = workspace_result["workspace"]["id"]
            return {"ok": True, "hackathonId": hackathon_id, "teamId": team_id, "projectId": project_id, **workspace_result}
        tid = _uuid(team_id)
        pid = _uuid(project_id)
        wid = _uuid(workspace_result.get("workspace", {}).get("id"))
        if tid and pid and wid:
            with self._session(write=True) as db:
                team = db.get(HackathonTeam, tid)
                if team:
                    team.project_id = pid
                    team.workspace_id = wid
        return {"ok": True, "hackathonId": hackathon_id, "teamId": team_id, "projectId": project_id, **workspace_result}

    def report_hackathon_team(self, user_id: str, hackathon_id: str, team_id: str, body: Dict[str, Any]) -> Dict[str, Any]:
        report = {"workspaceId": body.get("workspaceId"), "idea": body.get("idea"), "team": body.get("team"), "artifacts": body.get("artifacts"), "stage": body.get("stage"), "reportedBy": user_id}
        if not self.database_backed:
            saved = self._memory_insert("hackathonTeamReports", {"hackathonId": hackathon_id, "teamId": team_id, **report})
            return {"ok": True, "hackathonId": hackathon_id, "teamId": team_id, "report": saved}
        hid = _uuid(hackathon_id)
        tid = _uuid(team_id)
        uid = _uuid(user_id)
        if hid is None or tid is None:
            return {"ok": False, "error": "invalid_ids"}
        with self._session(write=True) as db:
            row = HackathonTeamReport(id=uuid.uuid4(), hackathon_id=hid, team_id=tid, workspace_id=_uuid(body.get("workspaceId")), idea=body.get("idea"), team=body.get("team"), artifacts=body.get("artifacts"), stage=body.get("stage"), reported_by=uid)
            db.add(row)
            db.flush()
            return {"ok": True, "hackathonId": hackathon_id, "teamId": team_id, "report": self._team_report_dict(row)}

    # ------------------------------------------------------------------
    # Private serializers/helpers
    # ------------------------------------------------------------------
    def _project_dict(self, project: Project, has_workspace: bool = False) -> Dict[str, Any]:
        return {
            "id": str(project.id),
            "title": project.title,
            "tagline": project.tagline or "",
            "industry": project.industry or "",
            "stage": _stage_value(project.stage),
            "isPrimary": False,
            "gsisScore": _num(project.gsis_score),
            "hasWorkspace": has_workspace,
            "origin": getattr(project, "origin", None),
            "createdAt": _iso(project.created_at),
            "updatedAt": _iso(project.updated_at),
        }

    def _intake_dict(self, intake: VentureIntake) -> Dict[str, Any]:
        return {"id": str(intake.id), "ownerId": str(intake.owner_id), "status": intake.status, "submission": intake.submission, "structuredProfile": intake.structured_profile, "promotedProjectId": _str_id(intake.promoted_project_id), "createdAt": _iso(intake.created_at), "updatedAt": _iso(intake.updated_at)}

    def _workspace_dict(self, workspace: Workspace) -> Dict[str, Any]:
        return {"id": str(workspace.id), "projectId": str(workspace.project_id), "name": workspace.name, "status": workspace.status, "seededFromAnalysis": workspace.seed_analysis_id is not None, "seedAnalysisId": _str_id(workspace.seed_analysis_id), "createdAt": _iso(workspace.created_at), "updatedAt": _iso(workspace.updated_at)}

    def _equity_holdings(self, user_id: str) -> List[Dict[str, Any]]:
        if not self.database_backed:
            return _sort_newest([deepcopy(h) for h in _MEMORY["equityGrants"] if h.get("userId") == user_id or h.get("collaboratorId") == user_id])
        uid = _uuid(user_id)
        if uid is None:
            return []
        with self._session() as db:
            grants = db.query(EquityGrant).filter(EquityGrant.user_id == uid).order_by(EquityGrant.created_at.desc()).all()
            project_ids = [grant.project_id for grant in grants]
            projects = {str(p.id): p for p in db.query(Project).filter(Project.id.in_(project_ids)).all()} if project_ids else {}
            caps = db.query(CapTableEntry).filter(CapTableEntry.project_id.in_(project_ids)).order_by(CapTableEntry.sort_order.asc()).all() if project_ids else []
            caps_by_project: Dict[str, List[CapTableEntry]] = {}
            for cap in caps:
                caps_by_project.setdefault(str(cap.project_id), []).append(cap)
            return [self._grant_dict(grant, projects.get(str(grant.project_id)), caps_by_project.get(str(grant.project_id), [])) for grant in grants]

    def _grant_dict(self, grant: EquityGrant, project: Optional[Project], caps: List[CapTableEntry]) -> Dict[str, Any]:
        return {
            "projectId": str(grant.project_id),
            "projectName": project.title if project else str(grant.project_id),
            "projectLogo": "",
            "equityPercent": _num(grant.equity_percent),
            "valueUSD": _num(grant.value_usd),
            "vestedPercent": _num(grant.vested_percent),
            "vestingSchedule": {"years": _int(grant.vesting_years, 4), "cliffMonths": _int(grant.vesting_cliff_months, 12)},
            "grantDate": _iso(grant.grant_date)[:10] if _iso(grant.grant_date) else "",
            "nextVest": {"date": _iso(grant.next_vest_date)[:10], "deltaPercent": _num(grant.next_vest_delta_percent)} if grant.next_vest_date else None,
            "dilutionProtected": bool(grant.dilution_protected),
            "capTable": [{"label": cap.label, "percent": _num(cap.percent), "highlighted": cap.holder_user_id == grant.user_id} for cap in caps],
        }

    def _equity_totals(self, holdings: List[Dict[str, Any]]) -> Dict[str, Any]:
        total_value = sum(_num(h.get("valueUSD")) for h in holdings)
        blended = sum(_num(h.get("equityPercent")) for h in holdings)
        vested_q = sum(_num(h.get("valueUSD")) * (_num(h.get("vestedPercent")) / 100) * 0.25 for h in holdings)
        upcoming = sorted([h for h in holdings if h.get("nextVest")], key=lambda h: h["nextVest"]["date"])
        next_vest = {"startup": upcoming[0].get("projectName"), "date": upcoming[0]["nextVest"]["date"], "deltaPercent": upcoming[0]["nextVest"]["deltaPercent"]} if upcoming else None
        return {"totalValueUSD": round(total_value, 2), "blendedEquityPercent": round(blended, 4), "vestedThisQuarterUSD": round(vested_q, 2), "nextVest": next_vest}

    def _vesting_series(self, holding: Dict[str, Any]) -> Dict[str, Any]:
        schedule = holding.get("vestingSchedule") or {}
        total_months = max(1, _int(schedule.get("years"), 4) * 12)
        cliff = _int(schedule.get("cliffMonths"), 12)
        try:
            base = datetime.fromisoformat(str(holding.get("grantDate"))[:10])
        except ValueError:
            base = _now()
        points = []
        for i in range(total_months):
            month = base.month - 1 + i
            year = base.year + month // 12
            mm = month % 12 + 1
            vested = 0 if i < cliff else min(100, round((i / total_months) * 100))
            points.append({"monthIso": f"{year:04d}-{mm:02d}", "vestedPercent": vested})
        return {"projectId": holding.get("projectId"), "projectName": holding.get("projectName"), "points": points}

    def _earnings_and_payouts(self, user_id: str) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        if not self.database_backed:
            earnings = _sort_newest([deepcopy(e) for e in _MEMORY["collaboratorEarnings"] if e.get("userId") == user_id or e.get("collaboratorId") == user_id])
            payouts = _sort_newest([deepcopy(p) for p in _MEMORY["payouts"] if p.get("userId") == user_id or p.get("collaboratorId") == user_id])
            return earnings, payouts
        uid = _uuid(user_id)
        if uid is None:
            return [], []
        with self._session() as db:
            rows = db.query(CollaboratorEarning).filter(CollaboratorEarning.user_id == uid).all()
            project_ids = [row.project_id for row in rows]
            projects = {str(p.id): p for p in db.query(Project).filter(Project.id.in_(project_ids)).all()} if project_ids else {}
            payouts = db.query(Payout).filter(Payout.user_id == uid).order_by(Payout.initiated_at.desc()).all()
            return [self._earning_dict(row, projects.get(str(row.project_id))) for row in rows], [self._payout_dict(row) for row in payouts]

    def _earning_dict(self, row: CollaboratorEarning, project: Optional[Project]) -> Dict[str, Any]:
        return {"projectId": str(row.project_id), "projectName": project.title if project else str(row.project_id), "earned": _num(row.earned_usd), "pending": _num(row.pending_usd), "revenueSharePercent": _num(row.revenue_share_percent), "contributionNote": row.contribution_note or ""}

    def _payout_dict(self, row: Payout) -> Dict[str, Any]:
        return {"id": str(row.id), "monthIso": row.month_iso, "amount": _num(row.amount_usd), "status": row.status, "destination": row.destination, "initiatedAt": _iso(row.initiated_at), "settledAt": _iso(row.settled_at)}

    def _cash_totals(self, earnings: List[Dict[str, Any]], payouts: List[Dict[str, Any]]) -> Dict[str, Any]:
        return {"lifetimeUSD": round(sum(_num(e.get("earned")) for e in earnings), 2), "pendingUSD": round(sum(_num(e.get("pending")) for e in earnings), 2), "revenueShareTTMUsd": round(sum(_num(p.get("amount")) for p in payouts[:12]) * 0.1, 2)}

    def _pool_dict(self, row: CapitalPool) -> Dict[str, Any]:
        return {"id": str(row.id), "name": row.name, "totalCapital": _num(row.total_capital_usd), "deployed": _num(row.deployed_usd), "startups": _int(row.startups_count), "milestonesHit": _int(row.milestones_hit), "fundsReleased": _num(row.funds_released_usd), "roiSimulation": _num(row.roi_simulation), "rules": {"minReadiness": _int(row.min_readiness), "maxPerStartup": _num(row.max_per_startup_percent), "milestoneTrigger": bool(row.milestone_trigger)}, "status": row.status}

    def _deal_meta(self, row: DealRoom) -> Dict[str, Any]:
        return {"id": str(row.id), "projectId": str(row.project_id), "status": row.status, "stage": row.stage, "daysOpen": _int(row.days_open), "messages": _int(row.messages), "docs": _int(row.docs), "lastActivity": row.last_activity or ""}

    def _term_sheet_dict(self, row: TermSheet) -> Dict[str, Any]:
        return {"id": str(row.id), "valuationUSD": _num(row.valuation_usd), "investmentUSD": _num(row.investment_usd), "equityPercent": _num(row.equity_percent), "instrument": row.instrument, "discountPercent": _num(row.discount_percent), "valuationCapUSD": _num(row.valuation_cap_usd), "extraTerms": row.extra_terms or {}}

    def _deal_document_dict(self, row: DealDocument) -> Dict[str, Any]:
        return {"id": str(row.id), "name": row.name, "status": row.status, "signedBy": _str_id(row.signed_by), "signedAt": _iso(row.signed_at), "createdAt": _iso(row.created_at)}

    def _data_room_dict(self, row: DataRoom) -> Dict[str, Any]:
        return {"id": str(row.id), "projectId": str(row.project_id), "sections": row.sections or DataRoomServiceSections, "docCount": _int(row.doc_count), "complianceVerified": bool(row.compliance_verified), "aiGovernanceVerified": bool(row.ai_governance_verified), "updatedLabel": row.updated_label or ""}

    def _data_rooms_payload(self, rooms: List[Dict[str, Any]], sections: List[str]) -> Dict[str, Any]:
        verified = sum(1 for room in rooms if room.get("complianceVerified"))
        return {"rooms": rooms, "sections": sections, "totals": {"activeRooms": len(rooms), "totalDocs": sum(_int(r.get("docCount")) for r in rooms), "complianceVerified": verified, "aiSummaries": len(rooms)}}

    def _reputation_dict(self, row: InvestorReputation) -> Dict[str, Any]:
        return {"score": _int(row.composite_score), "monthChange": _int(row.month_change), "metrics": [{"key": "responseSpeed", "label": "Response Speed", "score": _int(row.response_speed)}, {"key": "founderRating", "label": "Founder Rating", "score": _int(row.founder_rating)}, {"key": "followThrough", "label": "Follow-Through Consistency", "score": _int(row.follow_through)}, {"key": "valueAdd", "label": "Value-Add Contributions", "score": _int(row.value_add)}, {"key": "portfolioEngagement", "label": "Portfolio Engagement", "score": _int(row.portfolio_engagement)}], "leaderboard": {"rank": row.rank, "total": row.total_investors, "percentile": _num(row.percentile)}}

    def _review_dict(self, row: InvestorReview) -> Dict[str, Any]:
        return {"founderName": row.founder_name or "", "startup": row.startup or "", "rating": _int(row.rating), "comment": row.comment or "", "date": _iso(row.review_date)}

    def _reputation_payload(self, rep: Optional[Dict[str, Any]], reviews: List[Dict[str, Any]]) -> Dict[str, Any]:
        score = _int((rep or {}).get("score"))
        level = "Elite" if score >= 85 else "Established" if score >= 70 else "Building"
        return {"score": score, "level": level, "monthChange": _int((rep or {}).get("monthChange")), "metrics": (rep or {}).get("metrics", []), "reviews": reviews, "progression": [], "leaderboard": (rep or {}).get("leaderboard", {"rank": None, "total": None, "percentile": None})}

    def _feed_post_dict(self, row: FeedPost) -> Dict[str, Any]:
        return {"id": str(row.id), "authorId": str(row.author_id), "projectId": _str_id(row.project_id), "postType": row.post_type, "content": row.content, "tags": row.tags or [], "aiRelevanceScore": _num(row.ai_relevance_score), "likesCount": _int(row.likes_count), "commentsCount": _int(row.comments_count), "trustWeight": _num(row.trust_weight, 1), "isPinned": bool(row.is_pinned), "createdAt": _iso(row.created_at)}

    def _hackathon_dict(self, row: Hackathon, db: Any) -> Dict[str, Any]:
        teams = db.query(HackathonTeam).filter(HackathonTeam.hackathon_id == row.id).all()
        return {"id": str(row.id), "name": row.name, "theme": row.theme or "", "status": row.status, "registrants": sum(len(team.members or []) for team in teams), "teamsFormed": sum(1 for team in teams if not team.is_solo), "createdAt": _iso(row.created_at)}

    def _hackathon_team_dict(self, row: HackathonTeam) -> Dict[str, Any]:
        return {"id": str(row.id), "hackathonId": str(row.hackathon_id), "name": row.name, "members": row.members or [], "isSolo": bool(row.is_solo), "status": row.status, "projectId": _str_id(row.project_id), "workspaceId": _str_id(row.workspace_id)}

    def _hackathon_brief_dict(self, row: HackathonBrief) -> Dict[str, Any]:
        return {"id": str(row.id), "teamId": str(row.team_id), "hackathonId": str(row.hackathon_id), "problem": row.problem or "", "solution": row.solution or "", "fields": row.fields or {}, "composite": _num(row.composite_score), "critiques": row.critiques or [], "submittedAt": _iso(row.submitted_at)}

    def _hackathon_check_dict(self, row: HackathonCheckIn) -> Dict[str, Any]:
        return {"id": str(row.id), "teamId": str(row.team_id), "hackathonId": str(row.hackathon_id), "note": row.note or "", "progressDelta": _num(row.progress_delta), "activityScore": _num(row.activity_score), "createdAt": _iso(row.created_at)}

    def _team_report_dict(self, row: HackathonTeamReport) -> Dict[str, Any]:
        return {"id": str(row.id), "workspaceId": _str_id(row.workspace_id), "idea": row.idea, "team": row.team, "artifacts": row.artifacts, "stage": row.stage, "reportedBy": _str_id(row.reported_by), "createdAt": _iso(row.created_at)}

    def _hackathon_velocity_db(self, db: Any, hackathon_id: uuid.UUID, teams: List[HackathonTeam]) -> List[Dict[str, Any]]:
        checks = db.query(HackathonCheckIn).filter(HackathonCheckIn.hackathon_id == hackathon_id).all()
        by_team: Dict[str, List[HackathonCheckIn]] = {}
        for check in checks:
            by_team.setdefault(str(check.team_id), []).append(check)
        cells = []
        for team in teams:
            team_checks = by_team.get(str(team.id), [])
            activity = round(sum(_num(c.activity_score) for c in team_checks) / len(team_checks), 1) if team_checks else 0
            cells.append({"teamId": str(team.id), "name": team.name, "activity": activity})
        return cells

    def _rank_projects(self, projects: List[Dict[str, Any]], watchlist: set[str]) -> List[Dict[str, Any]]:
        ranked = []
        for project in projects:
            item = deepcopy(project)
            item["watchlisted"] = str(project.get("id")) in watchlist
            item["rankScore"] = _num(project.get("gsisScore")) + _num(project.get("eviI")) * 0.4
            ranked.append(item)
        ranked.sort(key=lambda row: row.get("rankScore", 0), reverse=True)
        return ranked

    def _ranking_formula(self) -> Dict[str, Any]:
        return {
            "gsis_weights": {
                "product_progress": "15%",
                "execution_velocity": "15%",
                "market_readiness": "20%",
                "beta_satisfaction": "10%",
                "revenue_growth": "10%",
                "founder_reputation": "10%",
                "community_influence": "5%",
                "investor_interest": "10%",
                "compliance": "5%",
            },
            "evi_i_signal": "6-dimensional investor execution signal",
            "decay_anti_gaming": "e^(-0.02*d)",
        }

    def _sector_rows(self, projects: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        buckets: Dict[str, List[float]] = {}
        for project in projects:
            buckets.setdefault(project.get("industry") or "Unspecified", []).append(_num(project.get("marketReadinessScore") or project.get("gsisScore")))
        return [{"sector": sector, "avgGrowth": round(sum(values) / len(values), 2), "startupCount": len(values)} for sector, values in buckets.items()]


DataRoomServiceSections = [
    "Metrics Dashboard",
    "Financials",
    "Testing Reports",
    "Compliance",
    "Governance",
    "Execution History",
]
