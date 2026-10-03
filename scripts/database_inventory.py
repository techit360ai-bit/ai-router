"""Shared database inventory and transformation helpers for PostgreSQL cutover."""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import sys
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Iterable

from sqlalchemy import Boolean, Date, DateTime, Enum, Float, Integer, LargeBinary, MetaData, Numeric, Table, create_engine, func, inspect, select
from sqlalchemy.dialects.postgresql import ARRAY, JSON, JSONB, UUID
from sqlalchemy.engine import Engine, make_url
import pgvector.sqlalchemy  # noqa: F401 - register VECTOR for PostgreSQL reflection

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from runtime_config import database_engine_options, require_postgres_url


def source_url(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        raise ValueError("database source is required")
    return raw if "://" in raw else f"sqlite:///{Path(raw).expanduser().resolve()}"


def source_path(value: str) -> Path:
    url = make_url(source_url(value))
    if url.drivername not in {"sqlite", "sqlite3"}:
        raise ValueError("legacy source must be a SQLite URL or file path")
    if not url.database or url.database == ":memory:":
        raise ValueError("legacy source must be an existing SQLite file")
    path = Path(url.database).expanduser()
    if not path.is_absolute():
        path = path.resolve()
    if not path.is_file():
        raise FileNotFoundError(f"legacy SQLite source does not exist: {path}")
    return path


def redact_url(value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return ""
    try:
        return make_url(raw).render_as_string(hide_password=True)
    except Exception:
        return raw


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def target_engine(url: str | None = None) -> Engine:
    database_url = require_postgres_url(url or os.getenv("DATABASE_URL", ""))
    return create_engine(database_url, **database_engine_options(database_url))


def source_engine(url: str) -> Engine:
    path = source_path(url)
    return create_engine(
        "sqlite://",
        creator=lambda: sqlite3.connect(f"file:{path}?mode=ro", uri=True),
    )


def _parse_json(value: Any) -> Any:
    if not isinstance(value, str):
        return value
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return value


def coerce_value(value: Any, column) -> Any:
    if value is None:
        return None
    column_type = column.type
    location = f"{column.table.name}.{column.name}"
    if isinstance(column_type, UUID):
        try:
            return value if isinstance(value, uuid.UUID) else uuid.UUID(str(value))
        except (ValueError, TypeError, AttributeError) as exc:
            raise ValueError(f"invalid UUID for {location}") from exc
    if isinstance(column_type, (JSON, JSONB)):
        parsed = _parse_json(value)
        if isinstance(value, str) and parsed is value:
            raise ValueError(f"invalid JSON for {location}")
        return parsed
    if isinstance(column_type, ARRAY):
        parsed = _parse_json(value)
        if isinstance(parsed, list):
            return parsed
        if isinstance(parsed, str):
            return [item.strip() for item in parsed.split(",") if item.strip()]
        if isinstance(parsed, (tuple, set)):
            return list(parsed)
        raise ValueError(f"invalid array for {location}")
    if column_type.__class__.__name__ == "Vector":
        parsed = _parse_json(value)
        if not isinstance(parsed, (list, tuple)):
            raise ValueError(f"invalid vector for {location}")
        try:
            vector = [float(item) for item in parsed]
        except (TypeError, ValueError) as exc:
            raise ValueError(f"invalid vector values for {location}") from exc
        dimensions = getattr(column_type, "dim", None)
        if dimensions and len(vector) != dimensions:
            raise ValueError(f"invalid vector dimension for {location}: expected {dimensions}, got {len(vector)}")
        return vector
    if isinstance(column_type, Boolean):
        if value in (True, 1, "1", "true", "True"):
            return True
        if value in (False, 0, "0", "false", "False"):
            return False
        raise ValueError(f"invalid boolean for {location}")
    if isinstance(column_type, DateTime) and isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
            if not column_type.timezone and parsed.tzinfo is not None:
                return parsed.astimezone(timezone.utc).replace(tzinfo=None)
            return parsed
        except ValueError as exc:
            raise ValueError(f"invalid timestamp for {location}") from exc
    if isinstance(column_type, Date) and not isinstance(column_type, DateTime) and isinstance(value, str):
        try:
            return date.fromisoformat(value)
        except ValueError as exc:
            raise ValueError(f"invalid date for {location}") from exc
    if isinstance(column_type, Integer) and not isinstance(value, bool):
        try:
            return int(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"invalid integer for {location}") from exc
    if isinstance(column_type, Float):
        try:
            return float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"invalid floating-point value for {location}") from exc
    if isinstance(column_type, Numeric):
        try:
            return Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError) as exc:
            raise ValueError(f"invalid numeric value for {location}") from exc
    if isinstance(column_type, Enum):
        text_value = str(value)
        if column_type.enums and text_value not in column_type.enums:
            raise ValueError(f"invalid enum for {location}: {text_value!r}")
        return text_value
    if isinstance(column_type, LargeBinary) and isinstance(value, str):
        try:
            return bytes.fromhex(value)
        except ValueError:
            return value.encode("utf-8")
    return value


def coerce_row(raw: dict[str, Any], target_table: Table, columns: Iterable[str] | None = None) -> dict[str, Any]:
    names = list(columns) if columns is not None else [column.name for column in target_table.columns if column.name in raw]
    target_columns = {column.name: column for column in target_table.columns}
    return {name: coerce_value(raw[name], target_columns[name]) for name in names}


def json_safe(value: Any) -> Any:
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, datetime):
        if value.tzinfo is not None:
            value = value.astimezone(timezone.utc)
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Decimal):
        return format(value.normalize(), "f")
    if isinstance(value, bytes):
        return value.hex()
    if hasattr(value, "tolist"):
        return json_safe(value.tolist())
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(item) for item in value]
    return value


def canonical_row(row: dict[str, Any]) -> str:
    return json.dumps(json_safe(row), sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def table_checksum(engine: Engine, table_name: str, *, schema: str | None = None) -> str:
    metadata = MetaData()
    table = Table(table_name, metadata, autoload_with=engine, schema=schema)
    order_columns = list(table.primary_key.columns) or list(table.columns)
    statement = select(table).order_by(*order_columns)
    digest = hashlib.sha256()
    with engine.connect() as connection:
        for row in connection.execute(statement).mappings():
            digest.update(canonical_row(dict(row)).encode("utf-8"))
            digest.update(b"\n")
    return digest.hexdigest()


def table_inventory(engine: Engine, *, include_checksums: bool = False) -> dict[str, Any]:
    inspector = inspect(engine)
    tables = sorted(name for name in inspector.get_table_names() if name != "alembic_version" and not name.startswith("sqlite_"))
    output: dict[str, Any] = {"tables": {}, "dialect": engine.dialect.name}
    if engine.dialect.name == "postgresql" and "alembic_version" in inspector.get_table_names():
        with engine.connect() as connection:
            output["migration_revision"] = connection.execute(select(Table("alembic_version", MetaData(), autoload_with=engine).c.version_num)).scalar_one_or_none()
    for name in tables:
        metadata = MetaData()
        table = Table(name, metadata, autoload_with=engine)
        with engine.connect() as connection:
            count = connection.execute(select(func.count()).select_from(table)).scalar_one()
        record: dict[str, Any] = {
            "row_count": int(count),
            "primary_key": [column.name for column in table.primary_key.columns],
            "columns": [
                {"name": column.name, "type": str(column.type), "nullable": bool(column.nullable), "default": str(column.server_default.arg) if column.server_default is not None else None}
                for column in table.columns
            ],
            "foreign_keys": [{"column": fk.parent.name, "target": fk.target_fullname} for fk in table.foreign_keys],
            "indexes": [
                {"name": index.get("name"), "columns": index.get("column_names", []), "unique": bool(index.get("unique"))}
                for index in inspector.get_indexes(name)
            ],
            "unique_constraints": inspector.get_unique_constraints(name),
            "check_constraints": inspector.get_check_constraints(name),
        }
        if include_checksums:
            record["checksum"] = table_checksum(engine, name)
        output["tables"][name] = record
    return output


def write_report(report: dict[str, Any], output: str | None) -> None:
    encoded = json.dumps(json_safe(report), indent=2, sort_keys=True)
    if output:
        Path(output).write_text(encoded + "\n", encoding="utf-8")
    else:
        print(encoded)
