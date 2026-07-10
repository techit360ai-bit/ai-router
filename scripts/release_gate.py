#!/usr/bin/env python3
"""Run the ai-router release-candidate gates used by CI and operators."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

ENV_CONTRACT = {
    "ENVIRONMENT": "production",
    "ALLOW_DEMO_AUTH": "false",
    "JWT_ALGORITHM": "HS256",
    "JWT_SECRET": "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
    "POSTGRES_PASSWORD": "ci-postgres-password",
    "DATABASE_URL": "postgresql://techit:secret@postgres.example:5432/techit_db",
    "REDIS_URL": "rediss://redis.example:6379",
    "CELERY_BROKER": "rediss://redis.example:6379",
    "ALLOWED_ORIGINS": "https://app.techit.example",
    "MCP_BASE_URL": "https://api.techit.example/api/mcp",
    "MCP_TIMEOUT": "10",
    "OPENAI_API_KEY": "sk-ci-contract-value",
    "ANTHROPIC_API_KEY": "sk-ant-ci-contract-value",
    "STRIPE_SECRET_KEY": "sk_live_ci_contract_value",
    "STRIPE_WEBHOOK_SECRET": "whsec_ci_contract_value",
}

TEST_ENV = {
    "ENVIRONMENT": "development",
    "ALLOW_DEMO_AUTH": "true",
    "JWT_SECRET": "test-secret-key-for-ci-only",
    "SECRET_KEY": "test-secret-key-for-ci-only",
    "DATABASE_URL": "postgresql://techit:password@localhost:5432/techit_db",
    "REDIS_URL": "redis://localhost:6379",
}


def release_gates() -> list[tuple[str, list[str], dict[str, str] | None]]:
    return [
        ("compile", [sys.executable, "-m", "compileall", "-q", "."], None),
        ("deployment-env-contract", [sys.executable, "scripts/validate_env.py"], ENV_CONTRACT),
        ("scalability-readiness", [sys.executable, "scripts/scalability_check.py"], TEST_ENV),
        ("pytest", [sys.executable, "-m", "pytest", "-q"], TEST_ENV),
    ]


def run(name: str, command: list[str], env: dict[str, str] | None = None) -> None:
    print(f"==> {name}", flush=True)
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    subprocess.run(command, cwd=ROOT, env=merged_env, check=True)


def main() -> int:
    for name, command, env in release_gates():
        try:
            run(name, command, env)
        except subprocess.CalledProcessError as exc:
            print(f"{name} failed with exit code {exc.returncode}", file=sys.stderr)
            return exc.returncode

    print("ai-router release gates OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
