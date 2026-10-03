#!/usr/bin/env python3
"""Import a read-only legacy SQLite snapshot into PostgreSQL exactly once."""

from __future__ import annotations

import argparse
import getpass
import hashlib
import json
import os
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import Integer, MetaData, Table, and_, select, text
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError

try:
    from database_inventory import canonical_row, coerce_row, file_sha256, json_safe, redact_url, source_engine, source_path, target_engine, write_report
except ModuleNotFoundError:  # Imported as scripts.migrate_sqlite_to_postgres in tests.
    from scripts.database_inventory import canonical_row, coerce_row, file_sha256, json_safe, redact_url, source_engine, source_path, target_engine, write_report


def _apply_schema(target: str) -> None:
    env = dict(os.environ)
    env["DATABASE_URL"] = target
    subprocess.run([sys.executable, "-m", "alembic", "upgrade", "head"], check=True, env=env)


def _ordered_tables(target: Engine, names: set[str]) -> list[Table]:
    metadata = MetaData()
    metadata.reflect(bind=target, only=sorted(names))
    return [table for table in metadata.sorted_tables if table.name in names]


def _validate_table_mapping(source_table: Table, target_table: Table) -> list[str]:
    source_columns = {column.name for column in source_table.columns}
    target_columns = {column.name for column in target_table.columns}
    unexpected = sorted(source_columns - target_columns)
    if unexpected:
        raise RuntimeError(
            f"SQLite source table {source_table.name} contains unmapped columns: {', '.join(unexpected)}"
        )
    missing_required = sorted(
        column.name
        for column in target_table.columns
        if column.name not in source_columns
        and not column.nullable
        and column.server_default is None
        and column.default is None
        and not (
            column.primary_key
            and isinstance(column.type, Integer)
            and column.autoincrement in (True, "auto")
        )
        and getattr(column, "identity", None) is None
    )
    if missing_required:
        raise RuntimeError(
            f"SQLite source table {source_table.name} is missing required PostgreSQL columns: "
            f"{', '.join(missing_required)}"
        )
    return [column.name for column in source_table.columns]


def _source_key(raw: dict[str, Any], source_table: Table) -> dict[str, Any]:
    primary_key = list(source_table.primary_key.columns)
    if primary_key:
        return {column.name: json_safe(raw.get(column.name)) for column in primary_key}
    return {"rowid": json_safe(raw.get("rowid"))} if "rowid" in raw else {}


def _audit_start(engine: Engine, source: Path, source_hash: str) -> uuid.UUID:
    metadata = MetaData()
    audit = Table("database_migration_audits", metadata, autoload_with=engine)
    migration_id = uuid.uuid4()
    with engine.begin() as connection:
        revision = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
        connection.execute(audit.insert().values(
            id=migration_id,
            source_kind="sqlite",
            source_location=str(source),
            source_sha256=source_hash,
            operator=os.getenv("MIGRATION_OPERATOR") or getpass.getuser(),
            alembic_revision=revision,
            status="running",
            verification_status="pending",
        ))
    return migration_id


def _audit_finish(engine: Engine, migration_id: uuid.UUID, status: str, report: dict[str, Any]) -> None:
    metadata = MetaData()
    audit = Table("database_migration_audits", metadata, autoload_with=engine)
    totals = report.get("totals", {})
    with engine.begin() as connection:
        connection.execute(
            audit.update().where(audit.c.id == migration_id).values(
                status=status,
                rows_imported=int(totals.get("imported", 0)),
                rows_skipped=int(totals.get("skipped", 0)),
                rows_rejected=int(totals.get("rejected", 0)),
                report=json_safe(report),
                completed_at=datetime.now(timezone.utc),
            )
        )


def _existing_row(connection, table: Table, row: dict[str, Any], primary_key: list[Any]) -> dict[str, Any] | None:
    if not primary_key:
        return None
    conditions = [column == row[column.name] for column in primary_key]
    return connection.execute(select(table).where(and_(*conditions))).mappings().one_or_none()


def _insert_batch(engine: Engine, table: Table, rows: list[dict[str, Any]], *, resume: bool) -> tuple[int, int]:
    if not rows:
        return 0, 0
    primary_key = list(table.primary_key.columns)
    imported = 0
    skipped = 0
    with engine.begin() as connection:
        pending: list[dict[str, Any]] = []
        for row in rows:
            existing = _existing_row(connection, table, row, primary_key)
            if existing is None:
                pending.append(row)
                continue
            if not resume:
                key = {column.name: json_safe(row[column.name]) for column in primary_key}
                raise RuntimeError(f"target row already exists for {table.name}: {key}; rerun with --resume only after validating the prior import")
            comparable_existing = {name: existing[name] for name in row}
            if canonical_row(comparable_existing) != canonical_row(row):
                key = {column.name: json_safe(row[column.name]) for column in primary_key}
                raise RuntimeError(f"target row conflicts with SQLite source for {table.name}: {key}")
            skipped += 1
        if pending:
            try:
                connection.execute(table.insert(), pending)
            except IntegrityError as exc:
                raise RuntimeError(f"PostgreSQL import failed for {table.name}: {exc.orig}") from exc
            imported = len(pending)
    return imported, skipped


def migrate(
    source: str,
    target: str,
    *,
    dry_run: bool,
    apply_schema: bool,
    batch_size: int,
    output: str | None,
    quarantine_path: str | None,
    resume: bool,
    resume_from: str | None,
    selected_tables: set[str],
) -> int:
    sqlite_path = source_path(source)
    source_hash = file_sha256(sqlite_path)
    if apply_schema:
        _apply_schema(target)
    source_db = source_engine(source)
    target_db = target_engine(target)
    report: dict[str, Any] = {
        "source": str(sqlite_path),
        "source_sha256": source_hash,
        "target": redact_url(target),
        "dry_run": dry_run,
        "resume": resume,
        "tables": {},
        "rejected": [],
        "totals": {"imported": 0, "skipped": 0, "rejected": 0},
    }
    migration_id: uuid.UUID | None = None
    status = "failed"
    try:
        source_metadata = MetaData()
        target_metadata = MetaData()
        source_metadata.reflect(bind=source_db)
        target_metadata.reflect(bind=target_db)
        source_names = {name for name in source_metadata.tables if not name.startswith("sqlite_")}
        target_names = set(target_metadata.tables)
        unmapped = sorted(source_names - target_names)
        if unmapped:
            raise RuntimeError(f"SQLite source contains tables with no PostgreSQL mapping: {', '.join(unmapped)}")
        common = (source_names & target_names) - {"alembic_version", "database_migration_audits"}
        if selected_tables:
            unknown = selected_tables - common
            if unknown:
                raise RuntimeError(f"selected tables are not common to source and target: {', '.join(sorted(unknown))}")
            common &= selected_tables
        ordered_tables = _ordered_tables(target_db, common)
        if resume_from:
            ordered_names = [table.name for table in ordered_tables]
            if resume_from not in ordered_names:
                raise RuntimeError(f"--resume-from table is not selected for import: {resume_from}")
            ordered_tables = ordered_tables[ordered_names.index(resume_from):]
        report["target_tables_without_source"] = sorted(target_names - source_names - {"alembic_version", "database_migration_audits"})
        report["selected_tables"] = [table.name for table in ordered_tables]
        report["resume_from"] = resume_from
        if not dry_run:
            migration_id = _audit_start(target_db, sqlite_path, source_hash)
            report["migration_id"] = str(migration_id)

        for target_table in ordered_tables:
            source_table = source_metadata.tables[target_table.name]
            source_columns = _validate_table_mapping(source_table, target_table)
            primary_key = list(source_table.primary_key.columns)
            order_columns = primary_key or list(source_table.columns)
            statement = select(source_table).order_by(*order_columns)
            table_imported = 0
            table_skipped = 0
            table_rejected = 0
            with source_db.connect() as source_connection:
                batch: list[dict[str, Any]] = []
                for raw_mapping in source_connection.execute(statement).mappings():
                    raw = dict(raw_mapping)
                    try:
                        batch.append(coerce_row(raw, target_table, source_columns))
                    except ValueError as exc:
                        table_rejected += 1
                        report["rejected"].append({
                            "table": target_table.name,
                            "source_key": _source_key(raw, source_table),
                            "reason": str(exc),
                            "present_fields": sorted(raw),
                        })
                        continue
                    if len(batch) >= batch_size:
                        if dry_run:
                            table_imported += len(batch)
                        else:
                            imported, skipped = _insert_batch(target_db, target_table, batch, resume=resume)
                            table_imported += imported
                            table_skipped += skipped
                        batch.clear()
                if batch:
                    if dry_run:
                        table_imported += len(batch)
                    else:
                        imported, skipped = _insert_batch(target_db, target_table, batch, resume=resume)
                        table_imported += imported
                        table_skipped += skipped
            report["tables"][target_table.name] = {
                "source_rows": table_imported + table_skipped + table_rejected,
                "imported_rows": table_imported,
                "skipped_rows": table_skipped,
                "rejected_rows": table_rejected,
                "primary_key": [column.name for column in target_table.primary_key.columns],
                "columns": source_columns,
            }
            report["totals"]["imported"] += table_imported
            report["totals"]["skipped"] += table_skipped
            report["totals"]["rejected"] += table_rejected

        status = "completed" if not report["rejected"] else "failed"
    except Exception as exc:
        report["error"] = str(exc)
        raise
    finally:
        if quarantine_path and report["rejected"]:
            Path(quarantine_path).write_text(json.dumps(report["rejected"], indent=2, sort_keys=True) + "\n", encoding="utf-8")
        report_payload = json.dumps(json_safe(report), sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        report["report_sha256"] = hashlib.sha256(report_payload.encode("utf-8")).hexdigest()
        if migration_id is not None:
            _audit_finish(target_db, migration_id, status, report)
        source_db.dispose()
        target_db.dispose()
        write_report(report, output)
    return 2 if report["rejected"] else 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True, help="Existing SQLite file or URL")
    parser.add_argument("--target", default=os.getenv("DATABASE_URL", ""), help="PostgreSQL URL; defaults to DATABASE_URL")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--apply-schema", action="store_true")
    parser.add_argument("--resume", action="store_true", help="Skip identical primary-key rows from a previously interrupted import")
    parser.add_argument("--resume-from", help="Start or resume at this table in foreign-key-safe load order")
    parser.add_argument("--table", action="append", default=[], help="Import one named table; may be repeated")
    parser.add_argument("--batch-size", type=int, default=500)
    parser.add_argument("--output", "--report-path", dest="output")
    parser.add_argument("--quarantine-path")
    args = parser.parse_args()
    if not args.target:
        parser.error("--target or DATABASE_URL is required")
    if args.batch_size < 1:
        parser.error("--batch-size must be positive")
    try:
        return migrate(
            args.source,
            args.target,
            dry_run=args.dry_run,
            apply_schema=args.apply_schema,
            batch_size=args.batch_size,
            output=args.output,
            quarantine_path=args.quarantine_path,
            resume=args.resume,
            resume_from=args.resume_from,
            selected_tables=set(args.table),
        )
    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        print(f"migration failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
