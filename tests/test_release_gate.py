from __future__ import annotations

from scripts.release_gate import release_gates


def test_release_gate_runs_compile_env_contract_and_pytest_in_order() -> None:
    gates = release_gates()

    assert [name for name, _, _ in gates] == [
        "compile",
        "deployment-env-contract",
        "pytest",
    ]
    assert gates[1][2]["ENVIRONMENT"] == "production"
    assert gates[1][2]["ALLOW_DEMO_AUTH"] == "false"
    assert gates[2][2]["ENVIRONMENT"] == "development"
    assert gates[2][1][-2:] == ["pytest", "-q"]
