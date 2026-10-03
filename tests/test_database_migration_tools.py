from __future__ import annotations

import sqlite3

import pytest
from sqlalchemy import Column, DateTime, Float, MetaData, String, Table
from sqlalchemy.dialects.postgresql import UUID

from scripts.database_inventory import coerce_row, redact_url, source_engine
from scripts.migrate_sqlite_to_postgres import _validate_table_mapping
from scripts.migration_preflight import _parse_window, discover_sqlite_candidates


def test_source_engine_rejects_missing_sqlite_file(tmp_path) -> None:
    missing = tmp_path / "missing.sqlite"
    with pytest.raises(FileNotFoundError, match="does not exist"):
        source_engine(str(missing))
    assert not missing.exists()


def test_source_engine_opens_existing_sqlite_read_only(tmp_path) -> None:
    source = tmp_path / "legacy.sqlite"
    with sqlite3.connect(source) as connection:
        connection.execute("CREATE TABLE example (id TEXT PRIMARY KEY)")
    engine = source_engine(str(source))
    try:
        with engine.begin() as connection:
            with pytest.raises(Exception):
                connection.exec_driver_sql("CREATE TABLE forbidden (id TEXT)")
    finally:
        engine.dispose()


def test_redact_url_hides_password() -> None:
    redacted = redact_url("postgresql://techit:super-secret@db.example/techit")
    assert "super-secret" not in redacted
    assert "***" in redacted


def test_coerce_row_matches_postgres_types() -> None:
    table = Table(
        "example",
        MetaData(),
        Column("id", UUID(as_uuid=True), primary_key=True),
        Column("score", Float()),
        Column("created_at", DateTime(timezone=False)),
        Column("name", String()),
    )
    row = coerce_row(
        {
            "id": "11111111-1111-4111-8111-111111111111",
            "score": "92.5",
            "created_at": "2026-09-16T10:00:00+00:00",
            "name": "fixture",
        },
        table,
    )
    assert str(row["id"]) == "11111111-1111-4111-8111-111111111111"
    assert row["score"] == 92.5
    assert row["created_at"].tzinfo is None


def test_table_mapping_rejects_unmapped_source_columns() -> None:
    source = Table(
        "example",
        MetaData(),
        Column("id", String(), primary_key=True),
        Column("legacy_only", String()),
    )
    target = Table("example", MetaData(), Column("id", String(), primary_key=True))
    with pytest.raises(RuntimeError, match="unmapped columns: legacy_only"):
        _validate_table_mapping(source, target)


def test_table_mapping_rejects_missing_required_target_columns() -> None:
    source = Table("example", MetaData(), Column("id", String(), primary_key=True))
    target = Table(
        "example",
        MetaData(),
        Column("id", String(), primary_key=True),
        Column("required_value", String(), nullable=False),
    )
    with pytest.raises(RuntimeError, match="missing required PostgreSQL columns: required_value"):
        _validate_table_mapping(source, target)


def test_migration_preflight_requires_ordered_timezone_window() -> None:
    with pytest.raises(ValueError, match="end must be after start"):
        _parse_window("2026-09-17T10:00:00Z", "2026-09-17T09:00:00Z")
    start, end = _parse_window("2026-09-17T10:00:00+02:00", "2026-09-17T12:00:00+02:00")
    assert start.endswith("+00:00")
    assert end.endswith("+00:00")


def test_migration_preflight_discovers_sqlite_candidates(tmp_path) -> None:
    (tmp_path / "legacy.sqlite").touch()
    (tmp_path / "nested").mkdir()
    (tmp_path / "nested" / "backup.db").touch()
    assert discover_sqlite_candidates(tmp_path) == ["legacy.sqlite", "nested/backup.db"]
