#!/usr/bin/env python3
"""Ensure CI deploys the migration head required by hardening contracts."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXPECTED_HEAD = "bc23de45fa67"


def main() -> int:
    result = subprocess.run(
        ["alembic", "heads"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    heads = [line.split()[0] for line in result.stdout.splitlines() if line.strip()]
    if heads != [EXPECTED_HEAD]:
        print(f"expected Alembic head {EXPECTED_HEAD}, found {heads}", file=sys.stderr)
        return 1
    print(f"alembic migration head OK: {EXPECTED_HEAD}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
