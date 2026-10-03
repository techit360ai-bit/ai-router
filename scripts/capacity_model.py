#!/usr/bin/env python3
"""Deterministic TechIT capacity model; performs no network traffic."""

from __future__ import annotations

import json
import math
import os
from pathlib import Path
from typing import Any, Mapping


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PROFILE = ROOT / "config" / "scalability_slos.json"


def load_profile(path: str | None = None) -> dict[str, Any]:
    profile_path = Path(path or os.getenv("SCALABILITY_SLO_PATH", str(DEFAULT_PROFILE)))
    payload = json.loads(profile_path.read_text(encoding="utf-8"))
    if int(payload.get("schema_version", 0)) != 1:
        raise ValueError("unsupported scalability SLO schema")
    return payload


def model_scenario(registered_users: int, defaults: Mapping[str, Any]) -> dict[str, Any]:
    users = max(1, int(registered_users))
    active = max(1, math.ceil(users * float(defaults["peak_active_fraction"])))
    calls_per_minute = active * float(defaults["api_calls_per_active_user_per_minute"])
    rps = calls_per_minute / 60
    ai_rps = rps * float(defaults["ai_call_fraction"])
    headroom = float(defaults["headroom_multiplier"])
    ai_in_flight = math.ceil(round(ai_rps * float(defaults["ai_p95_seconds"]) * headroom, 9))
    workers = math.ceil(ai_in_flight / max(1, int(defaults["worker_concurrency"])))
    db_connections = workers * int(defaults["database_connections_per_replica"])
    return {
        "registered_users": users,
        "peak_active_users": active,
        "api_calls_per_minute": round(calls_per_minute, 2),
        "api_rps": round(rps, 2),
        "ai_rps": round(ai_rps, 2),
        "ai_in_flight_with_headroom": ai_in_flight,
        "minimum_ai_workers": workers,
        "raw_database_connections": db_connections,
        "requires_connection_pooler": db_connections > int(defaults["database_connection_limit"]),
        "provider_spend_budget_usd_per_minute": round(
            float(defaults["provider_spend_base_usd_per_minute"])
            * max(float(defaults["provider_spend_base_demand_units"]), calls_per_minute)
            / float(defaults["provider_spend_base_demand_units"]),
            2,
        ),
    }


def build_report(profile: Mapping[str, Any] | None = None) -> dict[str, Any]:
    selected = dict(profile or load_profile())
    defaults = selected["capacity_defaults"]
    return {
        "profile_version": selected["version"],
        "service_levels": selected["service_levels"],
        "scenarios": [model_scenario(value, defaults) for value in selected["scenarios"]],
    }


def main() -> int:
    print(json.dumps(build_report(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
