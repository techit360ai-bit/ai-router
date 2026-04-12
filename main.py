""" 
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
)
from ai_router_core import UserContext, UserRole, SubscriptionTier

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
    Nothing else should call TechITAIBrain() -- it's a singleton.
    """
    global brain
    brain = TechITAIBrain()
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
        "34 AI agents · 51 task types · 20 scoring models · Prompt → Live App."
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

async def get_user_context(request: Request) -> UserContext:
    """
    Extract and validate the current user from the request.

    Production implementation:
      1. Read Authorization header → "Bearer <jwt_token>"
      2. Decode JWT using python-jose + SECRET_KEY
      3. Extract user_id from payload
      4. Query users + billing tables from PostgreSQL
      5. Build and return UserContext

    Current implementation:
      Returns a demo Founder Pro context so every endpoint works
      immediately without auth infrastructure. Replace this before
      going to production.

    To add real auth, install python-jose:
      pip install python-jose[cryptography] passlib[bcrypt]
    """
    # ── Production: uncomment and complete ────────────────────────────────
    # from jose import JWTError, jwt
    # token = request.headers.get("Authorization", "").replace("Bearer ", "")
    # if not token:
    #     raise HTTPException(status_code=401, detail="Missing authentication token")
    # try:
    #     payload = jwt.decode(token, os.getenv("SECRET_KEY"), algorithms=["HS256"])
    #     user_id = payload.get("sub")
    # except JWTError:
    #     raise HTTPException(status_code=401, detail="Invalid token")
    # user = await fetch_user_from_db(user_id)
    # return build_user_context(user)
    # ── End production block ──────────────────────────────────────────────

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


# ============================================================================
# HEALTH & STATUS
# ============================================================================

@app.get("/health", tags=["Status"])
async def health():
    """Platform health check. Used by Docker, Kubernetes, and load balancers."""
    return {
        "status":         "healthy",
        "ai_brain":       "operational",
        "version":        "3.0.0",
        "agents":         34,
        "task_types":     51,
        "scoring_models": 20,
        "db_tables":      42,
    }


@app.get("/", tags=["Status"])
async def root():
    return {
        "platform": "TechIT AI Incubation Platform",
        "version":  "3.0.0",
        "docs":     "/docs",
        "health":   "/health",
        "tagline":  "Idea → Score → Build → Deploy → Track → Raise. All here. All AI-native.",
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
    Intake → Unicorn → Market → Feasibility → Strategy → Finance →
    BusinessPlan → TechArch → InvestorIntel → AppScaffold

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
# PROMPT → LIVE APP  (App Scaffold Engine)
# ============================================================================

@app.post("/api/v1/scaffold/generate", tags=["Prompt → Live App"])
async def generate_scaffold(
    body: Dict[str, Any],
    user: UserContext = Depends(get_user_context),
):
    """
    Generate a complete application scaffold from the venture profile.
    Pages · Supabase schema SQL · API routes · .env.example · Deploy config.
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


@app.post("/api/v1/scaffold/{scaffold_id}/deploy", tags=["Prompt → Live App"])
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


@app.get("/api/v1/scaffold/{scaffold_id}/status", tags=["Prompt → Live App"])
async def scaffold_status(
    scaffold_id: str,
    user: UserContext = Depends(get_user_context),
):
    """Poll deployment status. 0 credits, Free+"""
    return AppScaffoldService(brain).get_deploy_status(scaffold_id)


@app.get("/api/v1/scaffold/{scaffold_id}/live-url", tags=["Prompt → Live App"])
async def scaffold_live_url(
    scaffold_id: str,
    user: UserContext = Depends(get_user_context),
):
    """Get live URL after deployment. 0 credits, Free+"""
    return AppScaffoldService(brain).get_live_url(scaffold_id)


@app.get("/api/v1/scaffold/{project_id}", tags=["Prompt → Live App"])
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


@app.get("/api/v1/scaffold/stacks", tags=["Prompt → Live App"])
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
):
    """Global Problems Board -- ranked by priority score. 0 credits, Free+"""
    # Production: SELECT * FROM problem_nodes ORDER BY priority_score DESC LIMIT :limit
    return {
        "message": "Global Problems Board -- query problem_nodes ordered by priority_score DESC",
        "limit": limit,
        "query": "SELECT * FROM problem_nodes WHERE verified=true ORDER BY priority_score DESC",
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
async def global_impact(user: UserContext = Depends(get_user_context)):
    """Global Impact Dashboard -- live metrics. 0 credits, Free+"""
    # Production: query impact_snapshots + solution_deployments aggregates
    return IdeaSolutionHubService(brain).get_global_impact_dashboard(
        active_problems=0, active_solutions=0, active_deployments=0,
        total_beneficiaries=0, countries=[], funds_deployed_usd=0.0,
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
async def credits_summary(user: UserContext = Depends(get_user_context)):
    """
    Current credit balance and usage summary. 0 credits, Free+

    Production: fetch UserBillingState from billing DB tables.
    """
    return {
        "user_id":             user.user_id,
        "credits_remaining":   user.credits_remaining,
        "subscription_tier":   user.subscription_tier.value,
        "message": (
            "Production: query credit_ledger + credit_purchases tables. "
            "See billing_system.py HybridCreditEngine."
        ),
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
    Stripe webhook handler.
    Production: verify signature, handle checkout.session.completed,
    update credit_purchases + credit_ledger tables.
    """
    # Production:
    # import stripe
    # payload = await request.body()
    # sig_header = request.headers.get("stripe-signature")
    # try:
    #     event = stripe.Webhook.construct_event(
    #         payload, sig_header, os.getenv("STRIPE_WEBHOOK_SECRET")
    #     )
    # except stripe.error.SignatureVerificationError:
    #     raise HTTPException(status_code=400, detail="Invalid signature")
    # Handle event.type ...
    return {"received": True}


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
"""
