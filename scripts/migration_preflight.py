#!/usr/bin/env python3
"""Fail-closed production preflight for the one-way SQLite/PostgreSQL cutover."""

from __future__ import annotations

import argparse
import json
import os
import stat
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import text

try:
    from database_inventory import file_sha256, redact_url, source_path, target_engine
except ModuleNotFoundError:  # Imported as scripts.migration_preflight in tests.
    from scripts.database_inventory import file_sha256, redact_url, source_path, target_engine
from runtime_config import EXPECTED_ALEMBIC_HEAD

ROOT = Path(__file__).resolve().parents[1]


def discover_sqlite_candidates(root: Path = ROOT) -> list[str]:
    candidates: list[str] = []
    for path in root.rglob("*"):
        if not path.is_file() or path.name.startswith("."):
            continue
        if path.suffix.lower() in {".db", ".sqlite", ".sqlite3"}:
            candidates.append(str(path.relative_to(root)))
    return sorted(candidates)


def _env_or_arg(value: str | None, name: str) -> str:
    result = (value or os.getenv(name, "")).strip()
    if not result:
        raise ValueError(f"{name} is required")
    return result


def _confirmed(value: str | None, name: str) -> bool:
    result = _env_or_arg(value, name).lower()
    if result not in {"1", "true", "yes", "confirmed"}:
        raise ValueError(f"{name} must be explicitly confirmed")
    return True


def _parse_window(start: str, end: str) -> tuple[str, str]:
    try:
        start_dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
        end_dt = datetime.fromisoformat(end.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("migration window must use ISO-8601 timestamps") from exc
    if start_dt.tzinfo is None or end_dt.tzinfo is None:
        raise ValueError("migration window timestamps must include a timezone")
    if end_dt <= start_dt:
        raise ValueError("migration window end must be after start")
    return start_dt.astimezone(timezone.utc).isoformat(), end_dt.astimezone(timezone.utc).isoformat()


def preflight(
    *,
    target: str,
    source: str | None,
    no_legacy_source: bool,
    operator: str | None,
    retention_owner: str | None,
    retention_policy: str | None,
    window_start: str | None,
    window_end: str | None,
    backup_id: str | None,
    pitr_confirmed: str | None,
    write_freeze_confirmed: str | None,
    cutover_approved: str | None,
    inventory_confirmed: str | None,
) -> dict[str, Any]:
    if bool(source) == bool(no_legacy_source):
        raise ValueError("provide exactly one of --source or --no-legacy-source")
    if no_legacy_source and _env_or_arg(inventory_confirmed, "SQLITE_AUTHORITY_INVENTORY_CONFIRMED").lower() not in {"1", "true", "yes", "confirmed"}:
        raise ValueError("SQLITE_AUTHORITY_INVENTORY_CONFIRMED must explicitly confirm the deployment inventory")

    operator_name = _env_or_arg(operator, "MIGRATION_OPERATOR")
    owner = _env_or_arg(retention_owner, "SQLITE_RETENTION_OWNER")
    policy = _env_or_arg(retention_policy, "SQLITE_RETENTION_POLICY")
    start, end = _parse_window(_env_or_arg(window_start, "MIGRATION_WINDOW_START"), _env_or_arg(window_end, "MIGRATION_WINDOW_END"))
    backup = _env_or_arg(backup_id, "POSTGRES_BACKUP_ID")
    _confirmed(pitr_confirmed, "POSTGRES_PITR_CONFIRMED")
    _confirmed(write_freeze_confirmed, "WRITE_FREEZE_CONFIRMED")
    _confirmed(cutover_approved, "CUTOVER_APPROVED")

    source_report: dict[str, Any]
    if source:
        path = source_path(source)
        mode = path.stat().st_mode
        if mode & (stat.S_IWUSR | stat.S_IWGRP | stat.S_IWOTH):
            raise ValueError(f"SQLite source must be read-only before cutover: {path}")
        source_report = {"location": str(path), "sha256": file_sha256(path), "read_only": True}
    else:
        source_report = {"location": None, "sha256": None, "read_only": None, "authority_confirmed_absent": True}

    database_url = target.strip()
    target_db = target_engine(database_url)
    try:
        with target_db.connect() as connection:
            actual_head = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one_or_none()
            vector_enabled = bool(connection.execute(text("SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector')")).scalar_one())
    finally:
        target_db.dispose()
    if actual_head != EXPECTED_ALEMBIC_HEAD:
        raise ValueError(f"target migration head must be {EXPECTED_ALEMBIC_HEAD}; found {actual_head or 'none'}")
    if not vector_enabled:
        raise ValueError("target PostgreSQL database must have the vector extension enabled")

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "operator": operator_name,
        "retention_owner": owner,
        "retention_policy": policy,
        "migration_window": {"start": start, "end": end},
        "backup_id": backup,
        "source": source_report,
        "target": {"url": redact_url(database_url), "alembic_head": actual_head, "pgvector": vector_enabled},
        "approvals": {"pitr": True, "write_freeze": True, "cutover": True},
        "status": "ready_for_operator_execution",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", help="Read-only SQLite snapshot or URL")
    parser.add_argument("--no-legacy-source", action="store_true")
    parser.add_argument("--target", default=os.getenv("DATABASE_URL", ""), required=not bool(os.getenv("DATABASE_URL")))
    parser.add_argument("--operator")
    parser.add_argument("--retention-owner")
    parser.add_argument("--retention-policy")
    parser.add_argument("--window-start")
    parser.add_argument("--window-end")
    parser.add_argument("--backup-id")
    parser.add_argument("--pitr-confirmed")
    parser.add_argument("--write-freeze-confirmed")
    parser.add_argument("--cutover-approved")
    parser.add_argument("--inventory-confirmed")
    parser.add_argument("--report", required=True)
    args = parser.parse_args()
    try:
        report = preflight(
            target=args.target,
            source=args.source,
            no_legacy_source=args.no_legacy_source,
            operator=args.operator,
            retention_owner=args.retention_owner,
            retention_policy=args.retention_policy,
            window_start=args.window_start,
            window_end=args.window_end,
            backup_id=args.backup_id,
            pitr_confirmed=args.pitr_confirmed,
            write_freeze_confirmed=args.write_freeze_confirmed,
            cutover_approved=args.cutover_approved,
            inventory_confirmed=args.inventory_confirmed,
        )
    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        print(f"migration preflight failed: {exc}", file=sys.stderr)
        return 1
    Path(args.report).write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"migration preflight OK: {args.report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
