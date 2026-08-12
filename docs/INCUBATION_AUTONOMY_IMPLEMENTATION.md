# Incubation Autonomy Upgrade — Eight-Phase Implementation

Date: 2026-08-12

## Operating boundary

The AI Router remains execution-only. It contains no customer billing, credits,
subscriptions, payment gateway, paywall, or customer-price logic. Provider cost
metadata is infrastructure telemetry only.

AI autonomy is capped at 60%. The AI may ask questions, research, challenge
claims, calculate provisional scores, draft roadmaps/tasks and generate private
sandbox artifacts. Humans alone approve validation, assumptions, geography,
pivots, MVP scope, committed roadmaps, repository creation, deployments,
publishing, external outreach, spending and production changes.

## Phase 1 — contracts and wiring

- Added dedicated finance, feasibility, tech-stack, SWOT, impact, roadmap,
  survey, recommendation, PMF, monetization and market-intelligence routes.
- Corrected all 16 Incubation Hub frontend mode mappings.
- Fixed architecture propagation into scaffold generation.
- Persisted the generated scaffold in the compiled blueprint.

## Phase 2 — founder questioning and evidence

- Added Founder Interrogation, Evidence Research, PMF Validation, Geographic
  Intelligence and MVP Build Planner agents.
- Added structured prompts that separate fact, founder claim, assumption and
  inference and require contradictory evidence and failure research.
- Added versioned incubation sessions, founder answers and immutable human
  decision events.

## Phase 3 — evidence-backed scoring

- Removed static Unicorn driver scores.
- Driver scores now derive from submitted evidence, include confidence and
  evidence provenance, and remain provisional pending human review.

## Phase 4 — workspace context

- Added versioned WorkspaceContextPack persistence.
- Automatically creates an idempotent private workspace after incubation.
- Automatically injects venture, answers, evidence, assumptions, decisions,
  roadmap, tasks, milestones and artifacts into workspace AI calls.

## Phase 5 — constrained MVP planning

- Added one-day prototype, three-day demo, one-week MVP and two-to-six-week
  production-MVP plans.
- Plans include code structure, exclusions, tests, acceptance criteria and
  founder constraints. Humans finalize the selected scope.

## Phase 6 — sandbox and deployment controls

- Added private sandbox artifact creation with compile, interaction, secret,
  dependency and basic security scans.
- Added protected ZIP/preview access, artifact hashes and rollback versions.
- External repository creation and preview deployment require explicit human
  approvals and a restricted signed deployment broker/GitHub App.
- Personal GitHub tokens are forbidden.

## Phase 7 — routing maturity

- Added deterministic task-complexity assessment.
- Added bounded runtime feedback, configurable canaries, disabled-model rollback
  control and quality-floor preservation.
- Users can select eligible models; unsupported selections are rejected rather
  than silently downgraded.

## Phase 8 — human-in-the-loop frontend and release gates

- Added founder questions, evidence, contradictions, geography, provisional PMF,
  MVP scope, decisions, sandbox and preview controls to Main and Fast Track.
- Added a dedicated Workspace AI Copilot distinct from Team Chat.
- Copilot automatically loads workspace context and surfaces approval notices
  for consequential intents without executing them.
- Added API, persistence, routing, sandbox and context-injection regression tests.

## Deployment synchronization required

1. Apply Alembic head `2b3c4d5e6f7a`.
2. Configure production provider keys and signed backend execution grants.
3. Configure `SANDBOX_ARTIFACT_ROOT` on durable private storage or replace local
   artifact storage with object storage.
4. Configure `DEPLOYMENT_BROKER_URL` and `DEPLOYMENT_BROKER_SECRET` for a
   restricted GitHub App/deployment broker; never pass personal tokens.
5. Forward authenticated workspace/project IDs and authorization grants from the
   platform backend.
6. Keep backend authorization as the source of truth for all human approval and
   external-action permissions.
7. Deploy Router and frontend together because the new UI depends on new API
   contracts.
8. Verify real provider, database, object-storage, broker, preview-health and
   rollback integrations in staging before production rollout.

## Verification

- AI Router release gates: passed.
- Backend tests: 103 passed.
- Frontend tests: 151 passed.
- Frontend TypeScript production build: passed.
- Alembic graph: one head.
- Secret scan: no GitHub token or private key found in changed source files.

