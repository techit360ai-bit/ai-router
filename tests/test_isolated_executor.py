from pathlib import Path
from unittest.mock import patch

import pytest

from isolated_executor import ExecutionLimits, IsolatedExecutionError, execute_in_sandbox


def test_execution_fails_closed_without_sandbox(monkeypatch, tmp_path: Path):
    monkeypatch.delenv("CODE_EXECUTION_SANDBOX_ENABLED", raising=False)
    with pytest.raises(IsolatedExecutionError):
        execute_in_sandbox(["python", "-c", "print(1)"], tmp_path)


def test_execution_uses_networkless_restricted_container(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("CODE_EXECUTION_SANDBOX_ENABLED", "true")
    with patch("isolated_executor.subprocess.run") as run:
        run.return_value = type("Result", (), {"returncode": 0, "stdout": "", "stderr": ""})()
        execute_in_sandbox(["python", "main.py"], tmp_path, limits=ExecutionLimits(timeout_seconds=7, memory_mb=128, cpus=0.5, pids=16))
        args = run.call_args.args[0]
        assert "--network=none" in args
        assert "--read-only" in args
        assert "--cap-drop=ALL" in args
        assert "--memory=128m" in args
