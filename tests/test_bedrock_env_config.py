"""Bedrock must be configured through environment variables and IAM, not code."""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def _env_keys(path: Path) -> set[str]:
    keys: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        match = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)=", line.strip())
        if match:
            keys.add(match.group(1))
    return keys


def test_bedrock_policy_contains_the_minimum_actions() -> None:
    policy = json.loads((ROOT / "config" / "aws" / "bedrock-minimum-policy.json").read_text())
    statement = policy["Statement"][0]
    assert statement["Effect"] == "Allow"
    assert statement["Resource"] == "*"
    assert set(statement["Action"]) == {
        "bedrock:InvokeModel",
        "bedrock:InvokeModelWithResponseStream",
        "bedrock:ListFoundationModels",
    }


def test_env_example_declares_the_bedrock_credential_chain() -> None:
    keys = _env_keys(ROOT / ".env.example")
    assert {
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_SESSION_TOKEN",
        "AWS_REGION",
        "BEDROCK_ENABLED",
        "BEDROCK_REGION",
        "AI_BEDROCK_LIVE_PROBE",
    } <= keys


def test_compose_passes_bedrock_configuration_to_the_container() -> None:
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    for name in (
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_SESSION_TOKEN",
        "AWS_REGION",
        "BEDROCK_ENABLED",
        "BEDROCK_REGION",
        "AI_BEDROCK_LIVE_PROBE",
    ):
        assert re.search(rf"{name}=\$\{{{name}(?=[:}}])", compose), name


def test_sigv4_adapter_does_not_embed_static_aws_credentials() -> None:
    source = (ROOT / "provider_adapters.py").read_text(encoding="utf-8")
    assert "aws_access_key_id=" not in source
    assert "aws_secret_access_key=" not in source


def test_sync_helper_does_not_copy_aws_secrets(tmp_path: Path) -> None:
    credentials = tmp_path / "credentials"
    credentials.write_text(
        "[techit]\n"
        "aws_access_key_id = test-access-key\n"
        "aws_secret_access_key = test-secret-key\n"
        "aws_session_token = test-session-token\n",
        encoding="utf-8",
    )
    config = tmp_path / "config"
    config.write_text("[profile techit]\nregion = eu-west-1\n", encoding="utf-8")
    env_file = tmp_path / ".env"
    env = {
        **os.environ,
        "AWS_SHARED_CREDENTIALS_FILE": str(credentials),
        "AWS_CONFIG_FILE": str(config),
    }

    subprocess.run(
        [
            sys.executable,
            str(ROOT / "scripts" / "sync_aws_env.py"),
            "--profile",
            "techit",
            "--env-file",
            str(env_file),
            "--enable-bedrock",
        ],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )

    synced = env_file.read_text(encoding="utf-8")
    assert "AWS_REGION=eu-west-1" in synced
    assert "BEDROCK_REGION=eu-west-1" in synced
    assert "test-access-key" not in synced
    assert "test-secret-key" not in synced
    assert "test-session-token" not in synced
