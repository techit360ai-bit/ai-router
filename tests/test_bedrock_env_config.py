"""Bedrock must be configured through environment variables and IAM, not code."""

from __future__ import annotations

import json
import re
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
