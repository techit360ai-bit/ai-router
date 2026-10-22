"""Each provider's credential format is declared and verified correctly.

Azure -> api-key header; Google Gemini -> ?key= query; Bedrock -> SigV4 AWS
credential chain; every other OpenAI-compatible provider -> Bearer.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import provider_key_health as pkh
from ai_router_core import AIRequest, TaskType, UserContext, UserRole
from model_registry import ModelRegistry
from provider_adapters import _openai_compatible_url, call_provider_model


def _ctx() -> UserContext:
    return UserContext(
        user_id="u", role=UserRole.FOUNDER, project_id="p", project_stage="mvp",
        industry="saas", tech_stack=[], past_feedback=[], training_progress={},
        time_logged_today=0, tasks_completed_week=0,
    )


def _request() -> AIRequest:
    return AIRequest(task_type=TaskType.CHAT, user_context=_ctx(), input_data={})


class HTTPClient:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    async def post(self, url, **kwargs):
        self.calls.append({"url": url, **kwargs})
        return SimpleNamespace(status_code=200, json=lambda: self.payload)


class _ProbeResponse:
    """Minimal stand-in for ``http.client.HTTPResponse`` used as a context manager."""

    def __init__(self, status):
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        return False


def _azure_config(**overrides) -> SimpleNamespace:
    base = dict(
        id="azure-gpt-4o", provider="azure_openai", adapter="openai_compatible",
        model_name="gpt-4o", api_key_env="AZURE_OPENAI_API_KEY", api_key_envs=[],
        auth="azure",
        base_url="https://res.openai.azure.com/openai/deployments/dep/chat/completions?api-version=2024-02-01",
        capabilities=[],
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def _openai_config(**overrides) -> SimpleNamespace:
    base = dict(
        id="m", provider="openrouter", adapter="openai_compatible", model_name="m",
        api_key_env="OPENROUTER_API_KEY", api_key_envs=[], auth="bearer",
        base_url="https://openrouter.ai/api/v1/chat/completions", capabilities=[],
    )
    base.update(overrides)
    return SimpleNamespace(**base)


def test_azure_compatible_url_preserves_the_api_version_query() -> None:
    config = _azure_config()
    assert _openai_compatible_url(config) == config.base_url


@pytest.mark.asyncio
async def test_azure_uses_api_key_header_and_does_not_duplicate_the_path() -> None:
    client = HTTPClient({"choices": [{"message": {"content": "ok"}}], "usage": {"total_tokens": 3}})
    result = await call_provider_model(
        _azure_config(), "prompt", _request(),
        env={"AZURE_OPENAI_API_KEY": "azure-secret"}, clients={"azure_openai": client},
    )
    assert result.text == "ok"
    call = client.calls[0]
    assert call["headers"]["api-key"] == "azure-secret"
    assert "Authorization" not in call["headers"]
    assert call["url"] == "https://res.openai.azure.com/openai/deployments/dep/chat/completions?api-version=2024-02-01"


@pytest.mark.asyncio
async def test_overlay_openai_compatible_providers_still_use_bearer() -> None:
    client = HTTPClient({"choices": [{"message": {"content": "ok"}}], "usage": {"total_tokens": 3}})
    await call_provider_model(
        _openai_config(), "prompt", _request(),
        env={"OPENROUTER_API_KEY": "or-secret"}, clients={"openrouter": client},
    )
    call = client.calls[0]
    assert call["headers"]["Authorization"] == "Bearer or-secret"
    assert "api-key" not in call["headers"]
    assert call["url"] == "https://openrouter.ai/api/v1/chat/completions"


def test_azure_probe_url_is_resource_level() -> None:
    assert pkh._azure_probe_url(
        "https://r.openai.azure.com/openai/deployments/d/chat/completions?api-version=2024-02-01"
    ) == "https://r.openai.azure.com/openai/models?api-version=2024-02-01"


def test_azure_readiness_probe_sends_the_api_key_header(monkeypatch) -> None:
    captured = {}

    def fake_urlopen(request, timeout=None):
        captured["url"] = request.full_url
        captured["headers"] = {k.lower(): v for k, v in request.headers.items()}
        return _ProbeResponse(200)

    monkeypatch.setitem(pkh._active_specs, "azure_openai", {
        "url": "https://r.openai.azure.com/openai/models?api-version=2024-02-01", "auth": "azure",
    })
    monkeypatch.setattr(pkh.urllib.request, "urlopen", fake_urlopen)
    assert pkh._probe_status("azure_openai", "azure-secret") == 200
    assert captured["headers"].get("api-key") == "azure-secret"
    assert "authorization" not in captured["headers"]


def test_google_gemini_readiness_probe_uses_the_query_key(monkeypatch) -> None:
    captured = {}

    def fake_urlopen(request, timeout=None):
        captured["url"] = request.full_url
        captured["headers"] = {k.lower(): v for k, v in request.headers.items()}
        return _ProbeResponse(200)

    monkeypatch.setitem(pkh._active_specs, "google", {
        "url": "https://generativelanguage.googleapis.com/v1beta/models", "auth": "query",
    })
    monkeypatch.setattr(pkh.urllib.request, "urlopen", fake_urlopen)
    assert pkh._probe_status("google", "gemini-key") == 200
    assert "key=gemini-key" in captured["url"]
    assert "authorization" not in captured["headers"]


def test_bedrock_readiness_uses_the_sigv4_credential_chain(monkeypatch) -> None:
    monkeypatch.setattr(pkh, "_aws_credential_status", lambda: 1)
    report = pkh._credential_chain_report("bedrock", region="us-east-1", live=False)
    assert report["ok"] is True and report["valid"] == 1

    monkeypatch.setattr(pkh, "_aws_credential_status", lambda: 0)
    report = pkh._credential_chain_report("bedrock")
    assert report["ok"] is False and report["invalid"] == 1

    monkeypatch.setattr(pkh, "_aws_credential_status", lambda: 1)
    monkeypatch.setattr(pkh, "_probe_bedrock_live", lambda region: 401)
    assert pkh._credential_chain_report("bedrock", live=True)["invalid"] == 1
    monkeypatch.setattr(pkh, "_probe_bedrock_live", lambda region: 200)
    assert pkh._credential_chain_report("bedrock", live=True)["ok"] is True
    monkeypatch.setattr(pkh, "_probe_bedrock_live", lambda region: 0)
    assert pkh._credential_chain_report("bedrock", live=True)["ok"] is True


def test_registry_declares_each_provider_auth_format() -> None:
    registry = ModelRegistry()
    assert registry.providers["azure_openai"].resolved_auth == "azure"
    assert registry.providers["google_vertex"].resolved_auth == "bearer"
    assert registry.providers["google"].resolved_auth == "query"
    assert registry.providers["bedrock"].resolved_auth == "sigv4"
    assert registry.providers["bedrock"].requires_api_key is False
    assert registry.providers["openai"].resolved_auth == "bearer"
