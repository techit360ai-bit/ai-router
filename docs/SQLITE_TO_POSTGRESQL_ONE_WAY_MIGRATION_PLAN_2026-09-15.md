# AI Router SQLite to PostgreSQL One-Way Migration Plan

**Status:** Plan only; implementation has not started  
**Date:** 2026-09-15  
**Repository:** `techit360ai-bit/ai-router`  
**Target:** PostgreSQL 16 with pgvector as the sole AI Router runtime database

## 1. Decision Summary

The AI Router will use PostgreSQL as its only authoritative database. There will be no runtime SQLite fallback, SQLite outbox mode, dual-read path, dual-write path, or automatic fallback from PostgreSQL to a local file or process-memory store in staging or production.

This is a one-way migration:

```text
Legacy SQLite data, if present
        │
        ▼
Validated PostgreSQL import
        │
        ▼
PostgreSQL-only application and workers
        │
        ▼
SQLite runtime code and artifacts removed
```

The application already has a PostgreSQL-first foundation: SQLAlchemy models in `database_schema.py`, Alembic migrations in `migrations/versions`, PostgreSQL/pgvector deployment services in `docker-compose.yml`, and production environment validation requiring a PostgreSQL `DATABASE_URL`. The implementation work is primarily to remove remaining compatibility paths, make the migration executable and observable, and move tests/local workflows to PostgreSQL.

## 2. Audit Findings

### 2.1 Existing PostgreSQL authority

- `database_schema.py` defines the SQLAlchemy schema using PostgreSQL UUID, JSON/JSONB, arrays, enums, and vector-compatible structures.
- `migrations/versions/` contains the initial schema and follow-on migrations for live domains, AI usage, settlement outbox, GSIS, Trust, investor notes, and projections.
- `migrations/env.py` requires `DATABASE_URL` for online migrations.
- `docker-compose.yml` provisions PostgreSQL and pgvector and injects PostgreSQL URLs into API, worker, scheduler, and migration services.
- `scripts/validate_env.py` rejects non-PostgreSQL database URLs for production/staging.
- `runtime_config.py` only permits `postgres` and `postgresql` schemes.
- `main.py`, `workers/workers.py`, `execution_telemetry.py`, and `live_domain_repository.py` use SQLAlchemy sessions/engines for PostgreSQL runtime persistence.

### 2.2 Remaining SQLite or non-durable paths

- `usage_settlement_client.py` contains a `sqlite` URL check that adds `check_same_thread`; this is runtime compatibility code and must be removed.
- `tests/test_usage_settlement_outbox.py` creates a temporary SQLite database and should move to a PostgreSQL test database or an explicit PostgreSQL Testcontainers/service fixture.
- `live_domain_repository.py` keeps an in-memory store for local development/tests. This may remain only as a pure unit-test seam if it is not presented as persistence; production/staging must fail without PostgreSQL. The preferred end state is PostgreSQL-backed integration tests plus isolated pure service tests, with no application data fallback.
- Some documentation describes “SQLite production fallback” or “local JSON development path” as existing architecture. Those statements must be updated after implementation.
- No checked-in `.db`, `.sqlite`, or `.sqlite3` authority file was found in the repository. A deployment inventory must still verify that no runtime volume, Render disk, worker artifact, or operator backup contains an authoritative SQLite database.

### 2.3 Migration-head risk

`alembic heads` currently reports `ef12ab34cd56` while `scripts/validate_migration_head.py` expects `cd34ef56a7b9`. Before data migration, the migration graph must be reconciled and a single approved head recorded. The migration must not proceed against an ambiguous or stale Alembic head contract.

## 3. Goals

1. Make PostgreSQL 16 + pgvector the only runtime database.
2. Preserve all authoritative AI Router data and relationships.
3. Preserve UUID identity, timestamps, enums, JSON/JSONB semantics, arrays, vector dimensions, indexes, constraints, and audit history.
4. Keep API response contracts stable during the cutover.
5. Remove runtime SQLite branches and persistence fallbacks.
6. Make failure explicit when PostgreSQL is unavailable.
7. Provide repeatable preflight, import, verification, cutover, and post-cutover commands.
8. Ensure API, Celery worker, scheduler, telemetry, usage settlement outbox, and background jobs all point to the same PostgreSQL authority.
9. Prevent accidental reverse migration or reintroduction of dual persistence.

## 4. Non-Goals

- Replacing PostgreSQL with another database.
- Rewriting the AI provider/router architecture.
- Moving Redis, object storage, or vector providers into PostgreSQL unless required by an existing schema contract.
- Using SQLite as a production rollback database.
- Maintaining read/write parity between SQLite and PostgreSQL after cutover.
- Changing business-level credit, Trust, scoring, or authorization rules except where required to preserve data types and authority semantics.

## 5. Target Architecture

### Runtime

```text
FastAPI API ───────────────┐
Celery workers ────────────┼── SQLAlchemy ── PostgreSQL 16 + pgvector
Celery beat ───────────────┤
Execution telemetry ──────┤
Usage settlement outbox ───┘

Redis: cache, broker, rate limits, short-term state
Object storage: private artifacts and uploads
External providers: AI, embeddings, billing, messaging, MCP
```

### Authority rules

- PostgreSQL owns structured state, audit state, usage ledger, score snapshots, Trust projections, and durable outbox records.
- Redis is not a source of truth and must be reconstructible.
- Process memory is allowed only for ephemeral request-local computation, never persisted user/project/workflow state.
- External providers are not databases of record.
- A missing or unhealthy PostgreSQL connection is a deployment/readiness failure for staging and production.

## 6. Data Scope and Mapping

### 6.1 Core schema inventory

The migration inventory must enumerate every table returned by `Base.metadata.tables` and every Alembic-created table. At minimum, include:

- `users`, profiles/learner records, and role metadata.
- `ai_prompts`, model/routing configuration, and prompt versions.
- Credit/usage tables owned by the Router schema, where present.
- `ai_usage_ledger` and `usage_settlement_outbox`.
- Decision audit/outcome tables.
- Project, incubation, workspace, live-domain, and sandbox artifact tables.
- GSIS/EVI score profiles, snapshots, recommendations, outcomes, benchmarks, and config audits.
- Trust verification, Trust projections, investor Trust notes, and related indexes.
- Any embedding/vector columns and their dimension/index requirements.

The implementation must generate a machine-readable inventory containing table name, row count, primary key, foreign keys, nullable columns, enum types, JSON/array/vector columns, indexes, and migration revision.

### 6.2 Legacy SQLite source handling

Because no authoritative SQLite file is checked into the repository, the migration command must support an explicit source path/URL rather than guessing. It must fail closed when:

- No source is provided where legacy data is expected.
- More than one candidate authority is found.
- The source schema does not match the approved inventory.
- A row cannot be mapped without an explicit policy.

If a legacy SQLite source is found, create a read-only snapshot before transformation. Never modify the original source during export.

### 6.3 Type mapping

| SQLite source | PostgreSQL target policy |
|---|---|
| Integer primary key | Preserve as integer only when the target model is integer; otherwise map deterministically to UUID and record the mapping |
| Text UUID | Validate canonical UUID format; reject or quarantine invalid values |
| `TEXT` timestamps | Parse as UTC; preserve original value in migration audit metadata when ambiguous |
| Boolean `0/1` | Convert to PostgreSQL boolean; reject values outside `0/1`/null |
| Numeric text | Parse with bounded precision; reject malformed values |
| JSON text | Parse and validate against contract; store JSONB |
| Delimited list text | Convert to PostgreSQL array only with a documented delimiter/escaping rule |
| Embedding blob/text | Validate dimension and numeric range; load into vector/array target |
| SQLite enum text | Normalize against approved enum values; quarantine unknown values |
| Empty string | Convert to null only where target contract defines empty-as-null; otherwise preserve |

No silent coercion is allowed for identity, authorization, billing, Trust, usage, or audit fields.

### 6.4 Identity and relationships

- Preserve user identity keys where already UUID-compatible.
- Build an immutable old-key to new-key mapping file for any transformed identifiers.
- Load parent tables before children.
- Validate every foreign key after import.
- Preserve event/audit ordering using source timestamps plus a deterministic tie-breaker.
- Never import raw secrets, provider tokens, or prohibited payloads into PostgreSQL.

## 7. Migration Deliverables

### 7.1 Migration tooling

Add a dedicated migration package/command set, for example:

- `scripts/migrate_sqlite_to_postgres.py` — read-only export, transform, and transactional load.
- `scripts/inspect_database_inventory.py` — source/target schema and row inventory.
- `scripts/verify_postgres_migration.py` — counts, checksums, relationships, indexes, and semantic checks.
- `scripts/retire_sqlite_paths.py` — CI/static check that rejects runtime SQLite references.
- `scripts/seed_postgres_reference_data.py` — idempotent required prompts/policies/config, if not covered by Alembic.

Commands must support `--dry-run`, `--source`, `--target`, `--table`, `--batch-size`, `--quarantine-path`, `--resume-from`, and `--report-path` where appropriate.

### 7.2 Alembic schema work

- Reconcile migration graph and establish one approved head.
- Add any missing PostgreSQL-only columns, constraints, indexes, vector extension setup, and outbox indexes.
- Add a migration marker table or deployment metadata row recording migration version, source snapshot hash, operator, start/end times, and verification result.
- Ensure migration scripts are idempotent where operationally safe and transactional where possible.
- Do not create SQLite-compatible branches in Alembic.

### 7.3 Runtime code changes

- Remove `sqlite` URL conditionals from `usage_settlement_client.py`.
- Make all SQLAlchemy engine options PostgreSQL-specific and bounded.
- Make `DATABASE_URL` mandatory in staging/production and fail fast at startup/readiness.
- Remove or isolate `LiveDomainRepository` memory fallback from production code paths.
- Ensure API, workers, scheduler, telemetry, and outbox use the same URL and pool policy.
- Remove any direct file-backed persistence discovered during implementation.
- Add explicit connection health and migration-version checks to readiness.

### 7.4 Test changes

- Replace `tests/test_usage_settlement_outbox.py` SQLite fixture with PostgreSQL.
- Add a reusable PostgreSQL test fixture that applies Alembic migrations to an isolated database/schema.
- Add migration tests for empty database, representative populated database, duplicate keys, nulls, malformed enums/JSON, vector dimensions, and foreign-key violations.
- Add one-way cutover tests proving the runtime refuses `sqlite://` URLs.
- Retain pure unit tests that do not need a database, but do not call them persistence coverage.
- Add integration tests for API, worker, scheduler, telemetry, and usage settlement against PostgreSQL.

## 8. Execution Phases

### Phase 0: Freeze and inventory

1. Freeze schema-changing work during the migration window.
2. Record deployed Router commit, Python/dependency versions, Alembic head, and environment contract.
3. Inventory all database URLs, volumes, workers, cron/scheduler jobs, and backup locations.
4. Search source, tests, Docker, CI, docs, and scripts for SQLite/file-backed authority references.
5. Produce source and target table inventories and identify whether any SQLite authority exists.
6. Resolve the Alembic head mismatch before proceeding.

**Exit:** One approved schema head, one identified source authority, and an approved migration manifest.

### Phase 1: Provision and harden PostgreSQL

1. Provision PostgreSQL 16 with pgvector in an isolated migration environment.
2. Configure TLS/network restrictions, least-privilege application role, migration role, backups, PITR, and pool limits.
3. Apply Alembic migrations to the approved head.
4. Enable required extensions and validate vector/index capabilities.
5. Run schema inventory and readiness checks.

**Exit:** Empty PostgreSQL target passes schema, extension, constraint, index, and readiness checks.

### Phase 2: Build and test importer

1. Implement read-only SQLite extraction, normalized staging records, and quarantine handling.
2. Load parent entities before children in bounded transactions.
3. Preserve IDs and timestamps according to the mapping policy.
4. Use `ON CONFLICT` only where the conflict policy is explicit and audited.
5. Generate row counts, checksums, rejected-row reports, mapping files, and restart checkpoints.
6. Run importer repeatedly against disposable PostgreSQL databases to prove idempotence.

**Exit:** Representative fixtures import with zero unexplained rejects and repeatable verification results.

### Phase 3: Shadow verification

1. Run PostgreSQL-backed application components against the imported copy in read-only/shadow mode.
2. Compare representative API responses, score snapshots, recommendation lists, Trust projections, and usage/outbox state against the source snapshot.
3. Validate authorization boundaries and absence of raw secrets/private payloads.
4. Run worker and scheduler replay tests.
5. Perform performance tests for connection pool, batch import, vector queries, telemetry inserts, and outbox flushes.

**Exit:** Semantic comparisons meet approved tolerances and all security boundaries pass.

### Phase 4: One-way production cutover

1. Announce a short write freeze for legacy SQLite-backed components, if any are found.
2. Stop or fence processes that can write the legacy source.
3. Take a final immutable source snapshot and hash it.
4. Run final import into PostgreSQL.
5. Run full verification and require operator sign-off.
6. Change API, workers, scheduler, telemetry, and settlement configuration to PostgreSQL-only `DATABASE_URL`.
7. Start services in dependency order: PostgreSQL, migrations, API, workers, scheduler.
8. Confirm health, migration version, request execution, usage settlement, and background jobs.
9. Mark the SQLite source retired and make it read-only archival data.

**Exit:** All live writes land in PostgreSQL; no service reads the legacy source.

### Phase 5: Remove compatibility and close migration

1. Delete SQLite engine branches and runtime fallback code.
2. Remove SQLite-specific test dependencies/fixtures.
3. Update docs, Docker, CI, environment examples, and operational runbooks.
4. Add CI checks that reject `sqlite://`, `sqlite3`, `aiosqlite`, `check_same_thread`, and file-backed authoritative stores in runtime code.
5. Retain the source snapshot only under approved archival/retention policy, not as an operational fallback.
6. Publish the final migration report and ownership handoff.

**Exit:** PostgreSQL-only runtime contract is enforced by code, tests, CI, and deployment configuration.

## 9. Verification Plan

### Structural verification

- Alembic revision equals approved head.
- Target table set equals approved schema inventory.
- Column types, nullability, defaults, enums, constraints, indexes, and extensions match.
- All foreign keys resolve.
- Vector columns have expected dimensions and indexes.

### Data verification

- Per-table source/target row counts.
- Per-table primary-key uniqueness.
- Deterministic checksums over canonicalized rows.
- Parent/child relationship counts.
- Timestamp range and ordering checks.
- Enum and JSON/array parse success.
- Usage ledger totals and outbox pending/delivered counts.
- Score snapshot and recommendation counts.
- Trust proof/history/projection consistency.

### Behavioral verification

- API read/write paths use PostgreSQL.
- Worker tasks persist and retrieve state from PostgreSQL.
- Scheduler jobs are idempotent after restart.
- Telemetry inserts do not break AI execution.
- Settlement outbox queues, retries, and marks delivery in PostgreSQL.
- Readiness fails when PostgreSQL is unavailable or at the wrong migration head.
- Runtime rejects `sqlite://` in staging/production.

### Security verification

- No raw provider tokens, secrets, or prohibited evidence imported.
- RLS/authorization policies remain effective where defined.
- Application role cannot run destructive migration operations.
- Migration reports contain identifiers and counts but not secret payloads.
- Source snapshots are encrypted and access-controlled.

## 10. Failure, Retry, and Recovery Policy

- Every import batch is transactional.
- Failed rows are quarantined with reason, table, source key, and sanitized payload summary.
- Import can resume from a checkpoint without duplicating successful rows.
- A failed migration does not switch the live application back to SQLite.
- Before cutover, the legacy system may continue operating under the approved freeze policy; after cutover, PostgreSQL is the only live authority.
- If post-cutover verification fails, stop traffic or disable the affected capability and repair PostgreSQL. Do not re-enable dual writes or silently restore SQLite as a live database.
- Operational rollback means restoring PostgreSQL from backup/PITR or reverting application code to a PostgreSQL-compatible release, not reversing into SQLite.

## 11. Deployment and Environment Changes

### Required environment contract

- `DATABASE_URL` must use `postgresql://` or `postgres://`.
- `POSTGRES_PASSWORD`/secret management must be configured outside source control.
- Pool settings must be bounded and compatible with API + worker + scheduler concurrency.
- Migration role credentials must be separate from runtime role credentials where supported.
- `AI_SETTLEMENT_OUTBOX_AUTO_CREATE` should remain disabled; the table must come from Alembic.
- `AI_SETTLEMENT_OUTBOX_ENABLED` remains enabled only when PostgreSQL and the settlement endpoint are ready.

### Docker/CI changes

- Keep PostgreSQL/pgvector as a required service for API, worker, scheduler, migration, and integration tests.
- Add a migration job that waits for PostgreSQL, runs `alembic upgrade head`, and verifies the approved head.
- Add PostgreSQL health checks to all dependent services.
- Replace any CI job that silently passes without a database with explicit unit versus integration labels.
- Add static SQLite-retirement gate.

## 12. Observability and Runbook Requirements

Emit structured events for:

- Migration start/end and revision.
- Source snapshot hash and target database identifier.
- Table batch progress and rejected-row counts.
- Verification result by category.
- Cutover start/end and operator identity.
- PostgreSQL connection failures, pool exhaustion, migration mismatch, and outbox errors.

The runbook must include:

- Preflight commands.
- Backup/snapshot commands.
- Dry-run importer commands.
- Verification commands and expected thresholds.
- Cutover sequence.
- Post-cutover smoke tests.
- PostgreSQL restore/PITR recovery procedure.
- SQLite archival and destruction/retention procedure.

## 13. Acceptance Criteria

Implementation is complete only when all criteria pass:

1. No production or staging code path accepts or constructs a SQLite database URL.
2. No production or staging authoritative state uses process memory, JSON files, or a local SQLite file.
3. All API, worker, scheduler, telemetry, and settlement outbox persistence runs on PostgreSQL.
4. Alembic has one approved head and CI verifies it.
5. The migration importer produces a signed/hashed report with zero unexplained data loss.
6. Row counts, checksums, foreign keys, indexes, enum values, JSON/array values, vectors, and audit ordering pass verification.
7. Runtime smoke tests pass after PostgreSQL-only cutover.
8. Tests distinguish pure unit tests from PostgreSQL integration tests; the outbox integration test no longer uses SQLite.
9. A PostgreSQL outage produces explicit readiness/operational failure, not silent fallback.
10. Static CI checks prevent reintroduction of SQLite runtime compatibility.
11. Documentation and deployment manifests describe PostgreSQL as the sole authority.
12. The legacy SQLite source, if discovered, is retained only as an immutable archive under approved retention policy.

## 14. Proposed Implementation Sequence

1. Reconcile Alembic head and schema inventory.
2. Add migration/verification tooling and PostgreSQL integration fixtures.
3. Convert outbox and related tests from SQLite to PostgreSQL.
4. Remove SQLite engine branches and production memory/file fallbacks.
5. Add PostgreSQL-only readiness and static retirement gates.
6. Run disposable import and shadow verification rehearsals.
7. Execute production snapshot/import/cutover.
8. Verify live API, workers, scheduler, telemetry, settlement, and intelligence persistence.
9. Archive legacy source and close the migration with an operator report.

## 15. Implementation Decision Gate

This document is the required local plan commit before implementation. No runtime or schema implementation should begin until the plan is reviewed and the following are confirmed:

- The authoritative legacy source, if any, and its retention owner.
- The approved PostgreSQL target and migration head.
- The production migration window and write-freeze policy.
- Backup/PITR readiness.
- The acceptable data-reconciliation tolerance (target: zero unexplained loss).
- The operator responsible for final cutover sign-off.
