# AI Router Production Hardening Plan

Status: implementation complete; production calibration approval awaits real labeled outcomes
Branch: `hardening/ai-router-production-readiness-2026-08-14`
Base: `57224fe` (`security/router-hardening-2026-08-13`)

## Objective

Make production-facing AI Router decisions evidence-based, auditable, and fail-closed. The router may continue to provide AI narratives, but it must not present fabricated people, scores, valuations, deployment artifacts, or probabilities as facts.

## Scope and Order

### P0: block fabricated production decisions

1. **Live collaborator matching**
   - Replace the hard-coded candidates in `agent_orchestration.py` with repository-backed profiles and verified activity signals.
   - Preserve explicit criteria filtering, but return `insufficient_evidence` when no live directory or required profile fields are available.
   - Add provenance for every match field and never expose synthetic names, skills, availability, or trust values.
   - Acceptance: matching tests prove that database records are used, missing records fail closed, and no fixture candidate reaches the API.

2. **Evidence-gated risk analysis**
   - Remove fixed market, feasibility, competitive-risk, and SWOT values.
   - Return model narrative plus structured evidence, confidence, missing fields, and `provisional_human_review_required` status.
   - Acceptance: sparse input cannot produce a numeric risk conclusion or generic SWOT presented as an evaluation.

3. **Evidence-gated investor signals**
   - Remove mid-range defaults for UPS, readiness, growth, MDR, IS, TRV, CEV, and related inputs.
   - Require explicit evidence or mark each dimension unknown; block investment readiness decisions below an evidence threshold.
   - Mark UPS as a heuristic score, not a probability, until calibrated.
   - Acceptance: absent data yields `insufficient_evidence` and reason codes rather than plausible scores.

### P1: make policy and calculations governable

4. **Versioned scoring policy registry**
   - Move weights, thresholds, decay constants, momentum caps, match minimums, valuation multiples, and classification labels to a validated versioned policy document.
   - Include effective date, owner, changelog, and policy id in every score response.
   - Acceptance: changing policy does not require source edits; invalid policy fails startup or request validation.

5. **Calibration and outcome validation**
   - Add an offline evaluation contract and fixtures for matching, GSIS, UPS, EVI-I, investment, risk, and valuation.
   - Track calibration, false-positive/false-negative rates, score drift, and outcome coverage before enabling consequential recommendations.
   - Acceptance: CI runs deterministic backtests and rejects probability claims without calibration metadata.

6. **Data quality and fairness controls**
   - Add field-level evidence provenance, freshness, confidence, missing-field reason codes, and human approval gates.
   - Measure ranking exposure and outcome parity for collaborator/investor matching; avoid protected attributes and proxy features.
   - Acceptance: responses expose audit metadata and monitoring events without leaking private profile data.

### P1: harden generated artifacts and routing operations

7. **Scaffold and deployment integrity**
   - Do not return success after parser fallback. Remove fictional download, preview, clone, and deployment URLs.
   - Validate generated JSON against schemas and require real artifact registration before returning links.
   - Acceptance: malformed model output returns a typed failure or provisional result with no deploy action.

8. **Provider registry freshness**
   - Add registry schema/version checks, provider metadata refresh, cost/context-limit freshness, and stale-config alerts.
   - Keep routing objectives configurable, but record the policy and registry versions used for each request.
   - Acceptance: stale or incomplete provider metadata cannot silently drive cost/quality routing.

9. **Prompt and stack selection integrity**
   - Remove the mandatory Next.js/Supabase/Tailwind default from prompts and select stacks only from explicit project requirements or approved configuration.
   - Acceptance: unrelated ventures do not receive an implicit framework choice; generated output records the selection rationale.

10. **Production observability and release gates**
   - Add metrics for insufficient evidence, fabricated-data regressions, policy versions, provider failures, latency/cost, ranking exposure, and human overrides.
   - Keep production runtime checks fail-closed for database, Redis, MCP HTTPS, JWT, provider credentials, execution grants, settlement, and storage.
   - Acceptance: release checks cover P0/P1 contracts and deployment runbook documents remaining manual controls.

## Implementation Result

Items 1–10 are implemented as code and release contracts. Consequential decisions remain human-review-only until database-backed production outcomes meet the configured sample, coverage, false-positive, false-negative, per-domain, and Brier-score thresholds.

## Completed Checkpoints

- `efb0859` — committed this plan and continuation instructions.
- `8875651` — collaborator matching reads persisted `matches`, `users`, and structured skill evidence; empty or untrusted input fails closed. Added `tests/test_matching_evidence.py`.
- `da1a855` — risk and investor outputs require explicit evidence; removed fabricated SWOT/risk/investor defaults; UPS is marked heuristic and uncalibrated. Added `tests/test_decision_evidence_gates.py`.
- `2c92ce1` — scaffold parsing and deployment surfaces fail closed; removed fictional artifact/live URLs and implicit stack defaults. Added `tests/test_scaffold_integrity.py`.
- `86fb0f8` — added validated `config/scoring_policies.json`, production freshness checks, policy-backed GSIS/UPS/EVI-I/investment/match/decay/valuation inputs, and policy metadata on score responses. Added `tests/test_scoring_policy_registry.py`.
- `4496e5c` — added `config/evaluation_contract.json`, deterministic fixtures for matching/GSIS/UPS/EVI-I/investment/risk/valuation, score-drift checks, FP/FN and coverage metrics, and rejection of uncalibrated numeric probability claims. Added `tests/test_offline_evaluation.py`.
- `76d3a02` — added privacy-safe collaborator ranking audit events, pseudonymous exposure references, field-level provenance, freshness, confidence, and missing-field reason codes. Added `tests/test_decision_audit.py`.
- `9b9c659` — added the Alembic `matches.policy_id` migration and current-versus-legacy policy provenance handling for persisted match decisions.
- `dd4c001` — added schema/version/freshness validation for model and task-policy registries, cost-complete profitability routing, and registry metadata on every AI response. Added `tests/test_registry_freshness.py`.
- `c711313` — expanded CI release gates for the production environment, P0/P1 contracts, deterministic evaluation, migration head, and deployment runbook.
- `f09927b` — completed investor ranking/parity auditing, immutable scaffold artifact registration, authenticated deployment broker integration, full scaffold JSON Schema validation, stack-selection rationale, hardening metrics/alerts, human override tracking, and database-backed production calibration outcomes.

Verification at this checkpoint: `python3 scripts/release_gate.py` => OK; `pytest -q` => `160 passed`; hardening contracts => `44 passed`; `alembic heads` => `bc23de45fa67`. Existing deprecation and local pytest-cache permission warnings remain.

## Production Activation

1. Apply Alembic head `bc23de45fa67`.
2. Record verified outcomes through `/api/v1/admin/calibration/outcomes`.
3. Monitor `/api/v1/admin/calibration/report`; do not change calibration status until it reports `approved` from real production outcomes.
4. Follow `docs/AI_ROUTER_PRODUCTION_RELEASE_RUNBOOK.md` for deployment and rollback.

## Continuation Instructions

```text
cd /home/faithsax/TechIT-Network/ai-router
git status --short
git branch --show-current
git log -3 --oneline
sed -n '1,240p' docs/AI_ROUTER_PRODUCTION_HARDENING_PLAN_2026-08-14.md
```

After each milestone: run the focused tests, update this document's status, commit one coherent change, and record unresolved production risks. Do not merge or deploy until P0 tests and runtime checks are green.

## Risk Register

- Resolved: live collaborator matching no longer exposes fabricated candidate records.
- Resolved: risk evaluation no longer wraps hard-coded risk or SWOT values around AI text.
- Resolved: investor intelligence no longer converts absent evidence into mid-range scores.
- Resolved: scaffold and deployment paths no longer return fictional artifact or live URLs.
- External activation dependency: no real labeled production outcome dataset is present in this workspace, so calibration remains `human_review_only` by design.
- Existing persisted match rows remain legacy/unversioned until replay or evidence-preserving backfill; new decisions record policy ids.
