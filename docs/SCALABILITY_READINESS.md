# AI Router Scalability Readiness

This repo now ships a CI-safe scalability smoke contract:

```bash
python3 scripts/scalability_check.py
```

By default the command is a dry run. It validates the target plan and probe
limits without contacting external services. The release gate runs this dry-run
contract before pytest.

To run against an authorized staging environment:

```bash
AI_ROUTER_SCALABILITY_PROBE_ENABLED=true \
AI_ROUTER_BASE_URL=https://ai-router-staging.example.com \
python3 scripts/scalability_check.py
```

The `/ready` endpoint bounds database connection checks so a broken Postgres
connection fails fast instead of holding the readiness request open. Operators
can tune the defaults with:

- `DATABASE_CONNECT_TIMEOUT_SECONDS` default `5`, max `60`
- `DATABASE_POOL_TIMEOUT_SECONDS` default `5`, max `60`

The probe is intentionally capped:

- Default concurrency: 2
- Max concurrency: 10
- Default requests per target: 3
- Max requests per target: 25

Trust Engine scalability contracts now cover:

- Investor Trust lookup indexes for investor/project reads.
- Trust profile status/score dashboard indexes.
- Trust verification history project timeline and expiry-scan indexes.
- Continuous verification worker batch cap and failure isolation.

Evidence required before claiming ai-router scalability:

- Staging probe results for health, readiness, dashboard auth boundary, and
  investor Trust auth boundary.
- AI Router quality gates passing on the same commit.
- Migration applied successfully in staging.
- Worker run metrics showing bounded batch sizes, isolated failed batches, and
  no provider calls from continuous verification refreshes.
