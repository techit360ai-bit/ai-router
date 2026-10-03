#!/usr/bin/env python3
"""Verify PostgreSQL schema integrity and optional transformed SQLite parity."""

from __future__ import annotations

import argparse
import os
import re
from typing import Any

from sqlalchemy import MetaData, Table, and_, func, inspect, or_, select, text

from database_inventory import canonical_row, coerce_row, file_sha256, redact_url, source_engine, source_path, table_inventory, target_engine, write_report
from runtime_config import EXPECTED_ALEMBIC_HEAD


EXPECTED_VECTOR_DIMENSIONS = {
    ("user_skill_embeddings", "embedding"): 1536,
    ("idea_embeddings", "embedding"): 1536,
}


def _foreign_key_orphans(engine) -> list[dict[str, Any]]:
    metadata = MetaData()
    metadata.reflect(bind=engine)
    failures: list[dict[str, Any]] = []
    with engine.connect() as connection:
        for child in metadata.sorted_tables:
            for constraint in child.foreign_key_constraints:
                pairs = [(element.parent, element.column) for element in constraint.elements]
                if not pairs:
                    continue
                parent = pairs[0][1].table
                populated = or_(*(child_column.is_not(None) for child_column, _ in pairs))
                match = and_(*(parent_column == child_column for child_column, parent_column in pairs))
                orphan_count = connection.execute(
                    select(func.count()).select_from(child).where(and_(populated, ~select(1).select_from(parent).where(match).exists()))
                ).scalar_one()
                if orphan_count:
                    failures.append({
                        "table": child.name,
                        "constraint": constraint.name,
                        "referred_table": parent.name,
                        "orphan_rows": int(orphan_count),
                    })
    return failures


def _postgres_catalog_checks(engine) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    with engine.connect() as connection:
        invalid_constraints = [dict(row) for row in connection.execute(text("""
            SELECT conrelid::regclass::text AS table_name, conname AS constraint_name, contype
            FROM pg_constraint
            WHERE connamespace = current_schema()::regnamespace AND NOT convalidated
            ORDER BY 1, 2
        """)).mappings()]
        invalid_indexes = [dict(row) for row in connection.execute(text("""
            SELECT indexrelid::regclass::text AS index_name, indrelid::regclass::text AS table_name,
                   indisvalid, indisready
            FROM pg_index
            WHERE indrelid::regclass::text NOT LIKE 'pg_%' AND (NOT indisvalid OR NOT indisready)
            ORDER BY 2, 1
        """)).mappings()]
    return invalid_constraints, invalid_indexes


def _vector_dimensions(engine) -> tuple[dict[str, int | None], list[dict[str, Any]]]:
    found: dict[str, int | None] = {}
    failures: list[dict[str, Any]] = []
    with engine.connect() as connection:
        rows = connection.execute(text("""
            SELECT c.relname AS table_name, a.attname AS column_name,
                   format_type(a.atttypid, a.atttypmod) AS formatted_type
            FROM pg_attribute a
            JOIN pg_class c ON c.oid = a.attrelid
            JOIN pg_namespace n ON n.oid = c.relnamespace
            JOIN pg_type t ON t.oid = a.atttypid
            WHERE n.nspname = current_schema() AND a.attnum > 0 AND NOT a.attisdropped AND t.typname = 'vector'
            ORDER BY c.relname, a.attname
        """)).mappings()
        for row in rows:
            match = re.fullmatch(r"vector\((\d+)\)", row["formatted_type"])
            found[f"{row['table_name']}.{row['column_name']}"] = int(match.group(1)) if match else None
    for (table, column), expected in EXPECTED_VECTOR_DIMENSIONS.items():
        actual = found.get(f"{table}.{column}")
        if actual != expected:
            failures.append({"table": table, "column": column, "expected": expected, "actual": actual})
    return found, failures


def _table_parity(source_db, target_db) -> dict[str, Any]:
    source_metadata = MetaData()
    target_metadata = MetaData()
    source_metadata.reflect(bind=source_db)
    target_metadata.reflect(bind=target_db)
    source_names = {name for name in source_metadata.tables if not name.startswith("sqlite_")}
    target_names = set(target_metadata.tables)
    parity: dict[str, Any] = {}
    for table_name in sorted(source_names):
        source_table = source_metadata.tables[table_name]
        target_table = target_metadata.tables.get(table_name)
        if target_table is None:
            parity[table_name] = {"ok": False, "reason": "missing PostgreSQL target table"}
            continue
        columns = [column.name for column in source_table.columns if column.name in target_table.c]
        target_primary_key = [column.name for column in target_table.primary_key.columns]
        key_columns = target_primary_key or columns
        source_rows: dict[str, str] = {}
        target_rows: dict[str, str] = {}
        with source_db.connect() as connection:
            for raw in connection.execute(select(source_table)).mappings():
                transformed = coerce_row(dict(raw), target_table, columns)
                key = canonical_row({name: transformed.get(name) for name in key_columns})
                if key in source_rows:
                    raise RuntimeError(f"duplicate source key during verification for {table_name}: {key}")
                source_rows[key] = canonical_row(transformed)
        with target_db.connect() as connection:
            for raw in connection.execute(select(*(target_table.c[name] for name in columns))).mappings():
                row = dict(raw)
                key = canonical_row({name: row.get(name) for name in key_columns})
                target_rows[key] = canonical_row(row)
        missing = sorted(set(source_rows) - set(target_rows))
        extra = sorted(set(target_rows) - set(source_rows))
        different = sorted(key for key in set(source_rows) & set(target_rows) if source_rows[key] != target_rows[key])
        parity[table_name] = {
            "source_rows": len(source_rows),
            "target_rows": len(target_rows),
            "missing_keys": missing[:20],
            "extra_keys": extra[:20],
            "different_keys": different[:20],
            "ok": not missing and not extra and not different,
        }
    return parity


def _mark_verification(engine, source_hash: str, verified: bool, report: dict[str, Any]) -> None:
    metadata = MetaData()
    audit = Table("database_migration_audits", metadata, autoload_with=engine)
    with engine.begin() as connection:
        existing = connection.execute(
            select(audit.c.id, audit.c.report)
            .where(and_(audit.c.source_sha256 == source_hash, audit.c.status == "completed"))
            .order_by(audit.c.started_at.desc())
            .limit(1)
        ).mappings().one_or_none()
        if existing is not None:
            connection.execute(
                audit.update().where(audit.c.id == existing["id"]).values(
                    verification_status="verified" if verified else "failed",
                    report={**(existing["report"] or {}), "verification": report, "verification_ok": verified},
                )
            )


def verify(target: str, source: str | None = None, output: str | None = None) -> int:
    target_db = target_engine(target)
    report: dict[str, Any] = {
        "target": redact_url(target),
        "expected_head": EXPECTED_ALEMBIC_HEAD,
        "checks": [],
        "tables": {},
        "ok": True,
    }
    source_hash: str | None = None
    try:
        inspector = inspect(target_db)
        target_tables = inspector.get_table_names()
        with target_db.connect() as connection:
            version = connection.execute(text("SELECT version_num FROM alembic_version")).scalar_one_or_none()
            extension = connection.execute(text("SELECT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector')")).scalar_one()
        report["actual_head"] = version
        report["checks"].append({"name": "migration_head", "ok": version == EXPECTED_ALEMBIC_HEAD, "detail": version})
        report["checks"].append({"name": "pgvector", "ok": bool(extension), "detail": "vector extension"})
        report["checks"].append({"name": "migration_audit_table", "ok": "database_migration_audits" in target_tables, "detail": "database_migration_audits"})

        orphans = _foreign_key_orphans(target_db)
        report["checks"].append({"name": "foreign_key_orphans", "ok": not orphans, "detail": orphans})
        invalid_constraints, invalid_indexes = _postgres_catalog_checks(target_db)
        report["checks"].append({"name": "validated_constraints", "ok": not invalid_constraints, "detail": invalid_constraints})
        report["checks"].append({"name": "valid_indexes", "ok": not invalid_indexes, "detail": invalid_indexes})
        vector_dimensions, vector_failures = _vector_dimensions(target_db)
        report["vector_dimensions"] = vector_dimensions
        report["checks"].append({"name": "vector_dimensions", "ok": not vector_failures, "detail": vector_failures})
        report["tables"] = table_inventory(target_db, include_checksums=True)["tables"]

        if source:
            path = source_path(source)
            source_hash = file_sha256(path)
            report["source"] = str(path)
            report["source_sha256"] = source_hash
            source_db = source_engine(source)
            try:
                parity = _table_parity(source_db, target_db)
                report["parity"] = parity
                report["checks"].append({"name": "source_parity", "ok": all(item["ok"] for item in parity.values()), "detail": parity})
            finally:
                source_db.dispose()
        report["ok"] = all(check["ok"] for check in report["checks"])
        if source_hash and "database_migration_audits" in target_tables:
            _mark_verification(target_db, source_hash, report["ok"], report)
    finally:
        target_db.dispose()
    write_report(report, output)
    return 0 if report["ok"] else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", default=os.getenv("DATABASE_URL", ""))
    parser.add_argument("--source")
    parser.add_argument("--output", "--report-path", dest="output")
    args = parser.parse_args()
    if not args.target:
        parser.error("--target or DATABASE_URL is required")
    try:
        return verify(args.target, args.source, args.output)
    except (FileNotFoundError, RuntimeError, ValueError) as exc:
        print(f"verification failed: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
