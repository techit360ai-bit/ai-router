Hey Devs,

The TECHIT AI Router backend is fully deployed and verified locally. Here is what is done and what you need to do to get running.

WHAT IS READY

• PostgreSQL 16 + pgvector — all tables migrated, extensions active, SQL functions and views deployed

• Redis 7 — sessions, cache, and Celery queue backend live

• FastAPI — AI Brain initialised with 34 agents, 51 task types, 20 scoring models

• Celery Worker — 4 queues running: default, ai_heavy, ai_light, scheduled

• Celery Beat — all 14 scheduled jobs registered

• Flower — Celery task monitor live at http://localhost:5555

• Health endpoint verified: GET /health returns all systems operational

• Swagger docs live at http://localhost:8000/docs

• All deployment blockers resolved and committed to the repo



⚠️ NEEDS YOUR ATTENTION (AI Engineers)

1. AUTH — every endpoint currently runs as demo_user_001 (FOUNDER_PRO). Real JWT auth is stubbed in main.py around line 90. Search for 'Production: uncomment' and complete that block before connecting the frontend.

2. STUB ENDPOINTS — three endpoints return placeholders, not real DB queries:

• GET /api/v1/solutions/problems/board

• GET /api/v1/solutions/impact/global

• GET /api/v1/credits/summary

3. STRIPE WEBHOOK — signature verification is commented out in main.py. Enable before connecting Stripe beyond local.

GETTING STARTED ON YOUR MACHINE

Prerequisites: Docker (Desktop or on CLI) running + API keys for OpenAI and Anthropic at minimum.

git clone https://github.com/techit360ai-bit/ai-router.git

cd techit-ai-router

cp .env .env

# Fill in your API keys

docker compose up -d postgres redis

docker compose run --rm migrate

docker compose up -d

docker compose ps



Verify with:

curl http://localhost:8000/health

# Expected: {"status":"healthy","agents":34,"scoring_models":20}



Swagger: http://localhost:8000/docs

Flower:  http://localhost:5555



⚠️ PORT NOTE — if you have PostgreSQL or Redis installed locally you will hit a port conflict. The compose file maps Postgres to host port 5433 and Redis to 6380 to avoid this. Everything inside Docker still talks on the standard ports.



🔑 MINIMUM API KEYS NEEDED

SECRET_KEY=$(python3 -c "import secrets; print(secrets.token_hex(32))")



POSTGRES_PASSWORD=Techmachine123



OPENAI_API_KEY=sk-...



ANTHROPIC_API_KEY=sk-ant-...