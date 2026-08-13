"""Provider adapter contracts using injected clients only."""

from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from ai_router_core import AIRequest, ModelRouter, TaskType, UserContext, UserRole
from provider_adapters import ProviderConfigError, call_provider_model


def _ctx() -> UserContext:
    return UserContext(
        user_id="u", role=UserRole.FOUNDER, project_id="p", project_stage="mvp",
        industry="saas", tech_stack=[], past_feedback=[], training_progress={},
        time_logged_today=0, tasks_completed_week=0,
    )


def _request(task=TaskType.CHAT, **kwargs) -> AIRequest:
    return AIRequest(task_type=task, user_context=_ctx(), input_data={}, **kwargs)


def _model(model_id: str):
    return ModelRouter().model_configs[model_id]


class Recorder:
    def __init__(self, response):
        self.response = response
        self.calls = []

    async def create(self, **kwargs):
        self.calls.append(kwargs)
        return self.response


class HTTPClient:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    async def post(self, url, **kwargs):
        self.calls.append({"url": url, **kwargs})
        return SimpleNamespace(status_code=200, json=lambda: self.payload)


@pytest.mark.asyncio
async def test_missing_provider_key_fails_closed() -> None:
    with pytest.raises(ProviderConfigError):
        await call_provider_model(_model("gpt-5.6-luna"), "prompt", _request(), env={})


@pytest.mark.asyncio
async def test_openai_responses_payload_and_usage() -> None:
    responses = Recorder(SimpleNamespace(
        output_text="response", usage=SimpleNamespace(input_tokens=4, output_tokens=6, total_tokens=10)
    ))
    client = SimpleNamespace(responses=responses)
    result = await call_provider_model(
        _model("gpt-5.6-luna"), "prompt", _request(max_tokens=123),
        env={"OPENAI_API_KEY": "test"}, clients={"openai": client},
    )
    assert result.text == "response" and result.tokens == 10
    assert responses.calls[0] == {"model": "gpt-5.6-luna", "input": "prompt", "max_output_tokens": 123}


@pytest.mark.asyncio
async def test_anthropic_and_cohere_normalization() -> None:
    messages = Recorder(SimpleNamespace(
        content=[SimpleNamespace(text="anthropic")],
        usage=SimpleNamespace(input_tokens=3, output_tokens=2),
    ))
    anthropic = await call_provider_model(
        _model("claude-haiku-4.5"), "prompt", _request(),
        env={"ANTHROPIC_API_KEY": "test"}, clients={"anthropic": SimpleNamespace(messages=messages)},
    )
    assert anthropic.text == "anthropic" and anthropic.tokens == 5

    embed = Recorder(SimpleNamespace(
        embeddings=[[0.1, 0.2]], meta=SimpleNamespace(billed_units=SimpleNamespace(input_tokens=2))
    ))
    cohere = await call_provider_model(
        _model("cohere-embed-english-v3"), "target", _request(TaskType.EMBEDDINGS),
        env={"COHERE_API_KEY": "test"}, clients={"cohere": SimpleNamespace(embed=embed.create)},
    )
    assert json.loads(cohere.text) == {"embeddings": [[0.1, 0.2]]}


@pytest.mark.asyncio
@pytest.mark.parametrize("model_id,provider,key,url_fragment", [
    ("kimi-k2.5", "moonshot", "MOONSHOT_API_KEY", "api.moonshot.ai"),
    ("mistral-large-latest", "mistral", "MISTRAL_API_KEY", "api.mistral.ai"),
])
async def test_generic_openai_compatible_providers(model_id, provider, key, url_fragment) -> None:
    client = HTTPClient({"choices": [{"message": {"content": "ok"}}], "usage": {"total_tokens": 7}})
    result = await call_provider_model(
        _model(model_id), "prompt", _request(), env={key: "test"}, clients={provider: client}
    )
    assert result.text == "ok"
    assert url_fragment in client.calls[0]["url"]
    assert client.calls[0]["json"]["model"] == _model(model_id).model_name
