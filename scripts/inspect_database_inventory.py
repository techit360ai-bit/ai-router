#!/usr/bin/env python3
"""Inspect a legacy SQLite source and/or PostgreSQL target database."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone

from database_inventory import redact_url, source_engine, source_path, table_inventory, target_engine, write_report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", help="SQLite URL or file path")
    parser.add_argument("--target", help="PostgreSQL URL; defaults to DATABASE_URL")
    parser.add_argument("--output")
    parser.add_argument("--checksums", action="store_true")
    args = parser.parse_args()
    if not args.source and not args.target:
        parser.error("provide --source, --target, or both")
    report = {"generated_at": datetime.now(timezone.utc).isoformat(), "source": None, "target": None}
    if args.source:
        engine = source_engine(args.source)
        try:
            report["source"] = {"location": str(source_path(args.source)), **table_inventory(engine, include_checksums=args.checksums)}
        finally:
            engine.dispose()
    if args.target:
        engine = target_engine(args.target)
        try:
            report["target"] = {"location": redact_url(args.target), **table_inventory(engine, include_checksums=args.checksums)}
        finally:
            engine.dispose()
    write_report(report, args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
