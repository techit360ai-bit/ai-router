# GSIS v2 Stage-Aware Startup Intelligence Engine

Status: Phases 1-2 vertical slice complete; Phases 3-4 pending

Plan commit: create this document before code changes so work can resume safely in a new context window.

## Product constraints

- Keep one canonical deterministic GSIS engine. AI may interpret evidence and generate narrative, but must not invent metrics or scores.
- Preserve the legacy GSIS formula and historical score fields. New evaluations use an explicitly versioned GSIS v2 scorecard.
- Add only focused founder-dashboard intelligence panels. Do not redesign the founder dashboard, navigation, density, color system, or overall operating philosophy.
- Expand Deal Intelligence with investor-oriented GSIS signals and evidence. Do not make an investment decision for the investor.
- Feed consumers receive only the compact score, stage, and momentum projection. Sensitive evidence, risks, and recommendations must not be present in that payload.
- Missing evidence is `UNKNOWN`, not zero. All scorecards expose confidence, coverage, evidence provenance, freshness, and model version.

## Existing implementation inventory

### AI router (`ai-router`)

- `ai_router_core.py::ScoringEngine.compute_gsis` is the legacy universal nine-component score.
- `config/scoring_policies.json` is the versioned configuration registry used by deterministic scoring.
- `policy_registry.py` validates policy identity, normalized weights, freshness, and calibration state.
- `integration_guide.py::GSISService` and `POST /api/v1/gsis/compute` provide the current compute API and optional AI narrative.
- `workers/workers.py::wcrs_gsis_refresh` recalculates legacy GSIS and writes historical snapshots.
- `database_schema.py` already contains project score fields and score snapshots. Legacy history must remain immutable and queryable.
- Existing agents consuming GSIS include Dashboard Intelligence, GSIS Compute, Tour Guide, Risk Evaluator, investor intelligence, and scheduled refresh workers.

### Application backend (`BACKEND/backend`)

- `domainService.js` projects persisted project data into organization health, investor deal flow, readiness, alerts, tasks, milestones, and watchlists.
- `aiRouterClient.js` already routes GSIS narrative calls through the FastAPI AI router.
- `GET /api/domain/investor/deal-flow` is the investor ranking source.
- Projects currently persist scalar `gsisScore`, stage, MRR, progress, readiness, timestamps, workspace state, and related domain collections.

### Product frontend (`new-frontend/frontend`)

- `src/lib/api/gsis.ts` currently exposes only the legacy scalar GSIS contracts.
- Founder `Dashboard.tsx` has a single GSIS card inside an established quiet, light operating dashboard.
- Investor `DealIntelligence.tsx` is a dark, dense ranking/filter surface backed by live domain deal flow.
- Feed components already show compact GSIS badges and must remain compact.
- Founder projects expose current stage, scalar GSIS, project progress, users, revenue, and workspace state; unavailable metrics must remain unknown.

## Target architecture

```text
observations + evidence + model context
                  |
                  v
       deterministic GSIS v2 engine
                  |
      canonical versioned scorecard
                  |
      +-----------+------------+
      |           |            |
   founder     investor       feed
   actions     analysis      compact signal
```

The v2 engine is configuration-driven and implements stage detection, stage-specific scoring, evidence confidence/coverage, momentum, risk, readiness gates, PMF, bottleneck selection, next best action, health classification, and role projections. The initial release accepts observations supplied by existing systems; persistence and background refresh use the same scorecard contract.

## Delivery sequence

### Phase 1: canonical deterministic engine and API

- Extend the scoring policy with versioned BUILD, LAUNCH, and GROWTH models, readiness gates, stage detection rules, evidence levels, freshness rules, stage-aware inactivity decay, risk thresholds, PMF thresholds, and recommendation playbooks.
- Add `ScoringEngine.compute_gsis_v2(payload)` without changing `compute_gsis`.
- Normalize raw observations to 0-100 using configured threshold curves and preserve `UNKNOWN` values.
- Return global score, stage health, declared/detected stage and confidence, momentum, PMF, risk radar, readiness, score components, primary bottleneck, next best action, evidence summaries, confidence, coverage, timestamps, model versions, and legacy linkage.
- Add role projections: founder (actions/readiness/risks), investor (quality/growth/risk/evidence), and feed (score/stage/momentum only).
- Add `POST /api/v2/gsis/scorecard` and `POST /api/v2/gsis/scorecards` batch endpoints. These remain deterministic and do not spend AI execution budget.
- Unit-test stage detection, weighted scores, missing data, confidence, freshness, momentum, gates, PMF, risks, business-model adaptation, role data minimization, and legacy compatibility.

### Phase 2: founder and Deal Intelligence vertical slice

- Extend `src/lib/api/gsis.ts` with typed v2 scorecard and batch contracts.
- Map only real persisted founder/deal-flow fields into observation payloads. Mark absent fields unknown.
- Replace the founder scalar GSIS card with a compact stage-aware operating panel in the same card language and page position. Include GSIS, stage, health, momentum, PMF when applicable, risk, readiness, bottleneck, next action, confidence, and coverage.
- Add investor scorecard signals to Deal Intelligence cards/list rows: GSIS, detected stage, PMF, momentum, risk, readiness, and evidence confidence. Preserve existing filters and ranking behavior until persisted v2 rankings are available.
- Add investor filters for minimum GSIS, stage, PMF, momentum, readiness, risk, and confidence without exposing founder-only actions.
- Keep feed APIs and UI unchanged except for consuming the compact projection when the backend later supplies it.
- Verify typecheck/build and relevant UI tests.

### Phase 3: persistence, closed loop, and background refresh

- Add additive PostgreSQL migrations for versioned profiles, metric definitions/observations, evidence, component scores, risk/readiness assessments, recommendations/outcomes, transitions, and immutable snapshots. Reuse project, user, organization, task, milestone, analytics, and customer entities.
- Add a legacy mapping layer that stores `legacy_gsis` beside new v2 snapshots; never rewrite old snapshots.
- Extend application-backend domain APIs with authorized founder, investor, admin, and feed projections. The feed endpoint must select only compact fields.
- Link accepted next actions to existing task/milestone infrastructure and record recommendation outcomes on task completion.
- Add scheduled/background refresh, snapshot, recommendation, and outcome jobs with latency/failure/score-change telemetry.

### Phase 4: administration, benchmarks, and calibrated prediction

- Add audited admin configuration for weights, thresholds, gates, decay, business models, geography, benchmarks, and confidence requirements.
- Add contextual benchmarks only when reliable datasets exist.
- Add clearly labelled AI estimates for readiness/stagnation predictions; keep probability claims disabled until TechIT outcome data passes calibration gates.

## Initial supported input contract

- Context: startup ID, declared stage, business model, industry, geography, evaluation time, last activity, milestone cadence.
- Evidence: metric key, value, status (`observed`, `derived`, `estimated`, `ai_inferred`, `unknown`), evidence level 1-5, source, observed timestamp, optional previous value/timestamp.
- Stage signals: MVP/product availability, users, customers, revenue/MRR, activation, retention, acquisition repeatability, pilots/design partners, product usage, growth, unit economics, operations, and team size.
- Existing normalized component scores may be supplied as derived observations during migration, with reduced confidence and explicit legacy provenance.

## Verification gates

- Legacy scoring policy tests remain unchanged and passing.
- All v2 policy weights sum to 1.0 and policy/model versions are returned.
- No missing metric is converted to zero.
- Critical readiness gates can block transition even when the aggregate score is high.
- Feed projection contains no evidence, risk radar, recommendations, customer/revenue detail, or component decomposition.
- Founder/investor projections contain only role-appropriate fields.
- Frontend builds successfully and the founder dashboard retains its current layout philosophy.
- Deal Intelligence remains usable when v2 scorecard calculation fails; legacy live deal flow still renders with an explicit unavailable state.

## Resume checklist

1. Read this plan and run `git status --short` in `ai-router`, `BACKEND`, and `new-frontend`.
2. Inspect the latest commits in each repository; do not overwrite unrelated work.
3. Run focused AI-router tests: `pytest -q tests/test_gsis_v2.py tests/test_scoring_policy_registry.py`.
4. Run frontend verification: `npm run build --prefix frontend` from `new-frontend`.
5. Continue from the first incomplete delivery phase and update `Status` plus this checklist when a phase lands.

## Current checkpoint

- Complete: configuration-driven BUILD/LAUNCH/GROWTH models, evidence confidence/freshness, missing-data coverage, stage detection, stage-aware decay, momentum, PMF, risk, readiness gates, bottleneck, next action, health classification, legacy linkage, role projections, and single/batch v2 APIs.
- Complete: founder operating scorecard in the existing dashboard card language, compact Deal Intelligence signals/filters, and the investor startup analysis scorecard.
- Complete: BUILD weights adjusted to Team 10% and Execution 10%.
- Verified: focused AI-router tests and the frontend production build.
- Pending: PostgreSQL persistence/migrations, immutable v2 snapshots, background refresh jobs, recommendation-to-task outcomes, admin configuration UI, contextual benchmarks, and calibrated prediction.
