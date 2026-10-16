# Entitlement and Billing Flow (Router <-> Backend)

The router executes inference; the backend owns entitlements, credits, pricing,
and settlement. The only coupling is the signed **execution grant**. The router
never reads balances and never trusts client-supplied entitlement input.

## Request lifecycle

1. Caller asks the backend to reserve usage. The backend atomically
   `reserveUsage(...)` (credits/allowance) and mints a short-lived execution
   grant (RS256 in production/staging; HS256 in dev).
2. The router verifies the grant (`ExecutionGrantVerifier`), consumes it once
   (`ExecutionGrantReplayGuard`), and validates subject + task type.
3. `routing_engine.select_chain` builds the candidate chain and applies:
   - task policy (quality, capability, cost, v2 billing/data policy),
   - grant `allowed_model_ids`,
   - grant `allowed_billing_classes` and `required_data_handling`,
   - circuit breaker and configured-provider filters,
   - per-request provider cost budget (`max_provider_cost_usd`).
4. For each attempt the router reserves provider spend
   (`ProviderSpendBudget`, per-minute) and, when a `workflow_id` is present,
   workflow budget (`WorkflowBudget`, cumulative). A workflow denial aborts the
   whole chain rather than falling through.
5. On success the router records an execution fact and settles:
   - provider spend (`ProviderSpendBudget.settle`),
   - workflow budget (`WorkflowBudget.settle`),
   - a signed settlement POST to the backend with an `Idempotency-Key`.

## Grant claims

| Claim | Effect in the router |
| --- | --- |
| `sub`, `request_id`/`jti` | Required. Subject must match the authenticated user. |
| `task_type` | Must match the request task type when present. |
| `allowed_model_ids` | Restricts the candidate set. |
| `max_input_tokens`, `max_output_tokens` | Clamp request budgets. |
| `max_provider_cost_usd` | Per-request cost ceiling (merged with task policy). |
| `allowed_billing_classes` (or `billing_class`) | Restricts routing to those classes. A free-only grant cannot reach a paid model. |
| `required_data_handling` (or `data_handling`) | Restricts routing to models with that data-handling policy. |
| `workflow_id` (or `workflowId`) | Groups sub-requests under one workflow budget. |
| `max_workflow_cost_usd` (or `maxWorkflowCostUsd`) | Cumulative workflow cost ceiling. |

## Settlement fact fields

The router sends execution *facts*, never prices it invented:

`request_id`, `user_id`, `workspace_id`, `workflow_id`, `task_type`, `provider`,
`model`, `status`, `prompt_tokens`, `completion_tokens`, `total_tokens`,
`provider_cost_usd`, `cost_status`, `pricing_version`, `latency_ms`,
`attempt_count`, `cache_hit`, `grant_id`, `reservation_id`, `metadata`.

- `cost_status` is `free`, `estimated`, or `pending_reconciliation`. When the
  registry has no pricing the router sends `pending_reconciliation` and a `null`
  cost instead of inventing a number.
- `pricing_version` records which registry pricing produced the estimate.
- `Idempotency-Key` equals `request_id`, so a retried delivery is not billed or
  counted twice.

## Workflow budgets

`WorkflowBudget` sums cost and call count across every sub-request of one
workflow, including trusted-worker fan-out that carries no grant. Trusted
workers are scoped per user (`trusted-worker:<user_id>`) when the caller does
not supply a `workflow_id`, and bounded by `AI_TRUSTED_WORKER_MAX_COST_USD` /
`AI_TRUSTED_WORKER_MAX_CALLS`. A ceiling of `0` counts without capping.

The backend now persists and reconciles the same facts. Every settlement POST
that carries a `workflow_id` is accumulated by `workflowBudgetService` into the
`workflowBudgets` platform collection (JSONB records — no schema migration),
tracking calls, failures, settled provider cost, settled credits, the ceiling,
remaining budget, `cost_status`, `pricing_version`, and a `within`/`exceeded`
verdict. Idempotent replays return the existing snapshot rather than double
counting. This lets finance confirm that router-enforced workflow ceilings
match what was actually settled, without the router ever reading a balance.

## Invariants

- The router never reads customer balances or prices.
- The backend grant is the sole authority for entitlement; client input is inert.
- A free-tier request can never silently spend on a paid model, including via
  fallback, because disallowed models are removed from the chain, not just
  deprioritized.
- No mock responses are used in production/staging; placeholder responses are
  explicitly marked `metadata.placeholder = true` and refused outside dev.
