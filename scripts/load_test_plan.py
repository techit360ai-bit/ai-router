#!/usr/bin/env python3
"""Build a safe, reviewable load/failure test matrix without contacting services."""

from __future__ import annotations

import json
from typing import Any

from scripts.capacity_model import load_profile


FAILURES = [
    "provider_429",
    "provider_timeout",
    "provider_5xx",
    "credential_quarantine",
    "redis_unavailable",
    "database_pool_exhaustion",
    "worker_loss",
    "duplicate_retry",
]


def build_plan(profile: dict[str, Any] | None = None) -> dict[str, Any]:
    selected = profile or load_profile()
    return {
        "profile_version": selected["version"],
        "execution_mode": "staging_only",
        "scenarios": [
            {"registered_users": users, "traffic_profile": profile_name, "failures": FAILURES}
            for users in selected["scenarios"]
            for profile_name in ("read_heavy", "write_heavy", "ai_burst", "websocket")
        ],
        "integrity_assertions": [
            "no_duplicate_jobs",
            "no_lost_drafts",
            "no_false_delivery_state",
            "no_unauthorized_offline_action",
            "no_financial_replay",
        ],
    }


if __name__ == "__main__":
    print(json.dumps(build_plan(), indent=2))
