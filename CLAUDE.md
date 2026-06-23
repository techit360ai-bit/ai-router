# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

**Dev server:**
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

**Docker (first-time setup):**
```bash
docker compose up -d postgres redis   # start infra first
docker compose run --rm migrate       # run migrations once
docker compose up -d                  # start everything
docker compose ps                     # verify all services healthy
```

**Docker (subsequent runs):**
```bash
docker-compose up
```

**Migrations:**
```bash
alembic upgrade head          # apply
alembic revision --autogenerate -m "description"  # generate new
```

**Celery worker:**
```bash
celery -A workers.workers worker --loglevel=info -Q ai_heavy,ai_light,scheduled
celery -A workers.workers beat --loglevel=info    # scheduler
celery -A workers.workers flower --port=5555      # monitor UI
```

**Tests:**
```bash
pytest                        # all tests
pytest tests/test_foo.py::test_bar  # single test
pytest -x                     # stop on first failure
```

**Runtime:** Python 3.11.9 (pinned in `runtime.txt`).

## Architecture

The platform is **TechIT AI Incubation Platform v3.0.0** — an AI-native startup incubation system with 34 agents, 51 task types, and 20 scoring models.

### Request flow

```
HTTP request → main.py endpoint
  → get_user_context() (currently stub; production needs JWT + DB lookup)
  → Service class in integration_guide.py (e.g. IncubationHubService)
    → TechITAIBrain singleton (owns ModelRouter, PromptEngine, SafetyEngine, AICommandLayer)
      → AgentOrchestrator → specific Agent(s) in agent_orchestration.py
        → AICommandLayer → LLM API call (OpenAI / Anthropic / Cohere fallback chain)
```

### Key modules

| File | Role |
|------|------|
| `main.py` | FastAPI app entry point. All HTTP endpoints, lifespan, CORS, error handlers. |
| `ai_router_core.py` | **Central source of truth.** All enums (`UserRole`, `SubscriptionTier`, `TaskType`), 20 scoring models, `ModelRouter` (vendor fallback chains), `PromptEngine` (versioned templates), `SafetyEngine`, `AICommandLayer`. |
| `integration_guide.py` | 16 service classes, one per platform section. All receive `TechITAIBrain` via DI. **This is where feature logic lives.** |
| `agent_orchestration.py` | 34 specialist agents + `AgentOrchestrator` + event→agent routing table + `VenturePipeline`. |
| `workers/workers.py` | 14 Celery tasks across 4 queues (`default`, `ai_heavy`, `ai_light`, `scheduled`). Beat schedule included in same file. |
| `database_schema.py` | SQLAlchemy models for all 42 tables (PostgreSQL 16 + pgvector). |
| `billing_system.py` | `CREDIT_OPERATIONS` dict, `HybridCreditEngine`, subscription access control. |
| `document_generation.py` | 8-type document factory (executive summary → pitch deck → business plan, etc.). |
| `idea_solution_hub.py` | Problem-driven pathway: Global Problems Board, solution projects, deployments, impact tracking. |

### TechITAIBrain singleton

`TechITAIBrain` in `integration_guide.py` is a true singleton (Python `__new__`). Initialised once in the FastAPI lifespan. Every service class gets one injected. Never instantiate it directly from a feature module — always receive it as a constructor argument.

### Scoring models (ai_router_core.py)

20 mathematical models live in `ScoringEngine`. The master composite is **GSIS** (Global Startup Intelligence Score). Key ones: `UPS` (unicorn potential, 10 drivers), `EVI` (execution velocity), `EVI-I` (investor-grade EVI), `WCRS` (marketplace ranking), `DecayFactor` (inactivity penalty). All scores are snapshotted to DB for trend analysis.

### Credit economy

Every API operation has a credit cost defined in `billing_system.CREDIT_OPERATIONS`. `SubscriptionAccessControl` in `ai_router_core.py` enforces tier gates (Free → Builder → Founder Pro → Investor → Enterprise). Credit deduction must happen inside the service layer before the LLM call.

### Known stub endpoints

The earlier three stubs (`/api/v1/solutions/problems/board`, `.../impact/global`, `/api/v1/credits/summary`) now run real PostgreSQL queries since commit `dafac33`. Newer stubs may still surface — search for `# Production:` comments to find them.

Stripe webhook signature verification is **enabled** (`stripe.Webhook.construct_event` at `main.py:1443`). `STRIPE_WEBHOOK_SECRET` must be set or the endpoint returns 500. (This note used to say verification was off — it isn't; the code was already updated.)

### Infrastructure (docker-compose.yml)

| Service | Port (host) | Notes |
|---------|-------------|-------|
| FastAPI | 8000 | Dockerfile.api |
| PostgreSQL 16 + pgvector | 5433 | `techit_db`, user `techit` |
| Redis 7 | 6380 | Broker + Celery backend |
| Celery worker | — | 4 queues |
| Celery Beat | — | 14 scheduled tasks |
| Flower | 5555 | Celery monitor |

### Auth

`get_user_context()` in `main.py` decodes the `Authorization: Bearer <jwt>` header with HS256 and the shared platform secret. Order: read `JWT_SECRET` first (canonical, matches BACKEND repo both on `main` and `feat/messaging-backend`), fall back to `SECRET_KEY` (legacy alias) so existing deployments keep booting.

Demo-auth fallback (`ALLOW_DEMO_AUTH=true`) returns a fake Founder Pro user when no token is present. **Forbidden** when `ENVIRONMENT` is `"production"` or `"staging"` — the module-level guardrail at the top of `main.py` raises on import so the service refuses to boot.

Operational fields (credits, team_size, …) are read from the JWT claims today; the production path will hydrate them from PostgreSQL keyed by `sub` (TODO). Dependencies: `python-jose[cryptography]` and `passlib[bcrypt]` are already in `requirements.txt`.

### Agent groups (34 total)

Defined in `Techit Network All Agents Master Prompts (1).md`. The master prompts in that file are the source of truth for each agent's system prompt / behavior.

| Group | Count | Key agents |
|-------|-------|-----------|
| Incubation Hub | 10 | VentureIntake, UnicornEvaluator, MarketIntelligence, ProductFeasibility, StartupStrategy, FinanceStrategy, InvestorIntelligence, BusinessPlanGenerator, TechArchitect, PivotIntelligence |
| Platform | 11 | TourGuide, AdaptiveTraining, Matching, RiskEvaluator, WorkspaceAssistant, FeedIntelligence, DashboardIntelligence, GSISCompute, AIProfile, OrgSphere, AdminMonitor |
| Idea & Solution Hub | 10 | ProblemAnalyzer, SolutionSynthesizer, ImpactPredictor, FeasibilityEstimator, ProblemDiscovery, SolutionMatcher, DeploymentPlanner, GrantMatcher, DiscussionModerator, FieldFeedback |
| Document Generation | 2 | DocumentGeneration, DocumentExport |
| Core Orchestration | 1 | TechITMasterOrchestrator |

### Unicorn evaluation framework

`UNICORN GOLD PROMPT.md` contains the 16-part master prompt that drives `UnicornEvaluatorAgent`. The 10 unicorn drivers scored 0–10 are: Market Size, Problem Severity, Founder Advantage, Technological Defensibility, Scalability, Network Effects, Revenue Model Strength, Market Timing, Competition Landscape, Capital Efficiency. UPS = (total / 100) × 100. Classifications: 0–30 Weak, 30–50 Idea Stage, 50–65 Pre-Aha, 65–75 Early Traction, 75–90 High Potential, 90–100 Unicorn Candidate.

### Environment variables

Minimum required to run locally: `JWT_SECRET` (or legacy `SECRET_KEY`), `POSTGRES_PASSWORD`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`. Generate `JWT_SECRET` with:
```bash
python3 -c "import secrets; print(secrets.token_hex(32))"
```

`JWT_SECRET` must match the value used by BACKEND/main (Node `jsonwebtoken`) and BACKEND/feat/messaging-backend (Go `jwt/v5`) so tokens issued by the platform verify here.

`ENVIRONMENT` defaults to `"development"`. Set to `"staging"` or `"production"` and the demo-auth guardrail will refuse to boot with `ALLOW_DEMO_AUTH=true`.

Full list: `DATABASE_URL`, `REDIS_URL`, `CELERY_BROKER`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `COHERE_API_KEY`, `JWT_SECRET` (alias `SECRET_KEY`), `ENVIRONMENT`, `ALLOW_DEMO_AUTH`, `STRIPE_SECRET_KEY`, `STRIPE_WEBHOOK_SECRET`, `PINECONE_API_KEY`, `AWS_S3_BUCKET`, `SENTRY_DSN`, `ELEVENLABS_API_KEY`, `MCP_BASE_URL`, `MCP_TIMEOUT`.

### Plugin tools via BACKEND (MCP integration)

Tool execution lives on BACKEND repo, branch `feat/plugins-mcp`, mounted at `/api/mcp` on the same Node Express service that serves `/api/auth`. ai-router reaches it through `mcp_client.MCPClient` (`mcp_client.py`).

Auth: pass the END USER'S Bearer token to every client call; the client forwards it as-is. BACKEND verifies with the same `JWT_SECRET` this service uses, so role enforcement happens there using the user's authenticated identity — no service-to-service token, no shared SA.

```python
from mcp_client import get_mcp_client
client = get_mcp_client()
tools = await client.list_tools(user_token=ctx.bearer)
result = await client.invoke('github', 'list_repositories', {}, user_token=ctx.bearer)
```

Environment: `MCP_BASE_URL` (defaults to `http://localhost:3000/api/mcp`), `MCP_TIMEOUT` seconds (default 10).
