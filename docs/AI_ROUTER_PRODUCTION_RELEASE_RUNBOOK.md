# AI Router Production Release Runbook

Status: release gate automated; deployment approval remains manual

## Automated Gate

Run from the AI Router directory:

```text
python3 scripts/release_gate.py
```

The gate compiles the code, validates the production environment contract, runs the P0/P1 hardening contracts, checks deterministic score drift, verifies the Alembic head, runs the scalability dry run, and executes the full test suite.

## Required Deployment Order

1. Verify provider prices, context limits, output limits, and registry timestamps against provider documentation. Update the registry version and `updated_at` when evidence changes.
2. Configure production JWT, execution-grant, settlement, private storage, provider, and decision-audit secrets. Never reuse the CI fixture values.
3. Apply `alembic upgrade head` and confirm the database reports head `ab12cd34ef56` before starting API or worker traffic.
4. Start Postgres/pgvector and Redis, then worker and scheduler, then the API. Confirm `/ready` succeeds with live dependencies.
5. Confirm structured decision-audit logs are exported to the approved restricted log sink. Audit events must not contain names, emails, skills, profile text, or raw user identifiers.
6. Exercise collaborator matching, sparse risk, sparse investor, and malformed scaffold requests. Confirm they fail closed with no fabricated records, numeric conclusions, or artifact URLs.

## Manual Approval Blocks

- Consequential score classifications remain human-review-only. `python3 offline_evaluation.py` must continue to report `human_review_only` until real labeled outcomes meet the approved coverage, false-positive, false-negative, and calibration thresholds.
- Existing match rows with no `policy_id` remain `legacy_or_unversioned`; do not backfill them with the current policy id unless the original scoring inputs are replayed under an approved migration process.
- Scaffold download/deploy/live links remain disabled until an authenticated artifact registry and deployment connector persist verifiable records.
- Ranking outcome parity cannot be approved until real outcomes are available. Do not add protected attributes or proxy features to routing or audit payloads.
- Production deployment requires an operator to confirm database backups, rollback ownership, alert routing, provider quota, settlement reconciliation, and private object-storage access controls.

## Rollback

1. Disable incoming AI execution at the gateway or revoke execution grants.
2. Roll back application containers to the last approved image.
3. Do not downgrade the match-policy migration while new code may write `matches.policy_id`.
4. Preserve decision-audit and settlement logs for incident review.
5. Re-run the release gate before restoring traffic.
