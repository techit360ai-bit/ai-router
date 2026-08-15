# AI Router Production Hardening Plan

Status: P0 and scoring policy registry complete; P1 calibration and operational controls remain
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

## Immediate Implementation Slice

P0 items 1–3 and the scaffold integrity portion of item 7 are implemented. The remaining work starts with versioned policy/calibration because the current score formulas still embed business policy in source/config without outcome validation.

## Completed Checkpoints

- `efb0859` — committed this plan and continuation instructions.
- `8875651` — collaborator matching reads persisted `matches`, `users`, and structured skill evidence; empty or untrusted input fails closed. Added `tests/test_matching_evidence.py`.
- `da1a855` — risk and investor outputs require explicit evidence; removed fabricated SWOT/risk/investor defaults; UPS is marked heuristic and uncalibrated. Added `tests/test_decision_evidence_gates.py`.
- `2c92ce1` — scaffold parsing and deployment surfaces fail closed; removed fictional artifact/live URLs and implicit stack defaults. Added `tests/test_scaffold_integrity.py`.
- `86fb0f8` — added validated `config/scoring_policies.json`, production freshness checks, policy-backed GSIS/UPS/EVI-I/investment/match/decay/valuation inputs, and policy metadata on score responses. Added `tests/test_scoring_policy_registry.py`.

Verification at this checkpoint: `pytest -q` => `139 passed` (existing deprecation and local pytest-cache permission warnings remain).

## Next Session

Implement item 5 next:

1. Define an offline evaluation fixture schema for matching, GSIS, UPS, EVI-I, investment, risk, and valuation outcomes.
2. Add deterministic backtests that record coverage and reject probability claims without calibration metadata.
3. Keep consequential classifications human-review-only until minimum outcome coverage and error-rate thresholds are approved.
4. Add migration support for persisted match records so future records store their scoring policy id; current records remain explicitly `legacy_or_unversioned`.

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
- Open: scoring policies are versioned and freshness-checked but remain uncalibrated against outcome data.
- Open: provider registry freshness, fairness monitoring, human override metrics, and release gates remain unimplemented.
- Open: existing persisted match rows do not store the policy id that produced their score; responses label them legacy/unversioned rather than attributing the current policy.
