"""Bedrock adapter contracts (SigV4 credential chain and bearer), mocked clients only."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from ai_router_core import AIRequest, ModelRouter, TaskType, UserContext, UserRole
from provider_adapters import (
    ProviderAuthError,
    ProviderResponseError,
    adapter_features,
    call_provider_model,
    supports_streaming,
)


def _ctx() -> UserContext:
    return UserContext(
        user_id="u", role=UserRole.FOUNDER, project_id="p", project_stage="mvp",
        industry="saas", tech_stack=[], past_feedback=[], training_progress={},
        time_logged_today=0, tasks_completed_week=0,
    )


def _request(**kwargs) -> AIRequest:
    return AIRequest(task_type=TaskType.CHAT, user_context=_ctx(), input_data={}, **kwargs)


def _model(model_id: str):
    return ModelRouter().model_configs[model_id]


class ConverseClient:
    """Minimal stand-in for a boto3 bedrock-runtime client (synchronous)."""

    def __init__(self, response):
        self.response = response
        self.calls = []

    def converse(self, **kwargs):
        self.calls.append(kwargs)
        return self.response


class HTTPClient:
    def __init__(self, payload, status_code: int = 200):
        self.payload = payload
        self.status_code = status_code
        self.calls = []

    async def post(self, url, **kwargs):
        self.calls.append({"url": url, **kwargs})
        return SimpleNamespace(status_code=self.status_code, json=lambda: self.payload)


def _converse_response(text: str, prompt_tokens: int = 4, completion_tokens: int = 6):
    return {
        "output": {"message": {"content": [{"text": text}]}},
        "usage": {
            "inputTokens": prompt_tokens,
            "outputTokens": completion_tokens,
            "totalTokens": prompt_tokens + completion_tokens,
        },
    }


@pytest.mark.asyncio
async def test_bedrock_converse_uses_upstream_model_and_normalizes_usage() -> None:
    client = ConverseClient(_converse_response("bedrock says hi"))
    result = await call_provider_model(
        _model("bedrock-claude-sonnet"), "prompt", _request(max_tokens=111),
        env={}, clients={"bedrock": client},
    )
    assert result.text == "bedrock says hi"
    assert result.tokens == 10
    assert result.raw == {"prompt_tokens": 4, "completion_tokens": 6}
    assert client.calls[0]["modelId"] == "us.anthropic.claude-sonnet-4-6-v1:0"
    assert client.calls[0]["messages"] == [{"role": "user", "content": [{"text": "prompt"}]}]
    assert client.calls[0]["inferenceConfig"] == {"maxTokens": 111}


@pytest.mark.asyncio
async def test_bedrock_converse_registry_auth_is_sigv4_and_region_is_declared() -> None:
    model = _model("bedrock-claude-sonnet")
    assert model.auth == "sigv4"
    assert model.region == "us-east-1"
    assert model.billing_class == "paid"


@pytest.mark.asyncio
async def test_bedrock_converse_empty_content_fails_closed() -> None:
    client = ConverseClient({"output": {"message": {"content": []}}, "usage": {}})
    with pytest.raises(ProviderResponseError):
        await call_provider_model(
            _model("bedrock-claude-sonnet"), "prompt", _request(),
            env={}, clients={"bedrock": client},
        )


@pytest.mark.asyncio
async def test_bedrock_bearer_sends_bearer_token_and_normalizes() -> None:
    config = SimpleNamespace(
        id="bedrock-bearer-test", provider="bedrock_bearer", adapter="bedrock_bearer",
        model_name="anthropic.claude-3-5-sonnet", api_key_env="BEDROCK_API_KEY", api_key_envs=[],
        base_url="https://bedrock.example/v1/converse", auth="bedrock_bearer", region="us-east-1",
        capabilities=[],
    )
    client = HTTPClient(_converse_response("bearer bedrock"))
    result = await call_provider_model(
        config, "prompt", _request(), env={"BEDROCK_API_KEY": "secret"},
        clients={"bedrock_bearer": client},
    )
    assert result.text == "bearer bedrock"
    assert client.calls[0]["headers"]["Authorization"] == "Bearer secret"
    assert client.calls[0]["json"]["modelId"] == "anthropic.claude-3-5-sonnet"


@pytest.mark.asyncio
async def test_bedrock_bearer_401_maps_to_auth_error() -> None:
    config = SimpleNamespace(
        id="bedrock-bearer-test", provider="bedrock_bearer", adapter="bedrock_bearer",
        model_name="m", api_key_env="BEDROCK_API_KEY", api_key_envs=[],
        base_url="https://bedrock.example/v1/converse", auth="bedrock_bearer", capabilities=[],
    )
    client = HTTPClient({}, status_code=401)
    with pytest.raises(ProviderAuthError):
        await call_provider_model(
            config, "prompt", _request(), env={"BEDROCK_API_KEY": "bad"},
            clients={"bedrock_bearer": client},
        )


def test_adapter_feature_declarations_are_honest() -> None:
    assert "text" in adapter_features("bedrock_converse")
    assert "embeddings" in adapter_features("cohere_embed")
    assert "embeddings" not in adapter_features("bedrock_converse")
    # No adapter exposes a verified streaming path yet.
    assert supports_streaming("openai_responses") is False
    assert supports_streaming("bedrock_converse") is False


@pytest.mark.asyncio
async def test_bedrock_openai_model_invokes_through_the_same_adapter() -> None:
    client = ConverseClient(_converse_response("oss answer"))
    result = await call_provider_model(
        _model("bedrock-gpt-oss-120b"), "prompt", _request(),
        env={}, clients={"bedrock": client},
    )
    assert result.text == "oss answer"
    assert client.calls[0]["modelId"] == "openai.gpt-oss-120b-1:0"


def test_bedrock_is_unconfigured_until_its_enable_flag_is_set() -> None:
    router = ModelRouter()
    model = router.registry.models["bedrock-claude-sonnet"]
    assert router.registry.is_provider_configured(model, {}) is False
    assert router.registry.is_provider_configured(
        model, {"BEDROCK_ENABLED": "true", "AWS_REGION": "us-east-1"}
    ) is True
