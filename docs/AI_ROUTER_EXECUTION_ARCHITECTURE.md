# TechIT AI Router: Execution Architecture and Backend Handoff

Date: 2026-08-10

## Scope

The AI Router is now an execution-only service. It selects models, calls AI
providers, validates responses, applies fallbacks, protects infrastructure, and
records provider telemetry. It does not decide whether a customer has paid,
which product plan they own, or how much a customer should be charged.

The backend remains responsible for future commercial authorization. No new
payment gateway, customer ledger, subscription engine, or pricing service was
created in this implementation.

## Request Flow

1. The backend authenticates the user and may issue a short-lived signed AI
   execution grant.
2. The Router verifies the grant subject, task, model restrictions, token
   limits, provider-spend limit, expiry, issuer, audience, and one-time ID.
3. The task policy supplies required capabilities, minimum quality, token and
   latency limits, retry count, cache policy, and structured-output schema.
4. The model registry filters enabled models by capabilities, context window,
   quality floor, provider status, user-selectability, and grant restrictions.
5. The routing engine ranks eligible models using quality, latency, provider
   health, and provider cost. A user-selected model is accepted only when it
   remains eligible for the task.
6. The command layer calls the selected provider. Timeouts and HTTP 429 errors
   receive one short same-provider retry. Other failures move immediately to
   the next eligible provider.
7. Structured output is parsed and schema-validated. Invalid output is treated
   as a failed provider attempt and activates fallback.
8. Every attempt is recorded with provider, model, prompt tokens, completion
   tokens, latency, status, error details, and estimated provider cost.
9. Safe deterministic tasks may be cached by user/workspace tenant. IP-protected
   tasks bypass cache.

## Seven Implemented Phases

### Phase 1: Execution-Only Contracts

- Removed customer plan, tier, balance, and debit fields from `UserContext`,
  `AIRequest`, `AIResponse`, agent results, and service responses.
- Split prompt tokens and completion tokens in the response contract.
- Added provider identity, cache state, request ID, and provider-cost telemetry.

### Phase 2: Signed Execution Grants

- Added JWT execution grants with issuer and audience validation.
- Added subject/task validation, allowed-model lists, input/output limits, and
  optional provider-spend limits.
- Added replay protection using Redis when available and process-local state
  otherwise.
- `REQUIRE_AI_EXECUTION_GRANT=false` remains the transition default because the
  backend issuer does not exist yet. Production can switch it to `true` only
  after backend synchronization is complete.

### Phase 3: Commercial Logic Removal

- Removed the old commercial modules, endpoints, scheduled reset worker,
  dependency, environment variables, prompt metadata, ORM tables, and active
  RLS policies.
- Added a forward Alembic migration that removes the old commercial state and
  reshapes AI telemetry. Historical migrations were left unchanged so existing
  environments have a valid upgrade path.

### Phase 4: Configurable Routing and Profitability

- Providers, models, prices, capabilities, quality levels, context windows,
  and user-selectability live in `config/model_registry.json`.
- All 54 task policies live in `config/task_policies.json`.
- Profitability routing in the Router means infrastructure efficiency only:
  maximize required quality and reliability while reducing provider spend and
  latency. It does not calculate gross margin because the Router has no revenue
  or customer-price data.
- True product profitability must later be calculated by the backend using its
  customer revenue data plus the Router's actual provider-cost telemetry.

### Phase 5: Reliability and Validation

- Records successful and failed provider attempts.
- Applies one short retry for timeout/429 failures.
- Uses provider/model circuit breakers with optional Redis state.
- Enforces task latency, input-token, output-token, quality, and optional
  provider-spend budgets.
- Validates JSON/schema output before accepting it.
- Routes embeddings through Cohere with OpenAI embeddings as fallback when both
  providers are configured.

### Phase 6: Model and Provider Expansion

- OpenAI: GPT-5.6 Sol, Terra, Luna; GPT-5.5; GPT-5.4; GPT-5.3-Codex; Codex Mini.
- Anthropic: Claude Fable 5, Opus 5, Sonnet 5, Haiku 4.5, Opus 4.6, Sonnet 4.6.
- Moonshot/Kimi: Kimi K2.5 through the generic OpenAI-compatible adapter.
- Mistral: Mistral Large, Mistral Small, and Codestral.
- Google, Cohere, OpenRouter, and a disabled custom OpenAI-compatible provider
  slot remain available.
- New model versions under an existing provider require configuration only.
  A genuinely new API protocol requires one adapter implementation plus config.

### Phase 7: Caching, Limits, Readiness, and Handoff

- Added per-user and per-workspace request limits.
- Added user/workspace-isolated caching and IP-protected bypass.
- Added registry checks to startup/readiness and deployment validation.
- Added model catalog endpoints for the frontend model picker:
  `GET /api/v1/models` and `GET /api/v1/tasks/{task_type}/models`.
- Added tests for registry coverage, user model selection, quality floors,
  profitability profiles, adapters, retries, fallback, validation, grants,
  caching, and removal of the old commercial runtime.

## Task Complexity Classifier

Complexity is configuration-driven, not inferred from model names. Supported
classes are reasoning, long generation, short generation, classification, code
generation, and embeddings. Each task declares capabilities and a minimum
quality score. This permits newer models and additional providers without
changing task-allocation source code.

Only add source code when a provider uses a new wire protocol or authentication
method. New model versions, quality scores, capabilities, prices, and routing
priority belong in configuration.

## User Model Selection

The frontend should request the task-filtered catalog and submit the selected
registry ID as `requested_model` or `model_id`. The Router rejects disabled,
non-selectable, grant-disallowed, capability-incompatible, undersized-context,
or below-quality models. It will not silently replace an explicitly selected
model; the caller receives a clear eligibility error.

## Backend Synchronization Required Later

Backend engineers must complete the following before commercial launch:

1. Build payment gateway, subscriptions, invoices, entitlements, customer
   balances, pricing plans, refunds, and webhooks entirely in the backend.
2. Decide whether an authenticated user may run an AI feature before calling
   the Router. The Router must not query backend commercial tables.
3. Issue short-lived, one-time execution grants containing `sub`, `jti`,
   `request_id`, `task_type`, `workspace_id`, `allowed_model_ids`, token limits,
   optional provider-spend limit, `iss`, `aud`, `iat`, and `exp`.
4. Send grants in `X-AI-Execution-Grant`; then enable
   `REQUIRE_AI_EXECUTION_GRANT=true` in staging before production.
5. Keep grant signing secrets separate from provider API keys and rotate them.
6. Consume Router telemetry asynchronously to obtain actual provider cost,
   tokens, latency, cache state, model, provider, and failure attempts.
7. Decide commercially whether cache hits, failed attempts, retries, and partial
   responses are chargeable. The Router records facts but makes no such decision.
8. Join backend revenue/customer-price data with Router provider cost to compute
   gross margin and product profitability.
9. Map backend feature entitlements to allowed task types and minimum quality.
   Paid features must grant only models that satisfy the configured quality floor.
10. Build reconciliation/idempotency around backend commercial events. Never use
    the Router's request ID as a payment transaction ID without a backend ledger.
11. Synchronize the frontend model picker with the Router catalog and preserve a
    backend override for features that should not expose model choice.
12. Monitor grant rejection rate, provider failure rate, circuit state, latency,
    token use, provider cost, and fallback frequency.

## Deployment Notes

- Keep provider prices private because they are infrastructure FinOps metadata.
- Update model prices and verified upstream IDs through reviewed configuration.
- Unknown provider prices are penalized in profitability scoring and are not
  treated as free.
- Moonshot and Mistral cost metadata should be added only after verification
  from their official pricing sources.
- Run the forward migration and back up removed commercial tables first if an
  existing environment contains data that backend engineers may later import.
