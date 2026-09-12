"""Least-privilege code execution adapter.

Generated code is executed only through a disposable container runtime. The
adapter fails closed when the runtime is unavailable; it never falls back to
the application process.
"""
from __future__ import annotations

import os
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


@dataclass(frozen=True)
class ExecutionLimits:
    timeout_seconds: int = 30
    memory_mb: int = 512
    cpus: float = 1.0
    pids: int = 64


class IsolatedExecutionError(RuntimeError):
    pass


def execute_in_sandbox(command: Sequence[str], workspace: str | Path, *, limits: ExecutionLimits | None = None) -> subprocess.CompletedProcess[str]:
    limits = limits or ExecutionLimits()
    image = os.getenv("CODE_EXECUTION_SANDBOX_IMAGE", "techit/code-sandbox:latest").strip()
    if not image or not os.getenv("CODE_EXECUTION_SANDBOX_ENABLED", "false").lower() in {"1", "true", "yes"}:
        raise IsolatedExecutionError("isolated_code_execution_not_enabled")
    root = Path(workspace).resolve()
    if not root.is_dir():
        raise IsolatedExecutionError("workspace_not_found")
    with tempfile.TemporaryDirectory(prefix="techit-exec-") as temp:
        cmd = ["docker", "run", "--rm", "--network=none", "--read-only", "--cap-drop=ALL", "--security-opt=no-new-privileges", f"--memory={int(limits.memory_mb)}m", f"--cpus={limits.cpus}", f"--pids-limit={int(limits.pids)}", "--tmpfs=/tmp:rw,noexec,nosuid,size=64m", "-v", f"{root}:/workspace:ro", "-v", f"{temp}:/output:rw", "--workdir=/workspace", image, *[str(item) for item in command]]
        try:
            return subprocess.run(cmd, text=True, capture_output=True, timeout=max(1, int(limits.timeout_seconds)), check=False, env={"PATH": "/usr/bin:/bin"})
        except subprocess.TimeoutExpired as exc:
            raise IsolatedExecutionError("sandbox_timeout") from exc
        except OSError as exc:
            raise IsolatedExecutionError("sandbox_runtime_unavailable") from exc
