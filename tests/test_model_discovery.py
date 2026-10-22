"""Discovery lists models as `discovered` (inert) and never approves them."""

from __future__ import annotations

import pytest

from model_discovery import discover
from model_registry import ModelRegistry


class FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def json(self):
        return self._payload


class FakeHTTP:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    async def get(self, url, **kwargs):
        self.calls.append({"url": url, **kwargs})
        return FakeResponse(self.payload)


class FakeBedrock:
    def __init__(self, payload):
        self.payload = payload
        self.calls = 0

    def list_foundation_models(self, **kwargs):
        self.calls += 1
        return self.payload


@pytest.mark.asyncio
async def test_openai_compatible_discovery_marks_models_discovered(monkeypatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "test")
    client = FakeHTTP({"data": [{"id": "vendor/a"}, {"id": "vendor/b"}]})
    document = await discover(ModelRegistry(), clients={"openrouter": client})
    by_id = {row["id"]: row for row in document["discovered_models"]}
    assert {"vendor/a", "vendor/b"} <= set(by_id)
    assert by_id["vendor/a"]["approval_status"] == "discovered"
    assert by_id["vendor/a"]["provider"] == "openrouter"
    assert client.calls[0]["url"].endswith("/models")


@pytest.mark.asyncio
async def test_bedrock_discovery_requires_the_enable_flag(monkeypatch) -> None:
    monkeypatch.delenv("BEDROCK_ENABLED", raising=False)
    bedrock = FakeBedrock({"modelSummaries": [{"modelId": "anthropic.claude"}]})
    document = await discover(ModelRegistry(), clients={"bedrock": bedrock})
    assert bedrock.calls == 0
    assert all(row["provider"] != "bedrock" for row in document["discovered_models"])


@pytest.mark.asyncio
async def test_bedrock_discovery_lists_models_when_enabled(monkeypatch) -> None:
    monkeypatch.setenv("BEDROCK_ENABLED", "true")
    bedrock = FakeBedrock({"modelSummaries": [
        {"modelId": "anthropic.claude", "responseStreamingSupported": True, "inputModalities": ["TEXT"]},
    ]})
    document = await discover(ModelRegistry(), clients={"bedrock": bedrock})
    row = next(r for r in document["discovered_models"] if r["provider"] == "bedrock")
    assert row["id"] == "anthropic.claude"
    assert row["approval_status"] == "discovered"
    assert row["streaming"] is True
    assert bedrock.calls == 1


@pytest.mark.asyncio
async def test_discovery_errors_do_not_break_other_providers(monkeypatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "test")

    class Boom:
        async def get(self, url, **kwargs):
            raise RuntimeError("network down")

    document = await discover(ModelRegistry(), clients={"openrouter": Boom()})
    assert document["errors"] and document["errors"][0]["provider"] == "openrouter"
    assert document["discovered_models"] == []


def test_discovered_entries_are_not_routable(monkeypatch) -> None:
    # A discovered entry has no registry presence, so it is inert by construction.
    registry = ModelRegistry()
    assert "vendor/a" not in registry.models
