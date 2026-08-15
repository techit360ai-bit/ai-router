from __future__ import annotations

from scripts.release_gate import release_gates


def test_release_gate_runs_hardening_contracts_before_full_pytest() -> None:
    gates = release_gates()

    assert [name for name, _, _ in gates] == [
        "compile",
        "deployment-env-contract",
        "hardening-contracts",
        "offline-evaluation",
        "migration-head",
        "scalability-readiness",
        "pytest",
    ]
    assert gates[1][2]["ENVIRONMENT"] == "production"
    assert gates[1][2]["ALLOW_DEMO_AUTH"] == "false"
    assert gates[1][2]["REQUIRE_AI_EXECUTION_GRANT"] == "true"
    assert gates[2][1][2:4] == ["pytest", "-q"]
    assert gates[3][1][-1] == "scripts/validate_offline_evaluation.py"
    assert gates[4][1][-1] == "scripts/validate_migration_head.py"
    assert gates[5][1][-1] == "scripts/scalability_check.py"
    assert gates[6][2]["ENVIRONMENT"] == "development"
    assert gates[6][1][-2:] == ["pytest", "-q"]
