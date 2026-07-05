
"""
TECHIT AI INCUBATION PLATFORM
==============================
# main.py - FastAPI Application Entry Point

This is the file uvicorn looks for: uvicorn main:app
It wires every service from integration_guide.py to HTTP endpoints.

Start (dev):
    uvicorn main:app --reload --host 0.0.0.0 --port 8000

Start (production, via Docker):
    uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
"""

from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
from typing import Optional, Dict, Any, List
import os
import structlog
from sqlalchemy import text

from integration_guide import (
    TechITAIBrain,
    IncubationHubService,
    DashboardIntelligenceService,
    WorkspaceAIService,
    TourGuideService,
    AdaptiveTrainingService,
    MatchingEngineService,
    RiskEvaluatorService,
    InvestorSectionService,
    FeedIntelligenceService,
    AIProfileService,
    OrgSphereService,
    MarketReadinessService,
    AdminMonitorService,
    HybridBillingService,
    GSISService,
    IdeaSolutionHubService,
    DocumentGenerationService,
    IPProtectionService,
    AppScaffoldService,
    TrustVerificationService,
    EquityService,
    PayoutService,
    CapitalPoolService,
    DealRoomService,
    DataRoomService,
    InvestorReputationService,
    GeoSignalService,
    ProjectService,
    WorkspaceService,
    HackathonService,
)
from ai_router_core import UserContext, UserRole, SubscriptionTier
from credit_ledger import SQLAlchemySessionFactoryCreditLedger
from runtime_config import (
    PROD_ENVS,
    RuntimeCheck,
    RuntimeConfigError,
    assert_runtime_ready,
    runtime_checks,
)

logger = structlog.get_logger()

# Global AI brain -- initialised once at startup, shared across all requests
brain: Optional[TechITAIBrain] = None


# ============================================================================
# LIFESPAN -- STARTUP & SHUTDOWN
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Initialise the TechIT AI brain on startup.
    All 34 agents are registered at this point.
    # Nothing else should call TechITAIBrain() -- it's a singleton.
    """
    global brain
    if ENVIRONMENT in PROD_ENVS:
        try:
            assert_runtime_ready()
        except RuntimeConfigError as exc:
            logger.error("runtime_config_invalid", error=str(exc))
            raise

    brain = TechITAIBrain()
    if ENVIRONMENT in PROD_ENVS:
        brain.command_layer.credit_ledger = SQLAlchemySessionFactoryCreditLedger(
            _db_session_factory()
        )
    logger.info(
        "techit_ai_brain_ready",
        agents=34,
        task_types=51,
        scoring_models=20,
        db_tables=42,
        version="3.0.0",
    )
    yield
    logger.info("techit_shutdown")


# ============================================================================
# APP CONFIGURATION
# ============================================================================

app = FastAPI(
    title="TechIT AI Incubation Platform",
    version="3.0.0",
    description=(
        "The execution intelligence layer for the global startup ecosystem. "
        "34 AI agents * 51 task types * 20 scoring models * Prompt -> Live App."
    ),
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# Compression for all responses > 500 bytes
app.add_middleware(GZipMiddleware, minimum_size=500)

# CORS -- restrict in production via ALLOWED_ORIGINS env var
ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:3000,http://localhost:8000",
).split(",")

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============================================================================
# AUTHENTICATION DEPENDENCY
# ============================================================================

# Auth config (env-driven).
#   JWT_SECRET       -- HS256 signing key shared with the token issuer (BACKEND repo,
#                       both Node main and Go feat/messaging-backend). Canonical name
#                       across all platform services as of 2026-06-20.
#   SECRET_KEY       -- legacy alias for JWT_SECRET. Honored as a fallback so existing
#                       ai-router deployments keep booting; new deployments should set
#                       JWT_SECRET instead.
#   JWT_ALGORITHM    -- defaults to HS256.
#   ALLOW_DEMO_AUTH  -- when true (default) requests WITHOUT a token fall back to the
#                       demo context so local dev keeps working. Forbidden when
#                       ENVIRONMENT is "production" or "staging" (see startup guard
#                       below). A request WITH a token is ALWAYS validated.
#   ENVIRONMENT      -- "development" | "staging" | "production". Drives the demo-auth
#                       guardrail.
SECRET_KEY = os.getenv("JWT_SECRET") or os.getenv("SECRET_KEY")
JWT_ALGORITHM = os.getenv("JWT_ALGORITHM", "HS256")
ALLOW_DEMO_AUTH = os.getenv("ALLOW_DEMO_AUTH", "true").lower() in ("1", "true", "yes")
ENVIRONMENT = os.getenv("ENVIRONMENT", "development").strip().lower()

# Startup guardrails are enforced in lifespan via runtime_config.assert_runtime_ready.

# Tolerant aliases so tokens minted by the Node backend map onto our enums.
_ROLE_ALIASES = {
    "founder": UserRole.FOUNDER,
    "collaborator": UserRole.BUILDER,
    "builder": UserRole.BUILDER,
    "investor": UserRole.INVESTOR,
    "organisation": UserRole.ACCELERATOR_MGR,
    "organization": UserRole.ACCELERATOR_MGR,
    "accelerator_manager": UserRole.ACCELERATOR_MGR,
    "admin": UserRole.ADMIN,
}


def _role_from_claim(value: Any) -> UserRole:
    if isinstance(value, str):
        return _ROLE_ALIASES.get(value.strip().lower(), UserRole.FOUNDER)
    return UserRole.FOUNDER


def _tier_from_claim(value: Any) -> SubscriptionTier:
    if isinstance(value, str):
        try:
            return SubscriptionTier(value.strip().lower())
        except ValueError:
            pass
    return SubscriptionTier.FREE


def _demo_user_context() -> UserContext:
    """Demo Founder Pro context for local dev / anonymous requests (ALLOW_DEMO_AUTH)."""
    return UserContext(
        user_id="demo_user_001",
        role=UserRole.FOUNDER,
        subscription_tier=SubscriptionTier.FOUNDER_PRO,
        credits_remaining=150,
        project_id="proj_demo_001",
        project_stage="idea",
        industry="edtech",
        tech_stack=["React", "Node.js", "PostgreSQL"],
        past_feedback=[],
        training_progress={"completion_percentage": 0},
        time_logged_today=45,
        tasks_completed_week=3,
        days_since_update=0,
        team_size=2,
        has_revenue=False,
        beta_users_count=0,
    )


def _context_from_claim(user_id: str, payload: Dict[str, Any]) -> UserContext:
    """Build a UserContext purely from JWT claims. Used as the source for
    non-security-critical fields, and as the fallback when DB lookup misses
    (newly-issued token, demo mode, DB unreachable)."""
    def _int(key: str, default: int) -> int:
        try:
            return int(payload.get(key, default))
        except (TypeError, ValueError):
            return default

    return UserContext(
        user_id=str(user_id),
        role=_role_from_claim(payload.get("role")),
        subscription_tier=_tier_from_claim(
            payload.get("subscription_tier") or payload.get("tier")
        ),
        credits_remaining=_int("credits_remaining", _int("credits", 0)),
        project_id=payload.get("project_id"),
        project_stage=payload.get("project_stage"),
        industry=payload.get("industry"),
        tech_stack=payload.get("tech_stack") or [],
        past_feedback=[],
        training_progress=payload.get("training_progress") or {"completion_percentage": 0},
        time_logged_today=_int("time_logged_today", 0),
        tasks_completed_week=_int("tasks_completed_week", 0),
        days_since_update=_int("days_since_update", 0),
        team_size=_int("team_size", 1),
        has_revenue=bool(payload.get("has_revenue", False)),
        beta_users_count=_int("beta_users_count", 0),
    )


def _hydrate_from_db(ctx: UserContext, db) -> UserContext:
    """Override security-critical fields (role, subscription_tier,
    credits_remaining) with DB values. Identity (user_id) and incidental
    fields (project, industry, etc.) stay from claim — a forged claim
    inflating `credits_remaining` cannot bypass the paywall because the DB
    is authoritative for usage state.

    DB unavailable or user not found → return ctx unchanged. The warning
    log surfaces ops issues without blocking auth."""
    from dataclasses import replace as dc_replace

    try:
        from database_schema import User as UserRow
        from sqlalchemy import select
        row = db.execute(
            select(UserRow).where(UserRow.id == ctx.user_id)
        ).scalar_one_or_none()
    except Exception as exc:  # noqa: BLE001
        logger.warning("user_db_hydrate_failed", user_id=ctx.user_id, error=str(exc))
        return ctx

    if row is None:
        return ctx

    def _enum_str(v: Any) -> str:
        return v.value if hasattr(v, "value") else str(v)

    return dc_replace(
        ctx,
        role=_role_from_claim(_enum_str(row.role)),
        subscription_tier=_tier_from_claim(_enum_str(row.subscription_tier)),
        credits_remaining=int(
            (row.subscription_credits_remaining or 0) + (row.payg_credits_balance or 0)
        ),
    )


async def get_user_context(request: Request) -> UserContext:
    """
    Extract and validate the current user from the request.

      1. Read Authorization header -> "Bearer <jwt_token>"
      2. Decode + verify the JWT (HS256) with SECRET_KEY (python-jose)
      3. Build a UserContext from claims
      4. Override role + subscription_tier + credits_remaining with DB values
         keyed by `sub` (closes ai-router #13) — a forged claim cannot bypass
         the paywall because the DB owns operational state.
      2. Decode + verify the JWT (HS256) with JWT_SECRET (python-jose).
         Uses SECRET_KEY only if JWT_SECRET is unset (legacy alias).
      3. Build a UserContext from the token claims

    A request WITH a token is always validated (401 on missing/invalid).
    A request WITHOUT a token falls back to the demo context only when
    ALLOW_DEMO_AUTH is enabled (forbidden in staging/production by C3 guard).
    """
    auth_header = request.headers.get("Authorization", "")
    token = auth_header[7:].strip() if auth_header[:7].lower() == "bearer " else ""

    if not token:
        if ALLOW_DEMO_AUTH:
            logger.warning("auth_demo_fallback", reason="no_token")
            return _demo_user_context()
        raise HTTPException(status_code=401, detail="Missing authentication token")

    if not SECRET_KEY:
        # A token was supplied but the server can't verify it.
        logger.error("auth_misconfigured", reason="JWT_SECRET/SECRET_KEY not set")
        raise HTTPException(status_code=500, detail="Authentication is not configured")

    try:
        from jose import JWTError, jwt
        payload = jwt.decode(token, SECRET_KEY, algorithms=[JWT_ALGORITHM])
    except JWTError as exc:
        logger.warning("auth_jwt_invalid", reason="decode_failed", error=str(exc))
        raise HTTPException(status_code=401, detail="Invalid or expired token")

    user_id = payload.get("sub") or payload.get("user_id")
    if not user_id:
        logger.warning("auth_jwt_invalid", reason="missing_subject_claim")
        raise HTTPException(status_code=401, detail="Token missing subject claim")

    ctx = _context_from_claim(str(user_id), payload)

    # Hydrate from DB. We resolve the session lazily here (instead of via
    # FastAPI Depends) so endpoints that use get_user_context don't have to
    # change their signatures — the dependency surface stays the same.
    try:
        Session = _db_session_factory()
        session = Session()
        try:
            ctx = _hydrate_from_db(ctx, session)
        finally:
            session.close()
    except Exception as exc:  # noqa: BLE001
        logger.warning("user_db_session_unavailable", user_id=str(user_id), error=str(exc))

    return ctx


# ============================================================================
# DATABASE DEPENDENCY
# ============================================================================

# Lazily-created engine + session factory (shared across requests). The engine
# is only constructed on first DB use so the app still imports without a DB.
_db_engine = None
_DBSession = None


def _db_session_factory():
    global _db_engine, _DBSession
    if _DBSession is None:
        from sqlalchemy import create_engine
        from sqlalchemy.orm import sessionmaker

        _db_engine = create_engine(
            os.getenv("DATABASE_URL", "postgresql://techit:password@postgres:5432/techit_db"),
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=5,
        )
        _DBSession = sessionmaker(bind=_db_engine, expire_on_commit=False)
    return _DBSession


def get_db():
    """FastAPI dependency yielding a SQLAlchemy session (closed after the request)."""
    Session = _db_session_factory()
    db = Session()
    try:
        yield db
    finally:
        db.close()


# ============================================================================
# HEALTH & STATUS
# ============================================================================

@app.get("/health", tags=["Status"])
async def health():
    """Liveness check. Does not prove dependencies are ready."""
    return {
        "status":         "healthy",
        "ai_brain":       "operational",
        "version":        "3.0.0",
        "agents":         34,
        "task_types":     51,
        "scoring_models": 20,
        "db_tables":      42,
    }


@app.get("/ready", tags=["Status"])
async def ready():
    """Readiness check for runtime config and dependency reachability."""
    checks = runtime_checks()

    db_ok = True
    db_detail = "ok"
    try:
        Session = _db_session_factory()
        session = Session()
        try:
            session.execute(text("SELECT 1"))
        finally:
            session.close()
    except Exception as exc:  # noqa: BLE001
        db_ok = False
        db_detail = str(exc)

    checks.append(RuntimeCheck("database.ping", db_ok, db_detail))
    ok = all(check.ok for check in checks)
    body = {
        "status": "ready" if ok else "not_ready",
        "checks": [
            {"name": check.name, "ok": check.ok, "detail": check.detail}
            for check in checks
        ],
    }
    if not ok:
        return JSONResponse(status_code=503, content=body)
    return body


@app.get("/", tags=["Status"])
async def root():
    return {
        "platform": "TechIT AI Incubation Platform",
        "version":  "3.0.0",
        "docs":     "/docs",
        "health":   "/health",
        "tagline":  "Idea -> Score -> Build -> Deploy -> Track -> Raise. All here. All AI-native.",
    }


# ============================================================================
# INCUBATION HUB
# ============================================================================

@app.post("/api/v1/incubation/pipeline/run", tags=["Incubation Hub"])
async def run_pipeline(
    venture_data: Dict[str, Any],
    user: UserContext = Depends(get_user_context),
):
    """
    Run the full 10-agent venture pipeline.
    Intake -> Unicorn -> Market -> Feasibility -> Strategy -> Finance ->
    BusinessPlan -> TechArch -> InvestorIntel -> AppScaffold

    Cost: 12 credits. Min tier: Investor+
    """
    return await IncubationHubService(brain).run_full_venture_pipeline(user, venture_data)


@app.post("/api/v1/incubation/idea/diagnose", tags=["Incubation Hub"])
async def diagnose_idea(
    idea_data: Dict[str, Any],
    user: UserContext = Depends(get_user_context),
):
    """Quick idea diagnostic -- 1 credit, Free+"""
    return await IncubationHubService(brain).run_idea_diagnostic(user, idea_data)


@app.post("/api/v1/incubation/unicorn/analyze", tags=["Incubation Hub"])
async def unicorn_analyze(
    venture_data: Dict[str, Any],
    user: UserContext = Depends(get_user_context),
):
    """10-driver Unicorn Potential Score -- 2 credits, Builder+"""
    return await IncubationHubService(brain).run_unicorn_analysis(user, venture_data)


@app.post("/api/v1/incubation/market/analyze", tags=["Incubation Hub"])
async def market_analyze(
    venture_data: Dict[str, Any],
    user: UserContext = Depends(get_user_context),
):
    """TAM/SAM/SOM + competitive landscape -- 2 credits, Builder+"""
    return await IncubationHubService(brain).run_market_intelligence(user, venture_data)


@app.post("/api/v1/incubation/strategy/generate", tags=["Incubation Hub"])
async def generate_strategy(
    venture_data: Dict[str, Any],
    user: UserContext = Depends(get_user_context),
):
    """GTM, pricing, growth strategy -- 3 credits, Founder Pro+"""
    return await IncubationHubService(brain).run_startup_strategy(user, venture_data)


@app.post("/api/v1/incubation/business-plan/generate", tags=["Incubation Hub"])
async def generate_business_plan(
    venture_data: Dict[str, Any],
    user: UserContext = Depends(get_user_context),
):
    """Executive summary + 10-section business plan -- 6 credits, Investor+"""
    return await IncubationHubService(brain).generate_business_plan(user, venture_data)


@app.post("/api/v1/incubation/pivot/analyze", tags=["Incubation Hub"])
async def pivot_analyze(
    data: Dict[str, Any],
    user: UserContext = Depends(get_user_context),
):
    """Pivot intelligence -- when to pivot and where -- 2 credits, Builder+"""
    return await IncubationHubService(brain).run_pivot_intelligence(
        user,
        data.get("venture_data", {}),
        data.get("unicorn_score", 0),
    )


@app.post("/api/v1/incubation/investor-readiness/generate", tags=["Incubation Hub"])
async def investor_readiness(
    venture_data: Dict[str, Any],
    user: UserContext = Depends(get_user_context),
):
    """Investor readiness report -- 2 credits, Investor+"""
    return await IncubationHubService(brain).generate_investor_readiness_report(
        user, venture_data
    )


# ============================================================================
# PROMPT -> LIVE APP  (App Scaffold Engine)
# ============================================================================

@app.post("/api/v1/scaffold/generate", tags=["Prompt -> Live App"])
async def generate_scaffold(
    body: Dict[str, Any],
    user: UserContext = Depends(get_user_context),
):
    """
    Generate a complete application scaffold from the venture profile.
  
    5 credits. Founder Pro+

    Body params:
      project_id    (required) str
      stack_choice  (optional) str  -- nextjs_supabase | nextjs_prisma |
                                      react_firebase | expo_supabase | fastapi_supabase
      venture_data  (optional) dict -- uses pipeline output if omitted
    """
    return await AppScaffoldService(brain).generate_scaffold(
        user_context=user,
        project_id=body.get("project_id", user.project_id or "proj_001"),
        stack_choice=body.get("stack_choice", "nextjs_supabase"),
        venture_data=body.get("venture_data"),
        arch_data=body.get("arch_data"),
    )


@app.post("/api/v1/scaffold/{scaffold_id}/deploy", tags=["Prompt -> Live App"])
async def deploy_scaffold(
    scaffold_id: str,
    body: Dict[str, Any],
    user: UserContext = Depends(get_user_context),
):
    """
    Trigger 1-click Vercel deployment of a generated scaffold.
    3 credits. Founder Pro+
    Returns: deploy_status, live_url, build_logs_url, estimated_ready_seconds
    """
    return await AppScaffoldService(brain).deploy_scaffold(
        user_context=user,
        scaffold_id=scaffold_id,
        deploy_target=body.get("deploy_target", "vercel"),
    )


@app.get("/api/v1/scaffold/{scaffold_id}/status", tags=["Prompt -> Live App"])
async def scaffold_status(
    scaffold_id: str,
    user: UserContext = Depends(get_user_context),
):
    """Poll deployment status. 0 credits, Free+"""
    return AppScaffoldService(brain).get_deploy_status(scaffold_id)


@app.get("/api/v1/scaffold/{scaffold_id}/live-url", tags=["Prompt -> Live App"])
async def scaffold_live_url(
    scaffold_id: str,
    user: UserContext = Depends(get_user_context),
):
    """Get live URL after deployment. 0 credits, Free+"""
    return AppScaffoldService(brain).get_live_url(scaffold_id)


@app.get("/api/v1/scaffold/{project_id}", tags=["Prompt -> Live App"])
async def get_scaffold(
    project_id: str,
    user: UserContext = Depends(get_user_context),
):
    """Retrieve scaffold for a project. 0 credits, Free+"""
    # Production: SELECT * FROM app_scaffolds WHERE project_id = :project_id
    return {
        "project_id": project_id,
        "message": "Scaffold retrieval -- query app_scaffolds table",
        "endpoint": f"/api/v1/scaffold/{project_id}",
    }


@app.get("/api/v1/scaffold/stacks", tags=["Prompt -> Live App"])
async def get_stacks(user: UserContext = Depends(get_user_context)):
    """List all supported stacks with credit costs and deploy times. 0 credits, Free+"""
    return AppScaffoldService(brain).get_available_stacks()


# ============================================================================
# DASHBOARD
# ============================================================================

@app.get("/api/v1/dashboard/intelligence", tags=["Dashboard"])
async def dashboard_intelligence(user: UserContext = Depends(get_user_context)):
    """Real-time GSIS + EVI-I + decay signals for the dashboard. 0 credits."""
    return await DashboardIntelligenceService(brain).get_dashboard_intelligence(user)


@app.post("/api/v1/gsis/compute", tags=["Dashboard"])
async def compute_gsis(
    scores: Dict[str, Any],
    user: UserContext = Depends(get_user_context),
):
    """Compute GSIS from component scores. 1 credit, Free+"""
    return await GSISService(brain).compute_with_narrative(user, scores)


# ============================================================================
# TRUST ENGINE LITE
# ============================================================================

@app.get("/api/v1/trust/profile", tags=["Trust Engine"])
async def trust_profile(
    user: UserContext = Depends(get_user_context),
    db=Depends(get_db),
):
    """Current metadata-only trust profile. 0 credits, Free+."""
    return TrustVerificationService(brain).get_profile(user, db)


@app.get("/api/v1/trust/badges", tags=["Trust Engine"])
async def trust_badges(
    user: UserContext = Depends(get_user_context),
    db=Depends(get_db),
):
    """Derived expiring trust badges. 0 credits, Free+."""
    return TrustVerificationService(brain).get_badges(user, db)


@app.get("/api/v1/trust/history", tags=["Trust Engine"])
async def trust_history(
    limit: int = 50,
    user: UserContext = Depends(get_user_context),
    db=Depends(get_db),
):
    """Append-only verification history. 0 credits, Free+."""
    return TrustVerificationService(brain).get_history(user, db, limit)


@app.post("/api/v1/trust/share-profile/preview", tags=["Trust Engine"])
async def trust_share_profile_preview(
    body: Dict[str, Any],
    user: UserContext = Depends(get_user_context),
    db=Depends(get_db),
):
    """Build an investor-safe Trust Profile preview after explicit founder opt-in. 0 credits, Free+."""
    return TrustVerificationService(brain).build_share_profile(user, body, db)


@app.get("/api/v1/trust/integrations", tags=["Trust Engine"])
async def trust_integrations(
    provider: Optional[str] = None,
    user: UserContext = Depends(get_user_context),
):
    """Provider integration manifests with permissions and metadata-only storage policy. 0 credits, Free+."""
    try:
        return TrustVerificationService(brain).get_integration_manifests(provider)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/v1/trust/verify/{source}", tags=["Trust Engine"])
async def trust_verify_source(
    source: str,
    body: Dict[str, Any],
    user: UserContext = Depends(get_user_context),
    db=Depends(get_db),
):
    """
    Submit metadata-only verification result for a source. 1 credit, Free+.

    This endpoint accepts provider adapter metadata only; it never accepts or
    stores raw provider payloads, OAuth tokens, source code, analytics events,
    contact lists, or document blobs.
    """
    try:
        return TrustVerificationService(brain).verify_source(user, source, body, db)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/v1/trust/adapters/{provider}/verify", tags=["Trust Engine"])
async def trust_verify_adapter_payload(
    provider: str,
    body: Dict[str, Any],
    user: UserContext = Depends(get_user_context),
    db=Depends(get_db),
):
    """Normalize provider metadata through a privacy adapter, then append a Trust verification row. 1 credit, Free+."""
    try:
        return TrustVerificationService(brain).verify_adapter_payload(user, provider, body, db)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/v1/trust/disconnect/{source}", tags=["Trust Engine"])
async def trust_disconnect_source(
    source: str,
    body: Dict[str, Any] | None = None,
    user: UserContext = Depends(get_user_context),
    db=Depends(get_db),
):
    """Disconnect a trust source and append a disconnected history row. 0 credits, Free+."""
    try:
        return TrustVerificationService(brain).disconnect_source(user, source, body, db)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/v1/trust/refresh/{source}", tags=["Trust Engine"])
async def trust_refresh_source(
    source: str,
    body: Dict[str, Any] | None = None,
    user: UserContext = Depends(get_user_context),
    db=Depends(get_db),
):
    """Trigger a metadata-only manual re-verification contract. 1 credit, Free+."""
    try:
        return TrustVerificationService(brain).refresh_source(user, source, body, db)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/v1/trust/refresh-plan", tags=["Trust Engine"])
async def trust_refresh_plan(
    body: Dict[str, Any],
    user: UserContext = Depends(get_user_context),
):
    """Compute continuous-verification refresh states without mutating history. 0 credits, Free+."""
    return TrustVerificationService(brain).get_refresh_plan(user, body)


@app.post("/api/v1/trust/continuous-verification/run", tags=["Trust Engine"])
async def trust_continuous_verification_run(
    body: Dict[str, Any],
    user: UserContext = Depends(get_user_context),
    db=Depends(get_db),
):
    """Prepare or execute metadata-only continuous verification actions. 0 credits, Free+."""
    try:
        return TrustVerificationService(brain).run_continuous_verification(user, body, db)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@app.post("/api/v1/trust/milestone", tags=["Trust Engine"])
async def trust_submit_milestone(
    body: Dict[str, Any],
    user: UserContext = Depends(get_user_context),
    db=Depends(get_db),
):
    """Submit milestone evidence metadata for review. 1 credit, Free+."""
    return TrustVerificationService(brain).submit_milestone(user, body, db)


@app.post("/api/v1/trust/milestone/review", tags=["Trust Engine"])
async def trust_review_milestone(
    body: Dict[str, Any],
    user: UserContext = Depends(get_user_context),
    db=Depends(get_db),
):
    """Review milestone evidence metadata and append approved/rejected Trust state. 1 credit."""
    return TrustVerificationService(brain).review_milestone(user, body, db)


@app.post("/api/v1/trust/team/invite", tags=["Trust Engine"])
async def trust_invite_team_member(
    body: Dict[str, Any],
    user: UserContext = Depends(get_user_context),
    db=Depends(get_db),
):
    """Prepare a metadata-only team invitation notification intent. 0 credits, Free+."""
    return TrustVerificationService(brain).invite_team_member(user, body, db)


@app.post("/api/v1/trust/team/verify", tags=["Trust Engine"])
async def trust_verify_team_member(
    body: Dict[str, Any],
    user: UserContext = Depends(get_user_context),
    db=Depends(get_db),
):
    """Verify a team member through metadata-only Trust state. 1 credit, Free+."""
    return TrustVerificationService(brain).verify_team_member(user, body, db)


@app.post("/api/v1/trust/notifications/preview", tags=["Trust Engine"])
async def trust_notifications_preview(
    body: Dict[str, Any],
    user: UserContext = Depends(get_user_context),
):
    """Build founder-only Trust notification intents without executing delivery. 0 credits, Free+."""
    return TrustVerificationService(brain).preview_notifications(user, body)


# ============================================================================
# TOUR GUIDE
# ============================================================================

@app.post("/api/v1/tour-guide/daily-check-in", tags=["Tour Guide"])
async def daily_check_in(user: UserContext = Depends(get_user_context)):
    """Daily momentum check-in. 0 credits, Free+"""
    return await TourGuideService(brain).daily_check_in(user)


# ============================================================================
# ADAPTIVE TRAINING
# ============================================================================

@app.post("/api/v1/training/curriculum/generate", tags=["Training"])
async def generate_curriculum(
    data: Dict[str, Any],
    user: UserContext = Depends(get_user_context),
):
    """
    Generate adaptive curriculum. Duration computed from TimeToMVPEngine --
    NOT fixed weeks. 1 credit, Free+
    """
    svc = AdaptiveTrainingService(brain)
    return await svc.generate_curriculum(
        user,
        hours_available_per_week=data.get("hours_per_week", 8.0),
        learning_pace=data.get("learning_pace", "standard"),
        target_mvp_weeks=data.get("target_mvp_weeks", 0),
        has_technical_skills=data.get("has_technical_skills", False),
    )


@app.post("/api/v1/training/curriculum/adapt", tags=["Training"])
async def adapt_curriculum(
    data: Dict[str, Any],
    user: UserContext = Depends(get_user_context),
):
    """Adapt curriculum based on trigger event (mvp_shipped, pivot, etc.). 1 credit."""
    return await AdaptiveTrainingService(brain).adapt_curriculum(
        user, data.get("trigger_event", ""), data
    )


@app.post("/api/v1/training/progress/update", tags=["Training"])
async def update_progress(
    data: Dict[str, Any],
    user: UserContext = Depends(get_user_context),
):
    """Mark a module complete and advance curriculum. 0 credits."""
    return await AdaptiveTrainingService(brain).mark_module_complete(
        user,
        data.get("module_id", ""),
        data.get("quiz_score"),
    )


# ============================================================================
# MATCHING
# ============================================================================

@app.post("/api/v1/matching/find-collaborators", tags=["Matching"])
async def find_collaborators(
    criteria: Dict[str, Any],
    user: UserContext = Depends(get_user_context),
):
    """Find compatible collaborators via vector + rules + LLM. 1 credit, Builder+"""
    return await MatchingEngineService(brain).find_collaborators(user, criteria)


# ============================================================================
# INVESTOR SECTION
# ============================================================================

@app.get("/api/v1/investor/deal-flow", tags=["Investor"])
async def deal_flow(user: UserContext = Depends(get_user_context)):
    """Ranked deal flow with EVI-I signals. 0 credits, Investor+"""
    return await InvestorSectionService(brain).get_deal_flow_ranking(user)


@app.post("/api/v1/investor/evi/{project_id}", tags=["Investor"])
async def investor_evi(
    project_id: str,
    startup_data: Dict[str, Any],
    user: UserContext = Depends(get_user_context),
):
    """6-dimensional EVI-I investor execution signal. 2 credits, Investor+"""
    return await InvestorSectionService(brain).get_investor_evi(user, startup_data)


@app.get("/api/v1/investor/capital-pools", tags=["Investor"])
async def investor_capital_pools(user: UserContext = Depends(get_user_context)):
    """Investor micro-fund capital pools with deployment + milestone release. 0 credits."""
    return await CapitalPoolService(brain).get_capital_pools(user)


@app.post("/api/v1/investor/capital-pools", tags=["Investor"])
async def investor_create_pool(
    body: Dict[str, Any],
    user: UserContext = Depends(get_user_context),
):
    """Create a new capital pool. 0 credits. Body: { name, totalCapital, rules }"""
    return await CapitalPoolService(brain).create_pool(user, body)


@app.post("/api/v1/investor/capital-pools/{pool_id}/release", tags=["Investor"])
async def investor_pool_release(
    pool_id: str,
    body: Dict[str, Any],
    user: UserContext = Depends(get_user_context),
):
    """Release escrowed capital on a hit milestone. 0 credits. Body: { projectId, milestone, amount }"""
    return await CapitalPoolService(brain).release_on_milestone(user, {**body, "poolId": pool_id})


@app.get("/api/v1/investor/deal-rooms", tags=["Investor"])
async def investor_deal_rooms(user: UserContext = Depends(get_user_context)):
    """Deal-room list metadata (status/stage/activity per startup). 0 credits."""
    return await DealRoomService(brain).get_deal_rooms(user)


@app.post("/api/v1/investor/deal-rooms/{project_id}", tags=["Investor"])
async def investor_deal_room(
    project_id: str,
    startup: Dict[str, Any] | None = None,
    user: UserContext = Depends(get_user_context),
):
    """
    Deal-room detail: term sheet (valuation ARR×8), milestone tranches, documents,
    negotiation stepper. 0 credits. Optional body: startup data (for valuation).
    """
    return await DealRoomService(brain).get_deal_room(user, project_id, startup)


@app.get("/api/v1/investor/data-rooms", tags=["Investor"])
async def investor_data_rooms(user: UserContext = Depends(get_user_context)):
    """Per-startup data-room vault metadata + access. 0 credits, Investor+"""
    return await DataRoomService(brain).get_data_rooms(user)


@app.post("/api/v1/investor/data-rooms/{project_id}/access", tags=["Investor"])
async def investor_data_room_access(
    project_id: str,
    body: Dict[str, Any],
    user: UserContext = Depends(get_user_context),
):
    """Share a data room with an investor. 0 credits. Body: { investorId, canDownload }"""
    return await DataRoomService(brain).grant_access(user, {**body, "projectId": project_id})


@app.get("/api/v1/investor/reputation", tags=["Investor"])
async def investor_reputation(user: UserContext = Depends(get_user_context)):
    """
    Investor reputation: composite score, component metrics, founder reviews,
    score progression, leaderboard position. 0 credits, Investor+.
    """
    return await InvestorReputationService(brain).get_reputation(user)


@app.get("/api/v1/investor/heatmap", tags=["Investor"])
async def investor_heatmap(user: UserContext = Depends(get_user_context)):
    """Geographic signal: per-region readiness/compliance + per-sector growth. 0 credits."""
    return await GeoSignalService(brain).get_heatmap(user)


# ============================================================================
# WORKSPACE AI  (task suggestions, code review, sprint planning)
# ============================================================================

def _extract_bearer_token(request: Request) -> Optional[str]:
    """Pull the raw Bearer off the request so we can forward it to BACKEND/api/mcp.
    Returns None when missing — endpoints that depend on MCP must decide
    whether to degrade gracefully or raise 401."""
    auth_header = request.headers.get("Authorization", "")
    if auth_header[:7].lower() == "bearer ":
        token = auth_header[7:].strip()
        return token or None
    return None


@app.post("/api/v1/workspace/tasks/suggest", tags=["Workspace"])
async def workspace_suggest_tasks(
    body: Dict[str, Any],
    request: Request,
    user: UserContext = Depends(get_user_context),
):
    """AI task suggestions for the workspace. 0 credits.

    Forwards the caller's Bearer token to BACKEND/api/mcp so suggestions are
    tool-aware (catalogue passed into the agent's prompt context)."""
    return await WorkspaceAIService(brain).suggest_tasks(
        user, body, user_token=_extract_bearer_token(request),
    )


@app.get("/api/v1/workspace/tools", tags=["Workspace"])
async def workspace_list_tools(
    request: Request,
    user: UserContext = Depends(get_user_context),
):
    """List plugin tools the user can invoke. 0 credits. Requires Bearer token."""
    token = _extract_bearer_token(request)
    if not token:
        raise HTTPException(status_code=401, detail="Bearer token required to list MCP tools")
    return await WorkspaceAIService(brain).list_tools(user, token)


@app.post("/api/v1/workspace/tools/invoke", tags=["Workspace"])
async def workspace_invoke_tool(
    body: Dict[str, Any],
    request: Request,
    user: UserContext = Depends(get_user_context),
):
    """Invoke a plugin tool as the authenticated user. 0 credits.
    Body: { plugin, tool, params? }. Forwards the caller's Bearer to
    BACKEND/api/mcp — role enforcement + audit happen there."""
    token = _extract_bearer_token(request)
    if not token:
        raise HTTPException(status_code=401, detail="Bearer token required to invoke MCP tool")
    plugin = (body.get("plugin") or "").strip()
    tool = (body.get("tool") or "").strip()
    if not plugin or not tool:
        raise HTTPException(status_code=400, detail="plugin and tool are required")
    params = body.get("params") or {}
    return await WorkspaceAIService(brain).invoke_tool(user, token, plugin, tool, params)


@app.post("/api/v1/workspace/code/review", tags=["Workspace"])
async def workspace_review_code(
    body: Dict[str, Any],
    user: UserContext = Depends(get_user_context),
):
    """AI code review. 1 credit, Founder Pro+. Body: { code, language, context }"""
    return await WorkspaceAIService(brain).review_code(user, body)


@app.post("/api/v1/workspace/sprint/plan", tags=["Workspace"])
async def workspace_plan_sprint(
    body: Dict[str, Any],
    user: UserContext = Depends(get_user_context),
):
    """AI sprint planning. 0 credits."""
    return await WorkspaceAIService(brain).plan_sprint(user, body)


# ============================================================================
# FOUNDER PROJECTS  (multi-project portfolio)
# ============================================================================

@app.get("/api/v1/founder/projects", tags=["Founder"])
async def founder_projects(user: UserContext = Depends(get_user_context)):
    """A founder's portfolio of ventures (multiple separate startups). 0 credits."""
    return await ProjectService(brain).list_founder_projects(user)


@app.post("/api/v1/founder/projects", tags=["Founder"])
async def founder_create_project(
    body: Dict[str, Any],
    user: UserContext = Depends(get_user_context),
):
    """Create a new venture. 0 credits.
    Body: { title, tagline?, industry?, stage?, hackathonId?, teamId? }.
    hackathonId+teamId are recorded on the project's origin field when both are
    provided, so a venture promoted from a hackathon knows where it came from."""
    return await ProjectService(brain).create_project(user, body)


# ============================================================================
# WORKSPACES  (bound to an analyzed venture; Incubation → Workspace pipeline)
# ============================================================================

@app.get("/api/v1/workspaces", tags=["Workspace"])
async def list_workspaces(user: UserContext = Depends(get_user_context)):
    """List the founder's workspaces (each bound to a project). 0 credits."""
    return await WorkspaceService(brain).list_workspaces(user)


@app.post("/api/v1/workspaces/provision", tags=["Workspace"])
async def provision_workspace(
    body: Dict[str, Any],
    user: UserContext = Depends(get_user_context),
):
    """
    Provision (or fetch) a workspace bound to an analyzed project, seeded from
    its latest Incubation Hub analysis. 0 credits. Body: { projectId, name? }
    """
    return await WorkspaceService(brain).provision_workspace(user, body)


@app.get("/api/v1/workspaces/{workspace_id}/context", tags=["Workspace"])
async def workspace_context(
    workspace_id: str,
    project_id: Optional[str] = None,
    user: UserContext = Depends(get_user_context),
):
    """Project-scoped workspace context (loads the bound venture's blueprint). 0 credits."""
    return await WorkspaceService(brain).get_workspace_context(user, workspace_id, project_id)


# ============================================================================
# HACKATHON INTELLIGENCE  (org host + team/founder + idea→workspace)
# ============================================================================

@app.get("/api/v1/hackathons", tags=["Hackathon"])
async def list_hackathons(user: UserContext = Depends(get_user_context)):
    """List hackathons. 0 credits."""
    return await HackathonService(brain).list_hackathons(user)


@app.get("/api/v1/hackathons/{hackathon_id}/overview", tags=["Hackathon"])
async def hackathon_overview(hackathon_id: str, user: UserContext = Depends(get_user_context)):
    """Org command-centre real-time stats. 0 credits."""
    return await HackathonService(brain).get_overview(user, hackathon_id)


@app.get("/api/v1/hackathons/{hackathon_id}/velocity", tags=["Hackathon"])
async def hackathon_velocity(hackathon_id: str, user: UserContext = Depends(get_user_context)):
    """Per-team build-velocity heatmap from REAL check-ins (not random). 0 credits."""
    return await HackathonService(brain).get_velocity_heatmap(user, hackathon_id)


@app.get("/api/v1/hackathons/{hackathon_id}/leaderboard", tags=["Hackathon"])
async def hackathon_leaderboard(hackathon_id: str, user: UserContext = Depends(get_user_context)):
    """Composite-ranked leaderboard. 0 credits."""
    return await HackathonService(brain).get_leaderboard(user, hackathon_id)


@app.get("/api/v1/hackathons/{hackathon_id}/pipeline", tags=["Hackathon"])
async def hackathon_pipeline(hackathon_id: str, user: UserContext = Depends(get_user_context)):
    """CRS pipeline buckets (incubation/prototype/learning). 0 credits."""
    return await HackathonService(brain).get_pipeline(user, hackathon_id)


@app.post("/api/v1/hackathons/{hackathon_id}/register", tags=["Hackathon"])
async def hackathon_register(
    hackathon_id: str, body: Dict[str, Any], user: UserContext = Depends(get_user_context),
):
    """Register a team/solo. 0 credits. Body: { name?, members? }"""
    return await HackathonService(brain).register(user, {**body, "hackathonId": hackathon_id})


@app.post("/api/v1/hackathons/{hackathon_id}/brief", tags=["Hackathon"])
async def hackathon_brief(
    hackathon_id: str, body: Dict[str, Any], user: UserContext = Depends(get_user_context),
):
    """Submit + score an idea brief. 0 credits. Body: { teamId, problem, solution, ... }"""
    return await HackathonService(brain).submit_brief(user, {**body, "hackathonId": hackathon_id})


@app.post("/api/v1/hackathons/{hackathon_id}/checkin", tags=["Hackathon"])
async def hackathon_checkin(
    hackathon_id: str, body: Dict[str, Any], user: UserContext = Depends(get_user_context),
):
    """Log a build check-in (feeds the velocity heatmap). 0 credits. Body: { teamId, note, progressDelta? }"""
    return await HackathonService(brain).log_check_in(user, {**body, "hackathonId": hackathon_id})


@app.get("/api/v1/hackathons/{hackathon_id}/teams/{team_id}/status", tags=["Hackathon"])
async def hackathon_team_status(
    hackathon_id: str, team_id: str, user: UserContext = Depends(get_user_context),
):
    """Team-facing status (brief, composite, check-ins, workspace). 0 credits."""
    return await HackathonService(brain).get_team_status(user, hackathon_id, team_id)


@app.post("/api/v1/hackathons/{hackathon_id}/teams/{team_id}/workspace", tags=["Hackathon"])
async def hackathon_team_workspace(
    hackathon_id: str, team_id: str, body: Dict[str, Any],
    user: UserContext = Depends(get_user_context),
):
    """Pipe the analyzed brief into a team workspace. 0 credits. Body: { projectId? }"""
    return await HackathonService(brain).provision_team_workspace(user, hackathon_id, team_id, body)


@app.post("/api/v1/hackathons/{hackathon_id}/teams/{team_id}/report", tags=["Hackathon"])
async def hackathon_team_report(
    hackathon_id: str, team_id: str, body: Dict[str, Any],
    user: UserContext = Depends(get_user_context),
):
    """Report a team's idea+artifacts to organizers (promote pipeline). 0 credits.
    Body: { workspaceId?, idea?, team?, artifacts?, stage? }"""
    return await HackathonService(brain).report_team_to_organizers(user, hackathon_id, team_id, body)


# ============================================================================
# TOUR GUIDE  (momentum audio briefing)
# ============================================================================

@app.post("/api/v1/tour-guide/audio-briefing", tags=["Tour Guide"])
async def tour_guide_audio_briefing(
    body: Dict[str, Any],
    user: UserContext = Depends(get_user_context),
):
    """Momentum audio briefing (TTS). 0 credits. Body: { text }"""
    return await TourGuideService(brain).get_audio_briefing(user, body.get("text", ""))


# ============================================================================
# ADMIN MONITOR  (anomaly scan + stagnation roster)
# ============================================================================

@app.post("/api/v1/admin/monitor/scan", tags=["Admin"])
async def admin_monitor_scan(
    body: Dict[str, Any],
    user: UserContext = Depends(get_user_context),
):
    """Anomaly scan over signals. 0 credits, Admin only. Body: { signals: [...] }"""
    return await AdminMonitorService(brain).run_anomaly_scan(user, body.get("signals", []))


@app.post("/api/v1/admin/stagnation-roster", tags=["Admin"])
async def admin_stagnation_roster(
    body: Dict[str, Any],
    user: UserContext = Depends(get_user_context),
):
    """Stagnating-project roster (decay-based). 0 credits. Body: { projects: [...] }"""
    return await AdminMonitorService(brain).check_stagnation_roster(user, body.get("projects", []))


# ============================================================================
# COLLABORATOR — EQUITY & VESTING
# ============================================================================

@app.get("/api/v1/collaborator/equity", tags=["Collaborator"])
async def collaborator_equity(user: UserContext = Depends(get_user_context)):
    """
    Collaborator equity holdings, totals, and vesting timeline. 0 credits, Free+.
    Returns { holdings, totals, vestingTimeline } in camelCase (matches the
    frontend EquityHolding / equityTotals / VestingTimelineSeries contracts).
    """
    return await EquityService(brain).get_collaborator_equity(user)


@app.post("/api/v1/collaborator/equity/dilution", tags=["Collaborator"])
async def collaborator_equity_dilution(
    body: Dict[str, Any],
    user: UserContext = Depends(get_user_context),
):
    """
    Apply a dilution event with protection. 0 credits, Free+.
    Body: { projectId, newSharesPercent, consentGiven }
    Already-vested equity is shielded unless consent is given.
    """
    return await EquityService(brain).record_dilution_event(user, body)


# ============================================================================
# COLLABORATOR — EARNINGS & PAYOUTS
# ============================================================================

@app.get("/api/v1/collaborator/earnings", tags=["Collaborator"])
async def collaborator_earnings(user: UserContext = Depends(get_user_context)):
    """
    Collaborator cash earnings, payout ledger, and totals. 0 credits, Free+.
    Returns { cashEarnings, payouts, totals } in camelCase (matches frontend
    CashEarning / Payout / cashTotals contracts).
    """
    return await PayoutService(brain).get_collaborator_earnings(user)


@app.post("/api/v1/collaborator/earnings/withdraw", tags=["Collaborator"])
async def collaborator_withdraw(
    body: Dict[str, Any],
    user: UserContext = Depends(get_user_context),
):
    """Request a withdrawal of pending funds. 0 credits. Body: { amount, destination? }"""
    return await PayoutService(brain).request_withdrawal(user, body)


# ============================================================================
# IDEA & SOLUTION HUB
# ============================================================================

@app.post("/api/v1/solutions/problems/submit", tags=["Idea & Solution Hub"])
async def submit_problem(
    body: Dict[str, Any],
    user: UserContext = Depends(get_user_context),
):
    """Submit a real-world problem to the Global Problems Board. 2 credits, Free+"""
    return await IdeaSolutionHubService(brain).submit_problem(
        user,
        title=body["title"],
        description=body["description"],
        category=body["category"],
        location=body.get("location", "Global"),
        who_is_affected=body.get("who_is_affected", ""),
        current_solutions=body.get("current_solutions", []),
        urgency=body.get("urgency", "emerging"),
        people_affected_millions=body.get("people_affected_millions", 1.0),
    )


@app.get("/api/v1/solutions/problems/board", tags=["Idea & Solution Hub"])
async def get_problems_board(
    limit: int = 20,
    user: UserContext = Depends(get_user_context),
    db=Depends(get_db),
):
    """Global Problems Board -- verified problems ranked by priority score. 0 credits, Free+"""
    from database_schema import ProblemNode

    capped = min(max(limit, 1), 100)
    try:
        rows = (
            db.query(ProblemNode)
            .filter(ProblemNode.verified.is_(True))
            .order_by(ProblemNode.priority_score.desc())
            .limit(capped)
            .all()
        )
    except Exception as e:  # noqa: BLE001 -- degrade rather than 500 the board
        logger.error("problems_board_query_failed", error=str(e))
        raise HTTPException(status_code=503, detail="Problems board temporarily unavailable")

    return {
        "problems": [
            {
                "id": str(p.id),
                "title": p.title,
                "description": p.description,
                "category": p.category,
                "urgency": p.urgency,
                "location": p.location,
                "priority_score": float(p.priority_score or 0),
                "impact_score": float(p.impact_score or 0),
                "engagement_count": p.engagement_count or 0,
                "sdg_alignment": p.sdg_alignment or [],
                "tags": p.tags or [],
                "is_ai_discovered": bool(p.is_ai_discovered),
                "created_at": p.created_at.isoformat() if p.created_at else None,
            }
            for p in rows
        ],
        "count": len(rows),
        "limit": capped,
    }


@app.post("/api/v1/solutions/problems/{problem_id}/analyze", tags=["Idea & Solution Hub"])
async def analyze_problem(
    problem_id: str,
    body: Dict[str, Any],
    user: UserContext = Depends(get_user_context),
):
    """Deep AI problem analysis -- stakeholder map, root causes. 2 credits, Builder+"""
    return await IdeaSolutionHubService(brain).analyze_problem(user, problem_id, body)


@app.get("/api/v1/solutions/problems/discover", tags=["Idea & Solution Hub"])
async def discover_problems(
    region: Optional[str] = None,
    limit: int = 20,
    user: UserContext = Depends(get_user_context),
):
    """Auto-discover problems from external signals. 2 credits, Builder+"""
    return await IdeaSolutionHubService(brain).discover_problems(user, region, limit)


@app.post("/api/v1/solutions/discussions/{thread_id}/convert", tags=["Idea & Solution Hub"])
async def convert_discussion(
    thread_id: str,
    body: Dict[str, Any],
    user: UserContext = Depends(get_user_context),
):
    """Convert matured discussion to Solution Project. 3 credits, Founder Pro+"""
    return await IdeaSolutionHubService(brain).convert_to_solution(
        user,
        problem_id=body["problem_id"],
        title=body["title"],
        solution_type=body["solution_type"],
        funding_type=body["funding_type"],
        description=body["description"],
        discussion_summary=body.get("discussion_summary", ""),
    )


@app.post("/api/v1/solutions/deployments/create", tags=["Idea & Solution Hub"])
async def create_solution_deployment(
    body: Dict[str, Any],
    user: UserContext = Depends(get_user_context),
):
    """Create real-world deployment plan for a validated solution. 2 credits, Founder Pro+"""
    from idea_solution_hub import (SolutionProject, SolutionType, FundingType,
                                    SolutionStage, ContributorRole)
    sol = SolutionProject(
        problem_id=body.get("problem_id", ""),
        title=body.get("title", ""),
        solution_type=SolutionType.HYBRID,
        funding_type=FundingType.HYBRID,
        stage=SolutionStage.VALIDATED,
        execution_plan=body.get("execution_plan", "x"),
        required_roles=[],
        impact_score=body.get("impact_score", 50.0),
        feasibility_score=body.get("feasibility_score", 50.0),
    )
    return await IdeaSolutionHubService(brain).create_deployment(
        user, body["solution_id"], body,
        body["mode"], body["region"],
        body.get("beneficiaries_target", 0),
    )


@app.post("/api/v1/solutions/deployments/{deployment_id}/feedback", tags=["Idea & Solution Hub"])
async def submit_field_feedback(
    deployment_id: str,
    body: Dict[str, Any],
    user: UserContext = Depends(get_user_context),
):
    """Submit field feedback from a live deployment. 1 credit, Free+"""
    return await IdeaSolutionHubService(brain).submit_field_feedback(
        user, deployment_id,
        body["solution_id"], body["field_report"],
        body.get("impact_metrics", {}), body.get("failure_points", []),
    )


@app.post("/api/v1/solutions/grants/generate", tags=["Idea & Solution Hub"])
async def generate_grant(
    body: Dict[str, Any],
    user: UserContext = Depends(get_user_context),
):
    """Generate AI grant application for a solution. 3 credits, Founder Pro+"""
    from idea_solution_hub import (SolutionProject, SolutionType, FundingType,
                                    SolutionStage)
    sol = SolutionProject(
        problem_id=body.get("problem_id", ""),
        title=body.get("title", ""),
        solution_type=SolutionType.SOCIAL_INITIATIVE,
        funding_type=FundingType.GRANTS,
        stage=SolutionStage.VALIDATED,
        impact_score=body.get("impact_score", 50.0),
        execution_plan=body.get("execution_plan", ""),
    )
    return await IdeaSolutionHubService(brain).generate_grant_application(
        user, sol,
        funder_name=body["funder_name"],
        funding_type=body.get("funding_type", "grants"),
        amount_usd=body.get("amount_usd", 50000),
    )


@app.get("/api/v1/solutions/impact/global", tags=["Idea & Solution Hub"])
async def global_impact(
    user: UserContext = Depends(get_user_context),
    db=Depends(get_db),
):
    """Global Impact Dashboard -- live aggregates over deployments + impact snapshots. 0 credits, Free+"""
    from sqlalchemy import func
    from database_schema import (
        ProblemNode, SolutionProject, SolutionDeployment, ImpactSnapshot,
    )

    try:
        active_problems = db.query(func.count(ProblemNode.id)).filter(
            ProblemNode.verified.is_(True)
        ).scalar() or 0
        active_solutions = db.query(func.count(SolutionProject.id)).scalar() or 0
        active_deployments = db.query(func.count(SolutionDeployment.id)).filter(
            SolutionDeployment.status == "active"
        ).scalar() or 0
        total_beneficiaries = db.query(
            func.coalesce(func.sum(SolutionDeployment.beneficiaries_reached), 0)
        ).scalar() or 0
        # Distinct deployment regions (drop NULLs) → country/region list.
        countries = [
            r[0] for r in db.query(SolutionDeployment.region)
            .filter(SolutionDeployment.region.isnot(None))
            .distinct().all()
        ]
        funds_deployed_usd = db.query(
            func.coalesce(func.sum(ImpactSnapshot.funds_deployed_usd), 0)
        ).scalar() or 0
    except Exception as e:  # noqa: BLE001
        logger.error("global_impact_query_failed", error=str(e))
        raise HTTPException(status_code=503, detail="Global impact data temporarily unavailable")

    return IdeaSolutionHubService(brain).get_global_impact_dashboard(
        active_problems=int(active_problems),
        active_solutions=int(active_solutions),
        active_deployments=int(active_deployments),
        total_beneficiaries=int(total_beneficiaries),
        countries=countries,
        funds_deployed_usd=float(funds_deployed_usd),
    )


# ============================================================================
# DOCUMENT GENERATION ENGINE
# ============================================================================

@app.get("/api/v1/documents/templates", tags=["Document Generation"])
async def get_doc_templates(user: UserContext = Depends(get_user_context)):
    """List all 8 document types with credit costs and page estimates. 0 credits, Free+"""
    return DocumentGenerationService(brain).get_available_templates()


@app.post("/api/v1/documents/generate", tags=["Document Generation"])
async def generate_document(
    body: Dict[str, Any],
    user: UserContext = Depends(get_user_context),
):
    """
    Generate any of the 8 document types.
    2–4 credits depending on type. Founder Pro+

    Body params:
      project_id       (required)
      document_type    (required) -- executive_summary | business_plan | pitch_deck |
                                    investor_report | unicorn_analysis_report |
                                    product_roadmap | financial_projection | market_research_report
      style            (optional) -- concise | standard | detailed  (default: standard)
      audience         (optional) -- founder_use | investors | accelerators  (default: investors)
      export_format    (optional) -- pdf | notion_doc | google_doc | slide_deck  (default: pdf)
      investor_mode    (optional) -- bool  (default: false)
      startup_data     (optional) -- dict
      analysis_results (optional) -- dict (GSIS, EVI-I, unicorn_potential_score)
    """
    return await DocumentGenerationService(brain).generate_document(
        user_context=user,
        project_id=body["project_id"],
        document_type=body["document_type"],
        style=body.get("style", "standard"),
        audience=body.get("audience", "investors"),
        export_format=body.get("export_format", "pdf"),
        investor_mode=body.get("investor_mode", False),
        startup_data=body.get("startup_data", {}),
        analysis_results=body.get("analysis_results", {}),
    )


@app.post("/api/v1/documents/investor-pack", tags=["Document Generation"])
async def investor_pack(
    body: Dict[str, Any],
    user: UserContext = Depends(get_user_context),
):
    """
    Generate the complete investor pack in one call:
    Executive Summary + Pitch Deck + Business Plan + Investor Report.
    8 credits. Investor+
    """
    return await DocumentGenerationService(brain).generate_investor_pack(
        user,
        body["project_id"],
        body.get("startup_data", {}),
        body.get("analysis_results", {}),
    )


@app.post("/api/v1/documents/{document_id}/edit", tags=["Document Generation"])
async def edit_document(
    document_id: str,
    body: Dict[str, Any],
    user: UserContext = Depends(get_user_context),
):
    """AI-powered in-document editing. 2 credits, Builder+"""
    return await DocumentGenerationService(brain).edit_with_ai(
        user, document_id,
        body["current_content"],
        body["edit_instruction"],
        body.get("section"),
    )


@app.post("/api/v1/documents/{document_id}/share", tags=["Document Generation"])
async def share_document(
    document_id: str,
    body: Dict[str, Any],
    user: UserContext = Depends(get_user_context),
):
    """Generate shareable link with expiry. 0 credits, Free+"""
    return await DocumentGenerationService(brain).share_document(
        user, document_id,
        body.get("expiry_days", 30),
    )


# ============================================================================
# IP PROTECTION
# ============================================================================

@app.get("/api/v1/ip-protection/status", tags=["IP Protection"])
async def ip_protection_status(user: UserContext = Depends(get_user_context)):
    """Three-layer IP protection status. 0 credits, Founder Pro+"""
    return IPProtectionService(brain).get_protection_status()


@app.post("/api/v1/ip-protection/check-fingerprint", tags=["IP Protection"])
async def check_fingerprint(
    body: Dict[str, Any],
    user: UserContext = Depends(get_user_context),
):
    """
    Check if a fingerprint matches any stored idea fingerprints.
    Returns action=block on collision, action=allow on clear.
    0 credits, Founder Pro+
    """
    svc = IPProtectionService(brain)
    fp = svc.fingerprint(body.get("idea_text", ""))
    stored = body.get("stored_fingerprints", [])
    return svc.check_exact_match(fp, stored)


@app.post("/api/v1/ip-protection/embed-idea", tags=["IP Protection"])
async def embed_idea(
    body: Dict[str, Any],
    user: UserContext = Depends(get_user_context),
):
    """Create vector embedding for IP leak detection. 1 credit, Founder Pro+"""
    return await IPProtectionService(brain).create_idea_embedding(
        user_context=user,
        project_id=body.get("project_id", user.project_id or ""),
        idea_text=body.get("idea_text", ""),
    )


# ============================================================================
# BILLING & CREDITS
# ============================================================================

@app.get("/api/v1/credits/summary", tags=["Billing"])
async def credits_summary(
    user: UserContext = Depends(get_user_context),
    db=Depends(get_db),
):
    """
    Current credit balance and usage summary from credit_ledger + credit_purchases.
    0 credits, Free+
    """
    from sqlalchemy import func
    from database_schema import CreditLedger, CreditPurchase

    try:
        latest = (
            db.query(CreditLedger)
            .filter(CreditLedger.user_id == user.user_id)
            .order_by(CreditLedger.created_at.desc())
            .first()
        )
        balance = latest.credits_after if latest else user.credits_remaining

        spent = db.query(func.coalesce(func.sum(CreditLedger.credits_delta), 0)).filter(
            CreditLedger.user_id == user.user_id,
            CreditLedger.credits_delta < 0,
        ).scalar() or 0

        credits_purchased = db.query(func.coalesce(func.sum(CreditPurchase.credits_qty), 0)).filter(
            CreditPurchase.user_id == user.user_id,
            CreditPurchase.status == "completed",
        ).scalar() or 0

        usd_spent = db.query(func.coalesce(func.sum(CreditPurchase.amount_usd), 0)).filter(
            CreditPurchase.user_id == user.user_id,
            CreditPurchase.status == "completed",
        ).scalar() or 0

        recent = (
            db.query(CreditLedger)
            .filter(CreditLedger.user_id == user.user_id)
            .order_by(CreditLedger.created_at.desc())
            .limit(10)
            .all()
        )
    except Exception as e:  # noqa: BLE001
        logger.error("credits_summary_query_failed", error=str(e))
        raise HTTPException(status_code=503, detail="Credit summary temporarily unavailable")

    return {
        "user_id":            user.user_id,
        "subscription_tier":  user.subscription_tier.value,
        "balance":            int(balance or 0),
        "credits_purchased":  int(credits_purchased),
        "credits_spent":      abs(int(spent)),
        "usd_spent":          float(usd_spent),
        "recent_transactions": [
            {
                "id":            str(t.id),
                "event_type":    t.event_type.value if hasattr(t.event_type, "value") else str(t.event_type),
                "credits_delta": t.credits_delta,
                "credits_after": t.credits_after,
                "task_type":     t.task_type,
                "description":   t.description,
                "created_at":    t.created_at.isoformat() if t.created_at else None,
            }
            for t in recent
        ],
    }


@app.post("/api/v1/billing/paywall/{operation_id}", tags=["Billing"])
async def check_paywall(
    operation_id: str,
    user: UserContext = Depends(get_user_context),
):
    """Check paywall status for an operation. 0 credits, Free+"""
    from billing_system import CREDIT_OPERATIONS
    op = CREDIT_OPERATIONS.get(operation_id)
    if not op:
        raise HTTPException(status_code=404, detail=f"Operation '{operation_id}' not found")
    can_afford = user.credits_remaining >= op.credit_cost
    return {
        "operation_id":    operation_id,
        "credit_cost":     op.credit_cost,
        "credits_remaining": user.credits_remaining,
        "can_proceed":     can_afford,
        "paywall_active":  not can_afford,
        "upgrade_message": f"Unlock {operation_id} -- upgrade your plan" if not can_afford else None,
    }


# ============================================================================
# STRIPE WEBHOOK
# ============================================================================

@app.post("/api/v1/webhooks/stripe", tags=["Billing"])
async def stripe_webhook(request: Request):
    """
    Stripe webhook handler with signature verification.

    Verifies the `stripe-signature` header against STRIPE_WEBHOOK_SECRET, then
    dispatches on event type. `checkout.session.completed` records a PAYG credit
    purchase (idempotent on the Stripe id).
    """
    import stripe

    webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET")
    if not webhook_secret:
        logger.error("stripe_webhook_misconfigured", reason="STRIPE_WEBHOOK_SECRET not set")
        raise HTTPException(status_code=500, detail="Stripe webhook is not configured")

    payload = await request.body()
    sig_header = request.headers.get("stripe-signature", "")

    try:
        event = stripe.Webhook.construct_event(payload, sig_header, webhook_secret)
    except ValueError:
        # Malformed payload
        raise HTTPException(status_code=400, detail="Invalid payload")
    except stripe.error.SignatureVerificationError:
        raise HTTPException(status_code=400, detail="Invalid signature")

    event_type = event.get("type", "")
    obj = event.get("data", {}).get("object", {}) or {}

    # Process known events. Failures here are logged but still return 200 so
    # Stripe doesn't retry indefinitely once the signature is verified.
    try:
        if event_type == "checkout.session.completed":
            _record_credit_purchase(obj)
        else:
            logger.info("stripe_webhook_ignored", event_type=event_type)
    except Exception as e:  # noqa: BLE001
        logger.error("stripe_webhook_processing_failed", event_type=event_type, error=str(e))

    return {"received": True, "event_type": event_type}


def _record_credit_purchase(session_obj: Dict[str, Any]) -> None:
    """Idempotently record a PAYG credit purchase from a completed checkout session."""
    from database_schema import CreditPurchase

    stripe_id = session_obj.get("id")
    metadata = session_obj.get("metadata", {}) or {}
    user_id = metadata.get("user_id")
    credits_qty = int(metadata.get("credits", 0) or 0)
    amount_usd = (session_obj.get("amount_total", 0) or 0) / 100.0  # cents -> USD

    if not (stripe_id and user_id and credits_qty > 0):
        logger.warning("stripe_checkout_missing_fields", stripe_id=stripe_id, user_id=user_id)
        return

    Session = _db_session_factory()
    db = Session()
    try:
        exists = db.query(CreditPurchase).filter(CreditPurchase.stripe_id == stripe_id).first()
        if exists:
            logger.info("stripe_checkout_already_recorded", stripe_id=stripe_id)
            return
        db.add(CreditPurchase(
            user_id=user_id,
            credits_qty=credits_qty,
            amount_usd=amount_usd,
            stripe_id=stripe_id,
            status="completed",
        ))
        db.commit()
        logger.info("stripe_credit_purchase_recorded", user_id=user_id, credits=credits_qty)
    finally:
        db.close()


# ============================================================================
# GLOBAL ERROR HANDLER
# ============================================================================

@app.exception_handler(PermissionError)
async def permission_error_handler(request: Request, exc: PermissionError):
    return JSONResponse(
        status_code=403,
        content={"error": "permission_denied", "detail": str(exc)},
    )


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    return JSONResponse(
        status_code=400,
        content={"error": "bad_request", "detail": str(exc)},
    )


@app.exception_handler(Exception)
async def general_error_handler(request: Request, exc: Exception):
    logger.error("unhandled_error", path=request.url.path, error=str(exc))
    return JSONResponse(
        status_code=500,
        content={"error": "internal_server_error", "detail": "An unexpected error occurred"},
    )


# ============================================================================
# DEV ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,          # auto-reload on file changes (dev only)
        log_level="info",
    )
