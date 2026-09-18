#!/usr/bin/env python3
"""Reject SQLite runtime persistence compatibility in the AI Router."""

from __future__ import annotations

import argparse
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXCLUDED_PARTS = {".git", "__pycache__", "tests", "docs", "migrations", "scripts"}
RUNTIME_SUFFIXES = {".py", ".pyi", ".toml", ".ini", ".yml", ".yaml", ".env", ".example"}
FORBIDDEN = ("sqlite://", "sqlite3", "aiosqlite", "check_same_thread")
FORBIDDEN_RUNTIME_SCHEMA = ("AI_SETTLEMENT_OUTBOX_AUTO_CREATE",)


def violations() -> list[dict[str, str | int]]:
    result = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or path.suffix not in RUNTIME_SUFFIXES:
            continue
        if any(part in EXCLUDED_PARTS for part in path.relative_to(ROOT).parts):
            continue
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except UnicodeDecodeError:
            continue
        for line_no, line in enumerate(lines, 1):
            lowered = line.lower()
            if any(pattern in lowered for pattern in FORBIDDEN) or any(pattern.lower() in lowered for pattern in FORBIDDEN_RUNTIME_SCHEMA):
                result.append({"path": str(path.relative_to(ROOT)), "line": line_no, "text": line.strip()})
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report")
    args = parser.parse_args()
    found = violations()
    if args.report:
        import json
        Path(args.report).write_text(json.dumps(found, indent=2) + "\n", encoding="utf-8")
    if found:
        for item in found:
            print(f"{item['path']}:{item['line']}: {item['text']}")
        return 1
    print("SQLite runtime retirement check passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
