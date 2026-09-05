# TechIT Network Scalability Implementation Plan

Status: implementation baseline committed locally; production rollout remains staged work.

## Objective

Support growth from the current deployment to 1,000,000+ registered users and large bursts of concurrent API and AI activity without rebuilding the existing Vite + React frontend, Node backend, AI Router, Workspace, Messaging, Feed, or Incubation Hub.

The target behavior is controlled degradation: queue work that can wait, reject work early with a retry hint when capacity is exhausted, and keep reads and core interactions available.

## Existing -> Extend -> New map

| Area | Existing | Extension required |
| --- | --- | --- |
| AI routing | Async calls, model fallback, retries, circuit breakers, cache, user/workspace limits | Add admission queues, provider/key bulkheads, durable jobs, and global demand budgets |
| Provider credentials | One `api_key_env` per provider | Add secret references for multiple key slots with health and cooldown state |
| Backend | Express routes and route-specific limits | Add global distributed limits, stateless replicas, and PostgreSQL |
| Persistence | SQLite production fallback and local JSON development path | PostgreSQL as the authoritative multi-replica store; retain SQLite for local use |
| Frontend | Vite + React, lazy routes, shared API clients, IndexedDB/PWA resilience | Add request coalescing, cache validators, polling backoff, and queue-aware states |
| Fast-Track | Existing intake, simulated progress, synchronous full pipeline, results dashboard | Preserve result contract; submit long work as durable jobs with real progress |
| Observability | Execution telemetry and hardening metrics | Add queue, provider-key, database-pool, and frontend saturation dashboards |

## Dynamic provider spend budget

The AI Router now contains a provider spend guard in `execution_controls.py`. It is infrastructure protection only; it does not define customer prices, credits, subscriptions, or TVCE.

Default formula:

```text
demand_units = max(base_demand_units, active_users_in_window, calls_in_window)
budget_usd_per_minute = base_budget_usd_per_minute
                         * demand_units / base_demand_units
                         * growth_multiplier
```

Defaults are `$100` for 10 demand units, which is `$10` per additional unit. At 1,000,000 demand units the uncapped computed budget is `$10,000,000` per minute. A production ceiling should still be set deliberately.

Configuration:

```text
AI_PROVIDER_SPEND_GUARD_ENABLED=true
AI_PROVIDER_SPEND_BASE_USD_PER_MINUTE=100
AI_PROVIDER_SPEND_BASE_DEMAND_UNITS=10
AI_PROVIDER_SPEND_GROWTH_MULTIPLIER=1
AI_PROVIDER_SPEND_MAX_USD_PER_MINUTE=0   # 0 means no software cap; set a real cap in production
```

The guard reserves the estimated maximum cost before each provider attempt, settles to actual usage on success, and releases the reservation on failure. Redis-backed counters are required for consistent behavior across replicas; the process-local path is for development and single-instance operation.

This budget is not a guarantee that provider quotas or billing limits increase. Provider account quotas, approved spend limits, and provider terms remain authoritative.

## Target architecture for 1M+ users

```text
CDN/object storage (hashed Vite assets, Brotli, HTTP/2/3)
        |
Load balancer / API gateway
        |
Stateless Node replicas -- Redis cluster (limits, locks, queues, pub/sub)
        |                         |
Managed PostgreSQL + PgBouncer   AI admission controller
                                  |
                         Interactive / long-running / batch queues
                                  |
                   Provider + model + credential-key bulkheads
                                  |
                       Existing AI Router and provider APIs
```

At this scale, use multiple regions only after a single-region design meets SLOs. Keep tenant and authorization boundaries explicit, and use regional routing with a globally consistent identity and billing ledger where required.

## Delivery phases

### Phase 0 - SLOs and capacity model

- Define RPS, concurrent sessions, AI queue age, p95/p99 latency, error budget, and provider spend limits.
- Separate registered users, daily active users, peak concurrent users, and calls per minute.
- Produce traffic profiles for read, write, WebSocket, interactive AI, and long-running analysis.

Exit: load model and SLOs are approved and reproducible in staging.

### Phase 1 - Production data and shared state

- Make managed PostgreSQL mandatory for staging/production.
- Add PgBouncer and size pools across all replicas and workers.
- Make Redis mandatory for distributed rate limits, circuit state, queues, locks, cache coordination, and WebSocket pub/sub.
- Review indexes, slow queries, transaction sizes, and retention policies.

Exit: no authoritative production state depends on a local filesystem or process memory.

### Phase 2 - Gateway and AI admission control

- Add global, IP, user, workspace, provider, model, and key limits.
- Add bounded semaphores per provider/model/key.
- Return `202` with a job ID for work beyond the synchronous latency budget.
- Return `429` with `Retry-After` for policy limits and `503` for exhausted platform capacity.
- Add cancellation, deadlines, idempotency keys, exponential backoff, and retry classification.

Exit: bursts create bounded queue growth rather than unbounded request memory or provider connections.

### Phase 3 - Credential pools

- Extend the provider registry to support secret references such as `OPENAI_API_KEY_1` through `_4` or a secret-manager registry.
- Track key load, 429 cooldown, authentication quarantine, timeout failures, and spend attribution.
- Alert on exhausted or invalid pools.
- Never expose key material to the frontend or telemetry.

Exit: a single exhausted key does not take down a provider route, and failover is observable.

### Phase 4 - Durable AI jobs

- Move Fast-Track and full Incubation pipelines to submit/status/result contracts.
- Persist job state and operation IDs in PostgreSQL.
- Use existing WebSocket/SSE/polling infrastructure for real progress.
- Keep current result schemas and UI actions compatible.
- Separate interactive, batch, and scheduled worker pools.

Exit: long-running work survives request disconnects and worker restarts without duplication.

### Phase 5 - Frontend efficiency

- Add request coalescing and deduplication to the shared Vite API client.
- Use ETags and conditional requests for stable reads.
- Paginate and incrementally render large lists.
- Back off polling when a tab is hidden or Data Saver is enabled.
- Cancel stale requests and centralize 429/503/queued/retryable states.
- Keep CDN delivery independent of API replicas.

Exit: initial route fan-out and background polling remain within an explicit client request budget.

### Phase 6 - Fast-Track parity and truthful progress

- Preserve the existing specialized intake and results dashboard.
- Replace simulated step advancement with server-reported states: queued, running, waiting for provider, completed, failed, and needs attention.
- Cache public repository metadata briefly, enforce fetch timeouts, and limit GitHub concurrency.
- Require idempotency for repeated submissions.

Exit: Fast-Track provides the same quality of result preview while reporting actual execution state.

### Phase 7 - Load, failure, and integrity testing

- Run staged tests at 100, 500, 1,000, 5,000, 10,000, 100,000, and modelled 1,000,000-user profiles.
- Test provider 429/5xx/timeouts, key quarantine, Redis loss, database saturation, queue overflow, worker loss, and network partitions.
- Verify no duplicate jobs/messages, lost drafts, stale-live claims, silent overwrites, unauthorized offline actions, or financial replay.

Exit: SLOs pass with measured headroom and failure behavior is documented.

### Phase 8 - Progressive rollout and operations

- Release behind feature flags and tenant cohorts.
- Monitor queue age, in-flight calls, provider/key health, spend, cache hit rate, DB pool saturation, WebSocket connections, and frontend failures.
- Set automated alerts and rollback thresholds.
- Recalculate capacity and spend budgets from observed demand monthly or after major feature launches.

Exit: on-call runbooks, dashboards, and rollback procedures are exercised.

## Non-goals

- No second workspace, editor, messaging system, API router, database, or offline application.
- No frontend API keys or browser-side provider routing.
- No assumption that multiple provider keys multiply quota.
- No customer pricing or TVCE values in the AI Router infrastructure configuration.

## Acceptance criteria

- Normal online behavior remains unchanged.
- AI bursts are bounded by admission control and provider/key capacity.
- Provider spend protection scales from the configured base and is visible in telemetry.
- Long analyses return durable job IDs and truthful progress.
- PostgreSQL and Redis are authoritative in multi-replica environments.
- Frontend request fan-out and polling are bounded.
- Load and integrity tests demonstrate no duplication, data loss, unauthorized execution, or false delivery state.
