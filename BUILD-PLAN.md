# TechIT — Dashboard Gap Build Plan (backend side: ai-router)

This branch (`feat/dashboard-backends`) builds the backend capabilities that the
React dashboards (techIT / new-frontend repo) need but the engine did not yet model,
and confirms endpoints for backend capabilities the dashboards will surface.

Paired frontend branch: `feat/dashboard-intelligence` in the `techIT` clone.

## Build constraints (this environment)
- Python 3.12 here; repo pins 3.11.9. `fastapi`/`sqlalchemy` are NOT installed,
  so the app cannot be run/imported here. Validation gate = `python3 -m py_compile`
  (syntax) + strict adherence to existing house patterns + pytest files to run on a
  real machine. State this in each commit; nothing is claimed "runtime-verified".

## House conventions (followed)
- Endpoints: `main.py`, `@app.post("/api/v1/...")`, inject `user: UserContext = Depends(get_user_context)`,
  delegate to a Service in `integration_guide.py`. Services receive `brain` singleton.
- DB models: `database_schema.py` (SQLAlchemy, PostgreSQL + pgvector).
- Scoring: `ai_router_core.py` `ScoringEngine`.
- Credits: `billing_system.py` `CREDIT_OPERATIONS`.
- Many existing endpoints return structured placeholder data with real shapes — that
  is the accepted house style for pre-DB features; new work matches it (real models +
  service methods returning correctly-shaped data, DB wiring marked where needed).

## Epics & status  (✅ done · 🚧 in progress · ⬜ todo)

### Section A — frontend exists, build backend
- ✅ A1 Collaborator Equity/vesting engine — EquityGrant/CapTableEntry/DilutionEvent models, EquityService (holdings/totals/vesting timeline/dilution protection), GET+POST /api/v1/collaborator/equity[/dilution]
- ✅ A2 Collaborator Earnings/payouts — CollaboratorEarning/Payout models, PayoutService (earnings/payouts/totals + withdrawal w/ balance check), GET /collaborator/earnings + POST .../withdraw
- ⬜ A3 Investor Capital Pools — pool/escrow/milestone-release entity
- ⬜ A4 Investor Deal Rooms — cap table, term sheet, e-signature, negotiation workflow
- ⬜ A5 Investor Data Rooms — document vault container + access control + per-investor sharing
- ⬜ A6 Investor Reputation — investor-side scoring, reviews, leaderboard
- ⬜ A7 Investor Global Heatmap — geo/region aggregation signal

### Section B — backend exists, confirm/extend endpoints (frontend surfaces them)
- ⬜ B1 EVI-I/IIS/WCRS deal-flow ranking — confirm endpoints feed Deal Intelligence
- ⬜ B2 GSIS composite — confirm dashboard intelligence + gsis/compute feed founder dashboard
- ⬜ B3 Adaptive Training — confirm curriculum endpoints
- ⬜ B4 Anomaly scan / stagnation roster — ensure endpoints exist
- ⬜ B5 Audio briefing — confirm get_audio_briefing endpoint
- ⬜ B6 Workspace review_code / plan_sprint — confirm endpoints

### Section C — LAST (per user)
- ⬜ C Idea & Solution Hub — backend already exists; FE built last

## Commit discipline
Commit after each coherent slice (model → service → endpoint → credit op). Update the
status box above in the same commit so progress survives session loss.
