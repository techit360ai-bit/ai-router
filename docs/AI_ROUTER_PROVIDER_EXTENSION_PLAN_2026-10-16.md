# AI Router - Provider-Independent, Policy-Driven Inference Gateway

## Extension plan (audit + design, no rebuild)

- Date: 2026-10-16
- Repo: `ai-router` (branch `fix/provider-key-readiness`)
- Objective: any supported provider (Anthropic, OpenAI, Amazon Bedrock, OpenRouter
  free and paid, and future providers) becomes usable by adding its API key to the
  configured environment variable - without rebuilding or replacing the existing
  router, billing, grant, or agent architecture.

## 0. Verdict up front

The current design is already a policy-driven, config-first gateway. Onboarding an
OpenAI-compatible provider today is *configuration only*: add a `providers[]` entry
and `models[]` entries to `config/model_registry.json`. No code change required.

Three things are genuinely missing, and all three are additive:

1. A first-class **Amazon Bedrock adapter** (AWS SigV4 / credential-chain and,
   where the model supports it, bearer-token auth) - `provider_adapters.py` has no
   Bedrock path today.
2. **Registry metadata** the prompt requires that the schema does not yet record:
   approval status, billing class, data-handling policy, supported regions,
   explicit streaming/tool-calling/vision/structured-output flags, and a per-model
   pricing version.
3. A **free-vs-paid policy** for OpenRouter and a **workflow-level budget**
   dimension, so a free-tier or multi-agent workflow can never silently spend.

Everything else the prompt asks for already exists in some form and should be
*extended*, not rebuilt.

## 1. Phase 1 - Repository and architecture audit

### 1.1 Modules that already exist and should be reused

| Module | Responsibility (already present) |
| --- | --- |
| `provider_adapters.py` | Provider boundary. Adapters: `openai_responses`, `anthropic_messages`, `gemini_generate`, `cohere_embed`, `openai_compatible`. Builds requests, normalizes responses, maps errors to `ProviderAuthError` / `ProviderRateLimitError` / `ProviderTimeoutError` / `ProviderResponseError` / `ProviderConfigError`. Deliberately has NO billing responsibility. |
| `model_registry.py` + `config/model_registry.json` | `ProviderDefinition` (id, adapter, api_key_env(s), base_url(+env), enabled_env, enabled, region, headers), `ModelDefinition` (id, provider, upstream_model, enabled, user_selectable, quality_tier/score, latency_score, context_window, max_output_tokens, capabilities, input/cached/output cost per million, priority, tags), `TaskPolicy`. Staleness gate (`MODEL_REGISTRY_MAX_AGE_DAYS`). `is_provider_configured`, `eligible_models`, `_meets_policy`. |
| `config/task_policies.json` | Per-task capability floors, quality floors, routing objective, token caps, timeout, `max_provider_cost_usd`, attempts/retries, cache TTL, structured output + schema, preferred/forbidden models. |
| `routing_engine.py` | `ModelRouter.select_chain`: rank by profile/complexity/quality/profitability, canary, `disabled_models`, circuit-breaker filter, provider-budget filter, "exclude unconfigured providers" (`AI_ROUTER_EXCLUDE_UNCONFIGURED`), EWMA feedback. |
| `execution_controls.py` | `ExecutionGrantVerifier` (RS256/HS256), `ExecutionGrantReplayGuard`, `ExecutionRateLimiter`, `ProviderCircuitBreaker`, `ProviderSpendBudget` (per-minute provider spend reserve/settle, Redis-shared), `ProviderCredentialPool` (least-loaded key, cooldown/quarantine), `AIAdmissionController`, `ResponseCache`. |
| `ai_command_layer_impl.py` | The single execution path: grant check -> rate limit -> safety -> prompt -> cache -> `select_chain` -> fallback loop (per-attempt spend reservation) -> provider call -> output validation -> settlement -> telemetry. |
| `usage_settlement_client.py` | Signs execution *facts* (not prices) and posts them to the backend; outbox for retry. |
| `provider_key_health.py` | Live per-provider key probing (bearer / `x-api-key` / query), valid/invalid/unknown classification, mandatory providers fail closed. |
| `runtime_config.py` | Startup/readiness env validation; refuses placeholder responses, demo auth, weak secrets in production. |
| `config/routing_runtime.json`, `config/scalability_slos.json` | Runtime routing controls (disabled models, canaries, rollback, feedback) and capacity/spend defaults. |
| BACKEND `usageGrantService.js`, `usageSettlementService.js`, `usageSettlementController.js` | Backend-minted, short-lived **execution grants** that atomically `reserveUsage` credits/allowance. |
| BACKEND TVCE + entitlement services (`tvceService.js`, `tvceBillingService.js`, `organizationEntitlementService.js`, `workspaceTeamEntitlementService.js`, `capabilityConsumptionService.js`) | Customer pricing, subscription/allowance, credits, workspace entitlements. |

### 1.2 Representative request trace (authenticated user -> usage)

1. Caller (`backend/src/services/aiRouterClient.js`) mints an execution grant via
   `issueExecutionGrant`, which first calls `reserveUsage(...)` in the backend to
   atomically reserve credits/allowance, then signs a JWT (`sub`, `jti`/
   `request_id`, `reservation_id`, `task_type`, `workspace_id`,
   `allowed_model_ids`, `max_input_tokens`, `max_output_tokens`,
   `max_provider_cost_usd`).
2. Router `ExecutionCommandLayer.process_request` verifies the grant
   (`ExecutionGrantVerifier`, RS256 in prod) and enforces `REQUIRE_AI_EXECUTION_GRANT`.
3. Rate limit (`ExecutionRateLimiter`), safety (`SafetyEngine`), prompt build
   (`PromptEngine`), response cache keyed on user/workspace/task/payload.
4. `ModelRouter.select_chain` ranks eligible models by task policy (quality floor,
   capabilities, token/context limits, provider cost) and drops unconfigured
   providers and open circuits.
5. Fallback loop `_execute_with_fallback`: per attempt it reserves provider-side
   spend (`ProviderSpendBudget.reserve`), calls `call_provider_model`, validates
   structured output, records feedback, opens the circuit on failure; retries only
   `ProviderRateLimitError` / `ProviderTimeoutError`.
6. `_record_execution` settles the provider spend reservation and posts signed usage
   facts (provider, model, tokens, `provider_cost_usd`, latency, grant/reservation
   ids, registry version) to the backend, which settles the reservation.

So the entitlement/reservation/settlement loop already exists and is authoritative
server-side. The router explicitly does not own balances, and provider cost is kept
separate from customer charge.

### 1.3 What the prompt asks for that already exists

- Provider-independent, config-driven routing with capability + quality floors:
  `routing_engine.py` + `config/task_policies.json`.
- Central model registry with pricing metadata: `model_registry.py`.
- Provider-side spend guard, circuit breakers, rate limits, credential pooling:
  `execution_controls.py`.
- Atomic credit reservation + settle with idempotency: backend
  `usageSettlementService.js` (idempotent on `request_id`).
- Server-side entitlement authority: backend grants; router never trusts client
  balances (the grant is signed and bounded).
- Error taxonomy and "do not retry invalid credentials": `_retryable` only retries
  429/timeout.
- No provider inference from key prefixes: providers are declared explicitly in the
  registry; `provider_key_health.py` probes by declared provider.
- Structured output validation: `output_validation.validate_output`.
- Registry freshness enforcement: `MODEL_REGISTRY_MAX_AGE_DAYS` + `test_registry_freshness`.

### 1.4 Gaps, risks and policy-bypass paths (verified in the repo)

1. **No Bedrock.** Zero references to `bedrock` in code, config or docs.
2. **OpenRouter is minimal.** One free model (`openrouter-llama-free`), no
   `openrouter/free` router, no approved paid OpenRouter models, no free-vs-paid
   policy. `training_generation` pins it with `max_provider_cost_usd: 0.0`.
3. **Registry schema is missing fields** the prompt requires: approval status,
   billing class, data-handling policy, supported regions, explicit
   streaming/tool-calling/vision/structured-output booleans, health status and a
   per-model pricing version. Capabilities are a loose `set[str]`.
4. **No discovery-vs-approval pipeline.** The registry is a hand-edited JSON; there
   is no "discovered but unapproved" staging area.
5. **Hardcoded model identifiers in code.** `main.py` uses
   `requested_model="openrouter-llama-free"` at three call sites (roughly lines
   2239, 2314, 2363). Model choice should come from task policy, not literals.
6. **Placeholder responses.** `ai_command_layer_impl.py` can return
   `"AI placeholder response via <model>"` when `ALLOW_AI_PLACEHOLDER_RESPONSES`
   and not production; the string is not tagged in metadata, so it is not obviously
   distinguishable downstream. It is blocked in prod/staging by
   `runtime_config.py`, but should carry an explicit `placeholder: true` marker.
7. **Trusted-worker grant bypass.** `AI_TRUSTED_WORKER_EXECUTION=true` (set for
   workers in `docker-compose.yml`) allows execution with no execution grant, i.e.
   no backend reservation. Multi-agent worker fan-out is therefore a spend path
   that must be covered by workflow budgets.
8. **No workflow-level budget.** Budgets are per-request (grant caps) and
   per-provider-per-minute (spend guard). Nothing aggregates cost across the many
   sub-requests a multi-agent workflow issues.
9. **Fallback does not consider billing class or data policy**, only capability,
   budget and circuit state - so a free-tier request could fall back to a paid
   model if both are eligible.
10. **Pricing version** is not recorded per billed request (registry/task-policy
    versions are; per-model price version is not).

## 2. Extension plan (Phases 2-13), additive only

### Phase 2 - Provider adapter architecture

- Add `auth` to `ProviderDefinition` (`bearer` | `anthropic` | `query` | `sigv4` |
  `bedrock_bearer`) so authentication is declared, never inferred from a key
  prefix. Today auth is derived from the adapter inside `provider_key_health.py`;
  make it explicit and shared with the adapters.
- Add adapters in `provider_adapters.py`:
  - `bedrock_converse` - AWS SDK (`boto3`) credential-chain auth, `region_name`
    from the provider definition, `modelId` = the model's `upstream_model`
    (a base model id or an inference-profile id such as
    `us.anthropic.claude-...`), request/response normalized to `ProviderResponse`.
  - `bedrock_bearer` - Bedrock endpoints that accept bearer tokens, using the same
    normalize/map/retry envelope.
- Extend the adapter contract with: `capabilities(adapter)`, `supports_streaming`,
  `stream(...)`, and a shared error-mapper so every adapter raises the existing
  `ProviderError` subclasses.
- Keep provider credentials strictly per-provider: the Bedrock key/role is never
  passed to `anthropic_messages` or `openai_responses`.
- Do not assume one protocol per provider: OpenRouter is `openai_compatible`,
  Bedrock OpenAI models go through `bedrock_converse`, Bedrock Claude through
  `bedrock_converse`, Anthropic Direct through `anthropic_messages`.

### Phase 3 - Environment and secret management

- Extend `.env.example` (and `runtime_config.py` checks) with documented,
  per-provider blocks: `BEDROCK_ENABLED`, `BEDROCK_REGION`,
  `BEDROCK_AUTH` (`sigv4`|`bearer`), `BEDROCK_API_KEY` (bearer only),
  `BEDROCK_INFERENCE_PROFILE_*`; `OPENROUTER_ENABLED`, `OPENROUTER_API_KEY`,
  `OPENROUTER_FREE_ONLY`; direct `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` (already
  present); model-registry, routing-policy, fallback, budget and feature-flag
  variables.
- Validation rules: a disabled provider never requires credentials; enabling a
  provider requires its credentials; production AWS may use IAM roles/temporary
  credentials instead of static keys (boto3 default chain).
- Reuse the existing "never log secrets" posture (`runtime_config._check_url`
  already reports only schemes; `provider_key_health` reports counts, not keys).

### Phase 4 - Central model registry (v2)

- Extend `ModelDefinition` with: `billing_class` (`free`|`paid`|`metered`),
  `approval_status` (`discovered`|`approved`|`disabled`), `supported_regions`,
  `data_handling` (e.g. `no_training`, `retention_bounded`), `health_status`,
  `pricing_version`, and explicit `streaming` / `tool_calling` /
  `structured_output` / `vision` booleans (validated against `capabilities`).
  Keep `enabled`/`user_selectable` as the effective gate, derived from
  `approval_status` so the two cannot diverge.
- Separate discovery from approval: add `config/discovered_models.json` populated
  by a new `model_discovery.py` (reads `GET /models` for OpenAI-compatible
  providers and Bedrock `ListFoundationModels`). Discovered models land as
  `approval_status: discovered` and are never routable until approved.
- Approval process: a small admin action (Phase 11) flips a discovered model to
  `approved`, which copies it into `model_registry.json` with pricing and
  capabilities. Documented in the model-registry doc.
- Every billed request records the effective `pricing_version` (new
  `routing_metadata()`/response `metadata` field).

### Phase 5 - OpenRouter free and paid

- Register `openrouter/free` as its own model id (capability-aware), plus approved
  paid OpenRouter models with real pricing.
- Add a `billing_class` policy to routing: when a request is free-tier
  (`grant.allowed_billing_classes = [free]`, derived from entitlement), the
  candidate chain is restricted to `free` models and **fallback cannot cross into
  `paid`**. `ProviderRateLimitError` on free models is handled as a best-effort
  exhaustion, not as permission to spend.
- Keep treating free models as best-effort: lower priority, `health_status`
  driven by the existing circuit breaker + key health.

### Phase 6 - Entitlement and access policy engine

- The router already defers to the signed backend grant. Extend the grant claims
  (BACKEND `usageGrantService.issueExecutionGrant`) with `billing_class` /
  `allowed_billing_classes`, `workflow_id`, and `max_workflow_cost_usd`, and have
  `routing_engine.select_chain` filter candidates on them in addition to
  `max_provider_cost_usd` / `allowed_model_ids`.
- Return a structured entitlement decision before invoking a paid provider:
  extend `ExecutionGrantVerifier` to expose the decision (allowed/denied + reason
  + billing class + remaining allowance) so the router can emit it to the caller.
- All authoritative state stays server-side in BACKEND; the router continues to
  treat the grant as the sole authority and never trusts client input.

### Phase 7 - Cost estimation, reservations, settlement

- Reuse `ProviderSpendBudget.reserve/settle` (provider side) and the backend
  `reserveUsage`/`settleUsage` (customer side). Additions:
  - Idempotency keys on the settlement POST (reuse `request_id`; add an explicit
    `Idempotency-Key` header).
  - Stream/partial handling: settle on stream end or cancellation, never mid-stream.
  - Estimated vs reconciled: when `_provider_cost` returns `None` (no pricing),
    record `cost_status: estimated|pending_reconciliation` instead of inventing a
    number; carry that through `usage_settlement_client.settle` and the response
    metadata.
  - Record `pricing_version` alongside the cost.

### Phase 8 - Task-aware routing

- Already present via `TaskPolicy`. Extend the policy schema with `max_latency_ms`,
  `required_billing_class`, and `data_handling` so the lowest-cost approved model
  that meets quality + capability + data policy is selected.
- Controlled escalation re-runs the same `select_chain` (hence the same grant,
  budget and billing-class checks) - no separate escalation path.

### Phase 9 - Workflow budgets and cost protection

- Introduce `workflow_id` on `AIRequest` and in the grant; add a
  `WorkflowBudget` control in `execution_controls.py` (Redis-backed, reserve/
  settle keyed by `workflow_id`) that sums across every sub-request of a workflow,
  including trusted-worker calls.
- Enforce limits for total workflow cost, model-call count, tokens, tool calls,
  retries, concurrency, daily/monthly usage and provider spend, reused through the
  existing admission controller and rate limiter.
- Extend the existing provider circuit breaker and add administrative kill
  switches (feature flags already read from env).

### Phase 10 - Fallback and failure handling

- Keep `_retryable` (429/timeout only). Extend the fallback candidate filter so a
  fallback is permitted only when provider enabled, model approved, capabilities +
  data policy satisfied, entitlement/billing class permits it, and the workflow
  budget allows the extra cost - this is where the free->paid guard and workflow
  budget plug in.
- Replace the untagged placeholder string with a structured, explicitly-flagged
  response (`metadata.placeholder = true`), and keep the production refusal in
  `runtime_config.py`.
- Structured error for "no permitted model": reuse `RegistryError` /
  `ExecutionAuthorizationError` but return a machine-readable body the frontend can
  explain.

### Phase 11 - Administrative controls and observability

- Extend the existing admin surface (`/internal/admin/telemetry`,
  `/api/v1/admin/hardening-metrics`, `/api/v1/admin/calibration/*`) with: provider
  status, model approval/availability, pricing configuration, free/paid routing
  policy, entitlement policy, workflow budgets, provider health, usage/cost
  analytics, failure rates, and audit logs.
- Record per request: request id, user id, workspace id, **workflow id**, agent id,
  task type, provider, model, `billing_class`, `pricing_version`, usage, provider
  cost, customer charge (from settlement), latency, outcome, fallback history.
- Keep not logging prompts/content.

### Phase 12 - Testing

Extend the existing suites (`test_model_routing.py`, `test_provider_adapters.py`,
`test_provider_execution.py`, `test_execution_controls.py`,
`test_execution_grant_verifier.py`, `test_registry_freshness.py`,
`test_provider_key_health.py`, `test_production_authorization` on the backend side)
with the prompt's 22 cases, all against **mocked providers**:

- Bedrock bearer and credential-chain auth; Bedrock Claude and Bedrock OpenAI
  invocation.
- OpenRouter free routing and paid authorization; free-tier restriction.
- Anthropic/OpenAI direct compatibility; invalid credentials; missing config;
  disabled providers.
- Model unavailability, rate limits, insufficient credit, allowance exhaustion,
  concurrent reservations, failed-request settlement, retry/fallback
  authorization, multi-agent workflow budgets, premium-model access denial, and
  no-mock-fallback.

Live smoke tests stay out of CI (gated behind an explicit flag and spend cap).

### Phase 13 - Migration and delivery

- Backward compatible: new registry fields are optional with safe defaults; the
  Bedrock adapter is additive; existing providers and agents are untouched.
- Deliverables: this audit, the file/migration map (section 4), updated
  `.env.example`, provider configuration examples, model-registry documentation,
  entitlement/billing flow documentation, test results, deployment + rollback plan,
  and outstanding limitations.
- No destructive migrations and no production deploy without explicit authorization.

## 3. Best approach (recommended)

Agreeing with the three decisions in the brief, plus two additions:

1. **Separate router from billing** - already true; keep the signed grant as the
   only coupling. Do not let the router read balances.
2. **Policy-driven, not provider-driven** - already true via `task_policies.json` +
   `billing_class`. Classify each *model*, not each provider: Bedrock Claude is
   paid; an OpenRouter `:free` model is free; OpenRouter also serves paid.
3. **Protect against hidden expenditure** - add the **workflow budget** dimension
   (Phase 9) and make **fallback billing-class-aware** (Phase 10); these are the
   two biggest real risks, more than any single request.
4. **Config-only onboarding as the north star.** The measure of success is that a
   new OpenAI-compatible provider needs *no code*, and a new non-compatible
   provider needs *one adapter file* plus config. That is already the shape of the
   system; the extension keeps it.
5. **Discovery is not approval.** Route only `approved` models; discovered models
   are inert until an admin approves them.

## 4. File-level change map

New files:
- `ai-router/docs/AI_ROUTER_PROVIDER_EXTENSION_PLAN_2026-10-16.md` (this document)
- `ai-router/model_discovery.py` (discovery -> discovered_models.json)
- `ai-router/config/discovered_models.json`
- `ai-router/docs/MODEL_REGISTRY.md` (registry schema + approval process)
- tests: `test_bedrock_adapter.py`, `test_openrouter_policy.py`,
  `test_workflow_budgets.py`

Modified files (additive):
- `provider_adapters.py` - `bedrock_converse`, `bedrock_bearer`, streaming,
  capability declarations, shared error mapper.
- `model_registry.py` - `ProviderDefinition.auth`; `ModelDefinition` new fields
  (billing_class, approval_status, supported_regions, data_handling,
  health_status, pricing_version, explicit capability booleans); approval/validation.
- `routing_engine.py` - filter by billing class / data policy / workflow budget.
- `ai_command_layer_impl.py` - metadata markers (placeholder, cost_status,
  pricing_version), workflow-id plumbing, settlement idempotency header.
- `execution_controls.py` - `WorkflowBudget`; grant claims for billing class and
  workflow.
- `usage_settlement_client.py` - idempotency key; cost_status; workflow_id.
- `runtime_config.py` - per-provider enablement validation (Bedrock/OpenRouter).
- `provider_key_health.py` - Bedrock probe + explicit `auth` from the registry.
- `config/model_registry.json`, `config/task_policies.json` - Bedrock providers,
  OpenRouter free+paid, new metadata, `openrouter/free`.
- `.env.example` - documented provider + policy variables.

BACKEND (separate change, additive to grants/entitlements):
- `usageGrantService.js` - grant claims (`allowed_billing_classes`, `workflow_id`,
  `max_workflow_cost_usd`) and workflow-level reservation.
- `usageSettlementService.js` - workflow budget accounting + reconciliation status.

## 5. Sequencing

1. Registry v2 schema + validation (no behavior change) and docs.
2. Bedrock adapter + `auth` field + key-health probe.
3. OpenRouter free/paid entries + `openrouter/free` + billing-class policy.
4. Grant claims (billing class, workflow) + routing filters.
5. Workflow budget control + settlement accounting.
6. Fallback billing-class/data-policy guard + placeholder marker.
7. Admin controls + observability.
8. Tests for the 22 cases; then internal-only enablement, then beta.

## 6. Explicit non-goals (to protect the existing design)

- No new abstraction layer replacing `ModelRouter` / `AICommandLayer`.
- No moving customer pricing into the router.
- No removal of existing providers, agents, or task policies.
- No destructive DB migrations; no automatic live-provider testing in CI.
- No claiming a capability exists until verified by a test in this repo.
