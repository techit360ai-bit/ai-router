"""
TECHIT AI ROUTER — DEPLOYMENT ARCHITECTURE
===========================================
Production-grade infrastructure for the TechIT AI Incubation Platform.

Stack
─────
  API Layer         → FastAPI (Python 3.11)
  Database          → PostgreSQL 16 + pgvector
  Cache / Queue     → Redis 7
  Vector Search     → pgvector (primary) + Pinecone (scale)
  Background Jobs   → Celery + Celery Beat
  Containers        → Docker + Kubernetes
  Object Storage    → AWS S3 + CloudFront
  Monitoring        → Sentry + Grafana + Prometheus + CloudWatch
  CI/CD             → GitHub Actions

Microservices
─────────────
  api-service        → FastAPI REST API (all endpoints)
  worker-service     → Celery workers (AI agent execution, 4 queues)
  scheduler-service  → Celery Beat (all cron jobs)
  scoring-service    → Real-time WCRS + GSIS + decay computation
  notification-svc   → Push + email notification delivery

Services included in this deployment
──────────────────────────────────────
  All AI agents (21 total)
  Hybrid billing system
  EVI-I investor signals
  Adaptive training (time-to-MVP engine)
  GSIS computation and surfacing
  Paywall enforcement
  Referral engine

Cost Model
──────────
  Per active Founder Pro user/month: ~$2–5
  Free tier user/month: ~$0.05
  Infrastructure at 10K users: ~$800/month
  AI costs at 10K active users: ~$20,100/month
  Gross margin at scale: ~96.5%
"""

# ============================================================================
# INFRASTRUCTURE DIAGRAM
# ============================================================================

ARCHITECTURE_DIAGRAM = """
┌──────────────────────────────────────────────────────────────┐
│                   LOAD BALANCER (AWS ALB / Nginx)            │
└──────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
┌──────────────┐   ┌──────────────┐   ┌──────────────────────┐
│  API Service │   │  API Service │   │   Worker Service     │
│  (FastAPI)   │   │  (FastAPI)   │   │   (Celery)           │
│              │   │              │   │                      │
│  All 21      │   │  All 21      │   │  All 21 agents       │
│  agents      │   │  agents      │   │  Scheduled jobs      │
│  Billing     │   │  Billing     │   │  EVI-I refresh       │
│  EVI-I       │   │  EVI-I       │   │  GSIS refresh        │
│  Training    │   │  Training    │   │  WCRS refresh        │
└──────────────┘   └──────────────┘   └──────────────────────┘
        │                                          │
        └─────────────────────┬────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
┌──────────────┐   ┌──────────────┐   ┌──────────────────────┐
│  PostgreSQL  │   │    Redis     │   │  External AI APIs    │
│  + pgvector  │   │              │   │                      │
│              │   │ Sessions     │   │ OpenAI GPT-4         │
│ 26 tables    │   │ Rate limits  │   │ Claude Sonnet 4.6    │
│ Score snaps  │   │ Agent memory │   │ Claude Haiku         │
│ EVI-I snaps  │   │ Credit cache │   │ GPT-4o-mini          │
│ GSIS history │   │ WCRS cache   │   │ Cohere Embeddings    │
│ Training     │   │ GSIS cache   │   │ ElevenLabs (voice)   │
│ Billing      │   │ Celery broker│   │ Pinecone (vectors)   │
│ Embeddings   │   │              │   │ Stripe (billing)     │
└──────────────┘   └──────────────┘   └──────────────────────┘
"""

# ============================================================================
# DOCKER COMPOSE — LOCAL DEVELOPMENT
# ============================================================================

DOCKER_COMPOSE = """
version: '3.8'

services:

  api:
    build:
      context: .
      dockerfile: Dockerfile.api
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://techit:password@postgres:5432/techit_db
      - REDIS_URL=redis://redis:6379
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
      - COHERE_API_KEY=${COHERE_API_KEY}
      - ELEVENLABS_API_KEY=${ELEVENLABS_API_KEY}
      - PINECONE_API_KEY=${PINECONE_API_KEY}
      - PINECONE_INDEX=techit-embeddings
      - STRIPE_SECRET_KEY=${STRIPE_SECRET_KEY}
      - STRIPE_WEBHOOK_SECRET=${STRIPE_WEBHOOK_SECRET}
      - AWS_S3_BUCKET=${AWS_S3_BUCKET}
      - ENVIRONMENT=development
      - SECRET_KEY=${SECRET_KEY}
      - SENTRY_DSN=${SENTRY_DSN}
    depends_on:
      postgres:
        condition: service_healthy
      redis:
        condition: service_healthy
    volumes:
      - ./:/app
    command: uvicorn main:app --host 0.0.0.0 --port 8000 --reload
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/health"]
      interval: 30s
      timeout: 10s
      retries: 3

  worker:
    build:
      context: .
      dockerfile: Dockerfile.worker
    environment:
      - DATABASE_URL=postgresql://techit:password@postgres:5432/techit_db
      - REDIS_URL=redis://redis:6379
      - CELERY_BROKER=redis://redis:6379
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}
      - COHERE_API_KEY=${COHERE_API_KEY}
    depends_on:
      - postgres
      - redis
    command: >
      celery -A workers.celery worker
      --loglevel=info
      --concurrency=4
      -Q default,ai_heavy,ai_light,scheduled
    deploy:
      replicas: 2

  scheduler:
    build:
      context: .
      dockerfile: Dockerfile.worker
    environment:
      - CELERY_BROKER=redis://redis:6379
    depends_on:
      - redis
      - worker
    command: celery -A workers.celery beat --loglevel=info

  postgres:
    image: pgvector/pgvector:pg16
    environment:
      - POSTGRES_USER=techit
      - POSTGRES_PASSWORD=password
      - POSTGRES_DB=techit_db
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./init.sql:/docker-entrypoint-initdb.d/init.sql
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U techit"]
      interval: 10s
      timeout: 5s
      retries: 5

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    command: redis-server --maxmemory 512mb --maxmemory-policy allkeys-lru
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 10s
      retries: 5

  flower:
    build:
      context: .
      dockerfile: Dockerfile.worker
    ports:
      - "5555:5555"
    environment:
      - CELERY_BROKER=redis://redis:6379
    depends_on:
      - redis
    command: celery -A workers.celery flower --port=5555

volumes:
  postgres_data:
  redis_data:
"""

# ============================================================================
# DOCKERFILE — API SERVICE
# ============================================================================

DOCKERFILE_API = """
FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y gcc libpq-dev curl && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["sh", "-c", "alembic upgrade head && uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4"]
"""

# ============================================================================
# REQUIREMENTS.TXT
# ============================================================================

REQUIREMENTS_TXT = """
# Core
fastapi==0.111.0
uvicorn[standard]==0.30.1
pydantic==2.7.4
pydantic-settings==2.3.4

# Database
sqlalchemy==2.0.31
alembic==1.13.2
psycopg2-binary==2.9.9
pgvector==0.3.1

# Cache + Queue
redis==5.0.7
hiredis==3.0.0
celery==5.4.0
flower==2.0.1

# AI
openai==1.35.7
anthropic==0.29.0
cohere==5.5.8
tiktoken==0.7.0

# Vector
pinecone-client==4.1.0

# Billing
stripe==10.3.0

# Storage
boto3==1.34.144

# Voice
elevenlabs==1.3.1

# Auth + Security
python-jose[cryptography]==3.3.0
passlib[bcrypt]==1.7.4
python-multipart==0.0.9

# Utilities
python-dotenv==1.0.1
httpx==0.27.0
structlog==24.2.0
tenacity==8.5.0

# Monitoring
sentry-sdk[fastapi]==2.7.1
prometheus-fastapi-instrumentator==7.0.0

# Testing
pytest==8.2.2
pytest-asyncio==0.23.7
"""

# ============================================================================
# FASTAPI MAIN APPLICATION
# ============================================================================

MAIN_APP = """
from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from contextlib import asynccontextmanager
from typing import Optional, Dict, Any
import structlog
import sentry_sdk

from integration_guide import (
    TechITAIBrain, IncubationHubService, DashboardIntelligenceService,
    WorkspaceAIService, TourGuideService, AdaptiveTrainingService,
    MatchingEngineService, RiskEvaluatorService, InvestorSectionService,
    FeedIntelligenceService, AIProfileService, OrgSphereService,
    MarketReadinessService, AdminMonitorService, HybridBillingService,
    GSISService,
)
from ai_router_core import UserContext, UserRole, SubscriptionTier

logger = structlog.get_logger()
brain  = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global brain
    brain = TechITAIBrain()
    logger.info("techit_ai_brain_ready", agents=21, services=16)
    yield
    logger.info("techit_shutdown")


app = FastAPI(
    title="TechIT AI Incubation Platform",
    version="2.0.0",
    description="AI orchestration layer for the global startup ecosystem",
    lifespan=lifespan,
)

app.add_middleware(GZipMiddleware, minimum_size=500)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://app.techit.io", "https://www.techit.io"],
    allow_credentials=True, allow_methods=["*"], allow_headers=["*"],
)


async def get_user_context(request: Request) -> UserContext:
    # Production: decode JWT → fetch user from DB → build UserContext
    return UserContext(
        user_id="demo_user", role=UserRole.FOUNDER,
        subscription_tier=SubscriptionTier.FOUNDER_PRO, credits_remaining=100,
        project_id=None, project_stage="idea", industry="edtech",
        tech_stack=[], past_feedback=[],
        training_progress={"completion_percentage": 0},
        time_logged_today=0, tasks_completed_week=0,
    )


@app.get("/health")
async def health():
    return {"status": "healthy", "ai_brain": "operational", "version": "2.0.0",
            "agents": 21, "scoring_models": 18}


# ── Incubation Hub ─────────────────────────────────────────────────────────

@app.post("/api/v1/incubation/pipeline/run")
async def run_pipeline(venture_data: dict, user: UserContext = Depends(get_user_context)):
    return await IncubationHubService(brain).run_full_venture_pipeline(user, venture_data)

@app.post("/api/v1/incubation/idea/diagnose")
async def diagnose_idea(idea_data: dict, user: UserContext = Depends(get_user_context)):
    return await IncubationHubService(brain).run_idea_diagnostic(user, idea_data)

@app.post("/api/v1/incubation/unicorn/analyze")
async def unicorn_analyze(venture_data: dict, user: UserContext = Depends(get_user_context)):
    return await IncubationHubService(brain).run_unicorn_analysis(user, venture_data)

@app.post("/api/v1/incubation/business-plan/generate")
async def generate_business_plan(venture_data: dict, user: UserContext = Depends(get_user_context)):
    return await IncubationHubService(brain).generate_business_plan(user, venture_data)

@app.post("/api/v1/incubation/pivot/analyze")
async def pivot_analyze(data: dict, user: UserContext = Depends(get_user_context)):
    return await IncubationHubService(brain).run_pivot_intelligence(
        user, data.get("venture_data", {}), data.get("unicorn_score", 0)
    )


# ── Dashboard ──────────────────────────────────────────────────────────────

@app.get("/api/v1/dashboard/intelligence")
async def dashboard_intelligence(user: UserContext = Depends(get_user_context)):
    return await DashboardIntelligenceService(brain).get_dashboard_intelligence(user)

@app.post("/api/v1/gsis/compute")
async def compute_gsis(scores: dict, user: UserContext = Depends(get_user_context)):
    return await GSISService(brain).compute_with_narrative(user, scores)


# ── Tour Guide ─────────────────────────────────────────────────────────────

@app.post("/api/v1/tour-guide/daily-check-in")
async def daily_check_in(user: UserContext = Depends(get_user_context)):
    return await TourGuideService(brain).daily_check_in(user)


# ── Adaptive Training ──────────────────────────────────────────────────────

@app.post("/api/v1/training/curriculum/generate")
async def generate_curriculum(data: dict, user: UserContext = Depends(get_user_context)):
    svc = AdaptiveTrainingService(brain)
    return await svc.generate_curriculum(
        user,
        hours_available_per_week=data.get("hours_per_week", 8.0),
        learning_pace=data.get("learning_pace", "standard"),
        target_mvp_weeks=data.get("target_mvp_weeks", 0),
        has_technical_skills=data.get("has_technical_skills", False),
    )

@app.post("/api/v1/training/curriculum/adapt")
async def adapt_curriculum(data: dict, user: UserContext = Depends(get_user_context)):
    return await AdaptiveTrainingService(brain).adapt_curriculum(
        user, data.get("trigger_event", ""), data
    )

@app.post("/api/v1/training/progress/update")
async def update_progress(data: dict, user: UserContext = Depends(get_user_context)):
    return await AdaptiveTrainingService(brain).mark_module_complete(
        user, data.get("module_id", ""), data.get("quiz_score")
    )


# ── Matching ───────────────────────────────────────────────────────────────

@app.post("/api/v1/matching/find-collaborators")
async def find_collaborators(criteria: dict, user: UserContext = Depends(get_user_context)):
    return await MatchingEngineService(brain).find_collaborators(user, criteria)


# ── Investor ───────────────────────────────────────────────────────────────

@app.get("/api/v1/investor/deal-flow")
async def deal_flow(user: UserContext = Depends(get_user_context)):
    return await InvestorSectionService(brain).get_deal_flow_ranking(user)

@app.post("/api/v1/investor/evi/{project_id}")
async def investor_evi(project_id: str, startup_data: dict,
                        user: UserContext = Depends(get_user_context)):
    return await InvestorSectionService(brain).get_investor_evi(user, startup_data)


# ── Credits ────────────────────────────────────────────────────────────────

@app.get("/api/v1/credits/summary")
async def credits_summary(user: UserContext = Depends(get_user_context)):
    # Production: fetch UserBillingState from DB
    return {"message": "Credit summary — requires UserBillingState from billing_system.py"}


# ── Stripe Webhook ─────────────────────────────────────────────────────────

@app.post("/api/v1/webhooks/stripe")
async def stripe_webhook(request: Request):
    # Production: verify Stripe signature, handle payment events,
    # update credit_purchases + credit_ledger tables
    return {"received": True}


# ── Idea & Solution Hub ────────────────────────────────────────────────────

@app.post("/api/v1/solutions/problems/submit")
async def submit_problem(body: dict, user: UserContext = Depends(get_user_context)):
    from integration_guide import IdeaSolutionHubService
    return await IdeaSolutionHubService(brain).submit_problem(
        user, body["title"], body["description"], body["category"],
        body.get("location", "Global"), body.get("who_is_affected", ""),
        body.get("current_solutions", []), body.get("urgency", "emerging"),
        body.get("people_affected_millions", 1.0),
    )

@app.get("/api/v1/solutions/problems/board")
async def get_problems_board(limit: int = 20, user: UserContext = Depends(get_user_context)):
    return {"message": "query problem_nodes ordered by priority_score DESC"}

@app.post("/api/v1/solutions/problems/{problem_id}/analyze")
async def analyze_problem(problem_id: str, body: dict, user: UserContext = Depends(get_user_context)):
    from integration_guide import IdeaSolutionHubService
    return await IdeaSolutionHubService(brain).analyze_problem(user, problem_id, body)

@app.get("/api/v1/solutions/problems/discover")
async def discover_problems(region: str = None, limit: int = 20, user: UserContext = Depends(get_user_context)):
    from integration_guide import IdeaSolutionHubService
    return await IdeaSolutionHubService(brain).discover_problems(user, region, limit)

@app.post("/api/v1/solutions/discussions/{thread_id}/convert")
async def convert_discussion(thread_id: str, body: dict, user: UserContext = Depends(get_user_context)):
    from integration_guide import IdeaSolutionHubService
    return await IdeaSolutionHubService(brain).convert_to_solution(
        user, body["problem_id"], body["title"], body["solution_type"],
        body["funding_type"], body["description"], body.get("discussion_summary", ""),
    )

@app.post("/api/v1/solutions/deployments/create")
async def create_deployment(body: dict, user: UserContext = Depends(get_user_context)):
    from integration_guide import IdeaSolutionHubService
    return await IdeaSolutionHubService(brain).create_deployment(
        user, body["solution_id"], body, body["mode"],
        body["region"], body.get("beneficiaries_target", 0),
    )

@app.post("/api/v1/solutions/deployments/{deployment_id}/feedback")
async def submit_feedback(deployment_id: str, body: dict, user: UserContext = Depends(get_user_context)):
    from integration_guide import IdeaSolutionHubService
    return await IdeaSolutionHubService(brain).submit_field_feedback(
        user, deployment_id, body["solution_id"], body["field_report"],
        body.get("impact_metrics", {}), body.get("failure_points", []),
    )

@app.post("/api/v1/solutions/grants/generate")
async def generate_grant(body: dict, user: UserContext = Depends(get_user_context)):
    from integration_guide import IdeaSolutionHubService
    return await IdeaSolutionHubService(brain).generate_grant_application(
        user, body["solution_id"], body,
        body["funder_name"], body["funding_type"], body["amount_usd"],
    )

@app.get("/api/v1/solutions/impact/global")
async def global_impact(user: UserContext = Depends(get_user_context)):
    from integration_guide import IdeaSolutionHubService
    return IdeaSolutionHubService(brain).get_global_impact_dashboard(0, 0, 0, 0, [], 0)


# ── Document Generation Engine ─────────────────────────────────────────────

@app.get("/api/v1/documents/templates")
async def get_doc_templates(user: UserContext = Depends(get_user_context)):
    from integration_guide import DocumentGenerationService
    return DocumentGenerationService(brain).get_available_templates()

@app.post("/api/v1/documents/generate")
async def generate_document(body: dict, user: UserContext = Depends(get_user_context)):
    from integration_guide import DocumentGenerationService
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

@app.post("/api/v1/documents/investor-pack")
async def investor_pack(body: dict, user: UserContext = Depends(get_user_context)):
    from integration_guide import DocumentGenerationService
    return await DocumentGenerationService(brain).generate_investor_pack(
        user, body["project_id"],
        body.get("startup_data", {}), body.get("analysis_results", {}),
    )

@app.post("/api/v1/documents/{document_id}/edit")
async def edit_document(document_id: str, body: dict, user: UserContext = Depends(get_user_context)):
    from integration_guide import DocumentGenerationService
    return await DocumentGenerationService(brain).edit_with_ai(
        user, document_id, body["current_content"],
        body["edit_instruction"], body.get("section"),
    )

@app.post("/api/v1/documents/{document_id}/share")
async def share_document(document_id: str, body: dict, user: UserContext = Depends(get_user_context)):
    from integration_guide import DocumentGenerationService
    return await DocumentGenerationService(brain).share_document(
        user, document_id, body.get("expiry_days", 30),
    )
"""

# ============================================================================
# CELERY WORKERS
# ============================================================================

CELERY_WORKERS = """
from celery import Celery
from celery.schedules import crontab
import asyncio
import structlog

logger = structlog.get_logger()

celery = Celery("techit_workers",
                broker="redis://redis:6379",
                backend="redis://redis:6379")

celery.conf.update(
    task_serializer="json", accept_content=["json"],
    result_serializer="json", timezone="UTC", enable_utc=True,
    task_routes={
        "workers.ai_heavy.*": {"queue": "ai_heavy"},
        "workers.ai_light.*": {"queue": "ai_light"},
        "workers.scheduled.*": {"queue": "scheduled"},
    },
)


@celery.task(name="daily_tour_guide")
def daily_tour_guide():
    \"\"\"Daily Tour Guide for all active users. 06:00.\"\"\"
    from integration_guide import TechITAIBrain, TourGuideService
    brain = TechITAIBrain()
    svc   = TourGuideService(brain)
    for user in _fetch_active_users():
        asyncio.run(svc.daily_check_in(user))


@celery.task(name="weekly_summaries")
def weekly_summaries():
    \"\"\"Weekly Tour Guide summaries. Sunday 18:00.\"\"\"
    from integration_guide import TechITAIBrain, TourGuideService
    brain = TechITAIBrain()
    svc   = TourGuideService(brain)
    for user in _fetch_active_users():
        asyncio.run(svc.weekly_summary(user, _fetch_week_activity(user.user_id)))


@celery.task(name="daily_investor_signals")
def daily_investor_signals():
    \"\"\"EVI-I + investor signals for all active startups. Daily 00:00.\"\"\"
    from integration_guide import TechITAIBrain, InvestorSectionService
    brain = TechITAIBrain()
    svc   = InvestorSectionService(brain)
    for startup in _fetch_active_startups():
        ctx = _build_system_context(startup["owner_id"])
        asyncio.run(svc.analyze_investor_signals(ctx, startup))


@celery.task(name="adaptive_curriculum_weekly")
def generate_curricula_weekly():
    \"\"\"Adaptive curriculum for new users. Monday 02:00.\"\"\"
    from integration_guide import TechITAIBrain, AdaptiveTrainingService
    brain = TechITAIBrain()
    svc   = AdaptiveTrainingService(brain)
    for user in _fetch_users_without_curriculum():
        asyncio.run(svc.generate_curriculum(user))


@celery.task(name="wcrs_gsis_refresh")
def refresh_wcrs_gsis():
    \"\"\"Refresh WCRS + GSIS for all active projects. Every 30 minutes.\"\"\"
    from ai_router_core import ScoringEngine
    for project in _fetch_all_projects_with_scores():
        wcrs = ScoringEngine.compute_wcrs(
            market_readiness=project.get("mrs", 0),
            execution_velocity=project.get("evi", 0),
            beta_satisfaction=project.get("bss", 0),
            revenue_growth_signal=project.get("rgs", 0),
            compliance_score=project.get("cs", 0),
            transparency_score=project.get("ts", 0),
            founder_reliability_score=project.get("frs", 0),
            quality_flags=project.get("quality_flags", 0),
            days_since_last_update=project.get("days_since_update", 0),
        )
        gsis = ScoringEngine.compute_gsis(
            product_progress_score=project.get("pps", 0),
            execution_velocity_index=project.get("evi", 0),
            market_readiness_score=project.get("mrs", 0),
            beta_satisfaction_score=project.get("bss", 0),
            revenue_growth_signal=project.get("rgs", 0),
            founder_reputation_score=project.get("frs", 0),
            community_influence_score=project.get("cis", 0),
            investor_interest_score=project.get("iis", 0),
            compliance_score=project.get("cs", 0),
        )
        _update_project_scores(project["id"], wcrs["adjusted_score"], gsis["gsis"],
                                wcrs["decay_factor"])


@celery.task(name="stagnation_roster")
def check_stagnation():
    \"\"\"Flag stagnating projects. Daily 07:00.\"\"\"
    from integration_guide import TechITAIBrain, AdminMonitorService
    brain = TechITAIBrain()
    svc   = AdminMonitorService(brain)
    ctx   = _build_admin_context()
    result = asyncio.run(svc.check_stagnation_roster(ctx, _fetch_all_projects()))
    for p in result["stagnating_list"]:
        _send_reengagement_notification(p["owner_id"], p["project_name"], p["days_inactive"])
    logger.info("stagnation_checked", stagnating=result["stagnating_count"])


@celery.task(name="monthly_credit_reset")
def reset_monthly_credits():
    \"\"\"Reset subscription credit allocations. 1st of month 00:00.\"\"\"
    from ai_router_core import CreditCost, SubscriptionTier
    from billing_system import BillingEventType
    for user in _fetch_all_active_users():
        new_credits = CreditCost.monthly_allocation(user.subscription_tier)
        _reset_user_credits(user.user_id, new_credits)
        _log_billing_event(user.user_id, BillingEventType.CREDITS_RESET_MONTHLY, new_credits)


@celery.task(name="admin_anomaly_scan")
def admin_anomaly_scan():
    \"\"\"Anomaly detection. Every 15 minutes.\"\"\"
    from integration_guide import TechITAIBrain, AdminMonitorService
    brain   = TechITAIBrain()
    svc     = AdminMonitorService(brain)
    ctx     = _build_admin_context()
    signals = _fetch_recent_anomaly_signals()
    asyncio.run(svc.run_anomaly_scan(ctx, signals))


@celery.task(name="investor_alert_check")
def investor_alert_check():
    \"\"\"Watchlist threshold alerts. Every 5 minutes.\"\"\"
    # Check investor_watchlist against current gsis_score + evi_i_score
    # Fire investor_alerts for any threshold crossings
    pass


# ── Celery Beat Schedule ────────────────────────────────────────────────────

celery.conf.beat_schedule = {
    "daily-tour-guide":          {"task": "daily_tour_guide",          "schedule": crontab(hour=6,  minute=0)},
    "weekly-summaries":          {"task": "weekly_summaries",          "schedule": crontab(hour=18, minute=0, day_of_week=0)},
    "daily-investor-signals":    {"task": "daily_investor_signals",    "schedule": crontab(hour=0,  minute=0)},
    "adaptive-curriculum":       {"task": "adaptive_curriculum_weekly","schedule": crontab(hour=2,  minute=0, day_of_week=1)},
    "wcrs-gsis-refresh":         {"task": "wcrs_gsis_refresh",         "schedule": crontab(minute="*/30")},
    "stagnation-roster":         {"task": "stagnation_roster",         "schedule": crontab(hour=7,  minute=0)},
    "monthly-credit-reset":      {"task": "monthly_credit_reset",      "schedule": crontab(hour=0,  minute=0, day_of_month=1)},
    "admin-anomaly-scan":        {"task": "admin_anomaly_scan",        "schedule": crontab(minute="*/15")},
    "investor-alert-check":      {"task": "investor_alert_check",      "schedule": crontab(minute="*/5")},
    # Idea & Solution Hub + Document Generation
    "problem-discovery-daily":   {"task": "problem_discovery_daily",      "schedule": crontab(hour=6,  minute=0)},
    "discussion-moderation":     {"task": "discussion_moderation_hourly", "schedule": crontab(minute=0)},
    "deployment-status-refresh": {"task": "deployment_status_refresh",    "schedule": crontab(minute="*/15")},
    "document-cleanup-weekly":   {"task": "document_cleanup_weekly",      "schedule": crontab(hour=3,  minute=0, day_of_week=0)},
    "impact-snapshot-daily":     {"task": "impact_snapshot_daily",        "schedule": crontab(hour=1,  minute=0)},
}




@celery.task(name="problem_discovery_daily")
def problem_discovery_daily():
    # Auto-discover problems from external data signals. Runs daily at 6 AM.
    # In production: call ProblemDiscoveryEngine for each global region
    # INSERT discovered problems into problem_nodes table for human review
    pass


@celery.task(name="discussion_moderation_hourly")
def discussion_moderation_hourly():
    # Moderate active problem discussion threads. Runs every hour.
    # Fetch discussion_threads updated in last 2 hours
    # Run DiscussionModeratorAgent — update ai_summary, clusters, readiness
    pass


@celery.task(name="deployment_status_refresh")
def deployment_status_refresh():
    # Refresh deployment status and beneficiary counts. Runs every 15 minutes.
    # Fetch active solution_deployments, update beneficiaries_reached
    # from latest field_feedback rows, create impact_snapshots
    pass


@celery.task(name="document_cleanup_weekly")
def document_cleanup_weekly():
    # Archive expired document share links. Runs weekly on Sunday at 3 AM.
    # UPDATE document_exports SET is_shareable = false
    # WHERE expires_at < NOW() AND is_shareable = true
    pass


@celery.task(name="impact_snapshot_daily")
def impact_snapshot_daily():
    # Snapshot impact scores for all active deployments. Runs daily at 1 AM.
    # For each active SolutionDeployment: compute ImpactScore
    # INSERT INTO impact_snapshots with latest metrics
    pass


# ── Helpers ─────────────────────────────────────────────────────────────────
def _fetch_active_users():         return []
def _fetch_week_activity(uid):     return {}
def _fetch_active_startups():      return []
def _fetch_all_projects():         return []
def _fetch_all_projects_with_scores(): return []
def _fetch_users_without_curriculum(): return []
def _fetch_recent_anomaly_signals(): return []
def _fetch_all_active_users():     return []
def _update_project_scores(pid, wcrs, gsis, decay): pass
def _reset_user_credits(uid, n):   pass
def _log_billing_event(uid, etype, n): pass
def _send_reengagement_notification(uid, name, days): pass
def _build_system_context(uid):    return None
def _build_admin_context():        return None
"""

# ============================================================================
# DATABASE INIT SQL
# ============================================================================

INIT_SQL = """
-- Extensions
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS pg_trgm;

-- pgvector indexes for semantic search
CREATE INDEX IF NOT EXISTS idx_user_skill_vec
    ON user_skill_embeddings USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

CREATE INDEX IF NOT EXISTS idx_idea_vec
    ON idea_embeddings USING ivfflat (embedding vector_cosine_ops)
    WITH (lists = 100);

-- Marketplace ranking function (GSIS + WCRS)
CREATE OR REPLACE FUNCTION top_startups(
    p_limit       int     DEFAULT 20,
    p_industry    text    DEFAULT NULL,
    p_stage       text    DEFAULT NULL,
    p_min_gsis    float   DEFAULT 0
)
RETURNS TABLE (
    project_id         uuid,
    title              text,
    industry           text,
    stage              text,
    gsis_score         float,
    wcrs_score         float,
    decay_factor       float,
    unicorn_score      float,
    investment_score   float,
    evi_i_score        float
) LANGUAGE sql STABLE AS $$
    SELECT p.id, p.title, p.industry, p.stage::text,
           p.gsis_score, p.wcrs_score, p.decay_factor,
           p.unicorn_potential_score, p.investment_score, p.evi_i_score
    FROM projects p
    WHERE p.gsis_score >= p_min_gsis
      AND (p_industry IS NULL OR p.industry = p_industry)
      AND (p_stage    IS NULL OR p.stage::text = p_stage)
    ORDER BY p.gsis_score DESC, p.wcrs_score DESC
    LIMIT p_limit;
$$;

-- IP leak detection (pgvector cosine similarity)
CREATE OR REPLACE FUNCTION find_similar_ideas(
    query_embedding vector(1536),
    threshold       float DEFAULT 0.90,
    max_results     int   DEFAULT 10
)
RETURNS TABLE (project_id uuid, title text, similarity float)
LANGUAGE sql STABLE AS $$
    SELECT ie.project_id, p.title,
           1 - (ie.embedding <=> query_embedding) AS similarity
    FROM idea_embeddings ie
    JOIN projects p ON p.id = ie.project_id
    WHERE ie.leak_detection_enabled = true
      AND 1 - (ie.embedding <=> query_embedding) >= threshold
    ORDER BY ie.embedding <=> query_embedding
    LIMIT max_results;
$$;

-- Skill matching (vector similarity for matching engine)
CREATE OR REPLACE FUNCTION find_skill_matches(
    query_embedding vector(1536),
    threshold       float DEFAULT 0.70,
    max_results     int   DEFAULT 20
)
RETURNS TABLE (user_id uuid, similarity float)
LANGUAGE sql STABLE AS $$
    SELECT ue.user_id,
           1 - (ue.embedding <=> query_embedding) AS similarity
    FROM user_skill_embeddings ue
    WHERE 1 - (ue.embedding <=> query_embedding) >= threshold
    ORDER BY ue.embedding <=> query_embedding
    LIMIT max_results;
$$;

-- Live score view (decay recomputed on read)
CREATE OR REPLACE VIEW project_scores_live AS
SELECT
    p.id, p.title, p.stage, p.industry,
    p.gsis_score, p.wcrs_score, p.unicorn_potential_score,
    p.investment_score, p.evi_i_score,
    p.days_since_update,
    EXP(-0.02 * p.days_since_update) AS live_decay_factor,
    p.wcrs_score * EXP(-0.02 * p.days_since_update) AS live_adjusted_score,
    p.gsis_score * EXP(-0.02 * p.days_since_update) AS live_gsis_adjusted
FROM projects p;

-- Monthly credit burn view
CREATE OR REPLACE VIEW monthly_credit_burn AS
SELECT
    u.id AS user_id, u.subscription_tier,
    u.subscription_credits_remaining,
    u.payg_credits_balance,
    COUNT(cl.id) AS transactions_this_month,
    SUM(ABS(cl.credits_delta)) FILTER (WHERE cl.event_type = 'credits_deducted')
        AS credits_consumed,
    SUM(cl.usd_charged_payg) AS payg_usd_spent
FROM users u
LEFT JOIN credit_ledger cl
    ON cl.user_id = u.id
    AND cl.created_at >= date_trunc('month', NOW())
GROUP BY u.id, u.subscription_tier,
         u.subscription_credits_remaining, u.payg_credits_balance;

-- Stagnation view
CREATE OR REPLACE VIEW stagnating_projects AS
SELECT p.id, p.title, p.owner_id, p.days_since_update,
       p.decay_factor,
       ROUND((1 - p.decay_factor) * 100, 1) AS score_penalty_pct,
       p.gsis_score, p.wcrs_score
FROM projects p
WHERE p.decay_factor < 0.70
  AND p.stage NOT IN ('scale')
ORDER BY p.decay_factor ASC;
"""

# ============================================================================
# ENVIRONMENT TEMPLATE
# ============================================================================

ENV_TEMPLATE = """
# Database
DATABASE_URL=postgresql://techit:password@localhost:5432/techit_db
REDIS_URL=redis://localhost:6379

# AI APIs (required)
OPENAI_API_KEY=sk-YOUR_KEY_HERE
ANTHROPIC_API_KEY=sk-ant-YOUR_KEY_HERE

# AI APIs (optional)
COHERE_API_KEY=YOUR_KEY_HERE
PINECONE_API_KEY=YOUR_KEY_HERE
PINECONE_INDEX=techit-embeddings
PINECONE_ENV=us-east-1-aws

# Billing
STRIPE_SECRET_KEY=sk_YOUR_KEY_HERE
STRIPE_WEBHOOK_SECRET=whsec_YOUR_KEY_HERE

# Voice (optional)
ELEVENLABS_API_KEY=YOUR_KEY_HERE

# AWS (optional — for S3 audio/document storage)
AWS_ACCESS_KEY_ID=YOUR_KEY_HERE
AWS_SECRET_ACCESS_KEY=YOUR_KEY_HERE
AWS_REGION=us-east-1
AWS_S3_BUCKET=techit-assets-dev

# Application
ENVIRONMENT=development
DEBUG=True
SECRET_KEY=change-this-to-a-256-bit-random-string
ALLOWED_ORIGINS=http://localhost:3000,http://localhost:8000

# Monitoring
SENTRY_DSN=
"""

# ============================================================================
# KUBERNETES MANIFEST
# ============================================================================

K8S_MANIFEST = """
# API Deployment
apiVersion: apps/v1
kind: Deployment
metadata:
  name: techit-api
  labels:
    app: techit-api
spec:
  replicas: 3
  selector:
    matchLabels:
      app: techit-api
  template:
    metadata:
      labels:
        app: techit-api
    spec:
      containers:
      - name: api
        image: techit/api:latest
        ports:
        - containerPort: 8000
        env:
        - name: DATABASE_URL
          valueFrom:
            secretKeyRef:
              name: techit-secrets
              key: database-url
        - name: OPENAI_API_KEY
          valueFrom:
            secretKeyRef:
              name: techit-secrets
              key: openai-api-key
        - name: ANTHROPIC_API_KEY
          valueFrom:
            secretKeyRef:
              name: techit-secrets
              key: anthropic-api-key
        - name: REDIS_URL
          value: "redis://techit-redis:6379"
        resources:
          requests:
            memory: "512Mi"
            cpu: "500m"
          limits:
            memory: "1Gi"
            cpu: "1000m"
        livenessProbe:
          httpGet:
            path: /health
            port: 8000
          initialDelaySeconds: 30
          periodSeconds: 10
---
apiVersion: v1
kind: Service
metadata:
  name: techit-api
spec:
  selector:
    app: techit-api
  ports:
  - port: 80
    targetPort: 8000
  type: LoadBalancer
---
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: techit-api-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: techit-api
  minReplicas: 3
  maxReplicas: 20
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
"""

# ============================================================================
# COST MODEL
# ============================================================================

COST_MODEL = """
TECHIT INFRASTRUCTURE COST MODEL
==================================

AI Model Costs (per 1M tokens)
──────────────────────────────
GPT-4 Turbo              $10.00  → Unicorn eval, code review, strategy, EVI-I
Claude Sonnet 4.6         $3.00  → Business plans, summaries, investor reports
GPT-4o-mini               $0.20  → Tour guide, chat, dashboard, GSIS narration
Claude Haiku              $0.25  → Matching, profile analysis, admin monitor
Cohere Embeddings         $0.10  → All semantic search operations

Per-User Monthly Cost (Founder Pro, active)
────────────────────────────────────────────
Daily Tour Guide ×30              $0.30
Weekly Summary ×4                 $0.20
Idea / Unicorn Evaluation ×2      $0.40
Business Plan ×1                  $0.40
Market Intelligence ×2            $0.40
GSIS Compute (daily)              $0.10
EVI-I Signal ×2                   $0.20
Adaptive Training Curriculum ×1   $0.15
Matching ×3                       $0.06
Dashboard / Chat (unlimited)      $0.10
TOTAL                           ~$2.31/month

Infrastructure at 10,000 active users
──────────────────────────────────────
PostgreSQL (RDS r7g.large)        $180/month
Redis (ElastiCache r7g.medium)    $80/month
API servers (3× c6a.xlarge)       $180/month
Worker servers (4× c6a.2xlarge)   $280/month
S3 + CloudFront                   $30/month
Monitoring stack                  $50/month
TOTAL                            $800/month

AI costs at 10K active users     ~$20,100/month
Grand total at 10K users         ~$20,900/month

Revenue at 10K users (blended)
───────────────────────────────
30% Free             →      $0
50% Founder Pro @$49 → $245,000
15% Investor @$199   → $298,500
5%  Enterprise @$999 →  $49,950
MRR                  $593,450
Gross Margin         ~96.5%

Cost Optimisation Levers
─────────────────────────
1. Aggressive Redis caching             → 40% AI call reduction
2. Prompt compression and batching      → 20% token reduction
3. Free tier always routed to Haiku     → 85% cost reduction for free users
4. Credit economy                       → users self-regulate consumption
5. GSIS/WCRS computed deterministically → only narration costs credits
6. Embeddings cached permanently        → never recomputed
"""

# ============================================================================
# DEPLOYMENT CHECKLIST
# ============================================================================

DEPLOYMENT_CHECKLIST = """
TECHIT — PRODUCTION DEPLOYMENT CHECKLIST
==========================================

□ INFRASTRUCTURE
  □ PostgreSQL 16 with pgvector, uuid-ossp, pg_trgm extensions
  □ Redis 7 cluster with maxmemory and eviction policy set
  □ S3 bucket for audio and document storage
  □ Load balancer with health checks
  □ Auto-scaling: API 3–20 pods, Workers 2–8 pods

□ DATABASE
  □ alembic upgrade head — all 26 tables created
  □ All pgvector indexes created (user_skill, idea_embeddings)
  □ Stored functions deployed (top_startups, find_similar_ideas, find_skill_matches)
  □ Views created (project_scores_live, monthly_credit_burn, stagnating_projects)
  □ ai_prompts seeded with all 20+ versioned prompt templates

□ API KEYS (AWS Secrets Manager — never in .env files in production)
  □ OpenAI (GPT-4 + GPT-4o-mini)
  □ Anthropic (Claude Sonnet 4.6 + Haiku)
  □ Cohere (embeddings)
  □ Pinecone (vector search at scale)
  □ ElevenLabs (Tour Guide audio briefings)
  □ Stripe (subscription billing + PAYG purchases + webhooks)

□ BILLING SYSTEM
  □ Stripe products and prices created for all 11 plans
  □ Stripe webhook endpoint configured and verified
  □ Monthly credit reset cron verified
  □ Paywall hit logging verified end-to-end
  □ PAYG overflow resolution tested (subscription_credits → payg_credits)

□ CELERY
  □ All 14 scheduled tasks registered in beat_schedule
  □ All 4 queues active (default, ai_heavy, ai_light, scheduled)
  □ Flower monitoring accessible
  □ Dead letter queue configured

□ AI AGENTS
  □ All 21 agents registered (confirm with orchestrator check)
  □ GSIS compute verified with all 9 component scores
  □ EVI-I investor signal compute verified with decay
  □ Adaptive training curriculum generates for all 3 pace modes
  □ Hybrid credit engine tested: subscription-first, then PAYG overflow

□ SECURITY
  □ DEBUG=False in production
  □ SECRET_KEY is cryptographically random (256-bit)
  □ CORS restricted to techit.io domains only
  □ JWT authentication on all API routes
  □ Rate limiting active in Redis per user per hour
  □ Prompt injection detection verified (SafetyEngine tests pass)
  □ IP fingerprinting working for idea submissions

□ MONITORING
  □ Sentry live and receiving test events
  □ Prometheus metrics scraping active
  □ Grafana dashboards: AI costs, agent success rates, GSIS trends,
    credit burn rates, paywall conversion, EVI-I distributions
  □ Alerts configured:
    - API error rate > 5%
    - Agent failure rate > 10%
    - User monthly AI cost > $10
    - Single request > $0.50
    - Decay roster > 20% of active projects stagnating
    - Credit balance goes negative (bug indicator)
    - Stripe webhook failures

□ FINAL SMOKE TESTS
  □ POST /api/v1/incubation/idea/diagnose → returns structured profile
  □ POST /api/v1/training/curriculum/generate → returns adaptive curriculum with weeks
  □ POST /api/v1/tour-guide/daily-check-in → returns momentum + decay
  □ GET  /api/v1/dashboard/intelligence → returns GSIS score card
  □ POST /api/v1/gsis/compute → returns GSIS with narrative
  □ POST /api/v1/investor/evi/{id} → returns EVI-I 6-dimension signal
  □ Full venture pipeline test (12 credits) completes without error
  □ Paywall fires correctly for Free user on business_plan operation
  □ PAYG overflow: subscription credits → payg credits with correct USD charge
"""


if __name__ == "__main__":
    print("""
╔═══════════════════════════════════════════════════════════════╗
║       TECHIT AI ROUTER v2.0 — DEPLOYMENT ARCHITECTURE        ║
╠═══════════════════════════════════════════════════════════════╣
║  Quick Start:                                                 ║
║    1. cp .env.example .env  →  fill in API keys               ║
║    2. docker-compose up -d                                    ║
║    3. docker-compose exec api alembic upgrade head            ║
║    4. curl http://localhost:8000/health                       ║
║    5. Flower: http://localhost:5555                           ║
║                                                               ║
║  21 agents  |  18 scoring models  |  16 service classes      ║
║  11 plans   |  9 cron jobs        |  26 DB tables             ║
║                                                               ║
║  Cost at 10K users: ~$20,900/month                           ║
║  Revenue at 10K users: ~$593,450 MRR (96.5% gross margin)    ║
╚═══════════════════════════════════════════════════════════════╝
""")
    print(COST_MODEL)
