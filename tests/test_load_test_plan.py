from scripts.load_test_plan import build_plan


def test_load_plan_covers_scale_profiles_and_failure_modes() -> None:
    plan = build_plan()
    assert any(row["registered_users"] == 1_000_000 for row in plan["scenarios"])
    assert {row["traffic_profile"] for row in plan["scenarios"]} == {"read_heavy", "write_heavy", "ai_burst", "websocket"}
    assert "credential_quarantine" in plan["scenarios"][0]["failures"]
    assert "no_duplicate_jobs" in plan["integrity_assertions"]
