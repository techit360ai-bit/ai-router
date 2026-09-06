from scripts.capacity_model import build_report, load_profile, model_scenario


def test_capacity_profile_models_all_committed_scenarios() -> None:
    report = build_report(load_profile())
    assert [row["registered_users"] for row in report["scenarios"]] == [
        100, 500, 1_000, 5_000, 10_000, 100_000, 1_000_000,
    ]


def test_capacity_model_applies_littles_law_and_headroom() -> None:
    row = model_scenario(10_000, {
        "peak_active_fraction": 0.1,
        "api_calls_per_active_user_per_minute": 2,
        "ai_call_fraction": 0.1,
        "ai_p95_seconds": 20,
        "worker_concurrency": 10,
        "database_connections_per_replica": 10,
        "database_connection_limit": 100,
        "headroom_multiplier": 1.5,
        "provider_spend_base_usd_per_minute": 100,
        "provider_spend_base_demand_units": 10,
    })
    assert row["api_rps"] == 33.33
    assert row["ai_in_flight_with_headroom"] == 100
    assert row["minimum_ai_workers"] == 10
    assert row["provider_spend_budget_usd_per_minute"] == 20_000
