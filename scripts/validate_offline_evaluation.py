#!/usr/bin/env python3
"""Validate deterministic score drift while preserving the human-review gate."""

from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from offline_evaluation import run_backtests  # noqa: E402


def main() -> int:
    report = run_backtests()
    if report["drift_metrics"]["maximum_absolute_drift"] != 0:
        print("offline evaluation detected score drift", file=sys.stderr)
        return 1
    if report["calibration_metrics"]["numeric_probability_claims"] != 0:
        print("uncalibrated numeric probability claim reached the fixture report", file=sys.stderr)
        return 1
    if report["release_gate"]["status"] != "human_review_only":
        print("offline evaluation unexpectedly approved consequential automation", file=sys.stderr)
        return 1
    print("offline evaluation contract OK: human_review_only")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
