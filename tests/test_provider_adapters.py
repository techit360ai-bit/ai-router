"""
Provider adapter contract tests. Standalone (no pytest dependency): run with
    python3 tests/test_provider_adapters.py
Exit 0 = all asserts passed. Uses fake clients only; no provider network calls.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from types import SimpleNamespace
from typing import Any, Dict, List

# Allow running from repo root or tests/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ai_router_core import (  # noqa: E402
    AICommandLayer,
    AIRequest,
    ModelProvider,
    ModelRouter,
    PromptEngine,
    SafetyEngine,
    SubscriptionTier,
    TaskType,
    UserContext,
    UserRole,
)
from provider_adapters import (  # noqa: E402
    ProviderAuthError,
    ProviderConfigError,
    ProviderTimeoutError,
    call_provider_model,
)


class FakeOpenAICompletions:
    def __init__(self) -> None:
        self.calls: List[Dict[str, Any]] = []

    async def create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=SimpleNamespace(content="OpenAI normalized response")
                )
            ],
            usage=SimpleNamespace(total_tokens=42),
        )


class FakeOpenAIClient:
    def __init__(self) -> None:
        self.completions = FakeOpenAICompletions()
        self.chat = SimpleNamespace(completions=self.completions)


class FakeAnthropicMessages:
    def __init__(self) -> None:
        self.calls: List[Dict[str, Any]] = []

    async def create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        return SimpleNamespace(
            content=[SimpleNamespace(text="Anthropic normalized response")],
            usage=SimpleNamespace(input_tokens=11, output_tokens=13),
        )


class FakeAnthropicClient:
    def __init__(self) -> None:
        self.messages = FakeAnthropicMessages()


class FakeCohereClient:
    def __init__(self) -> None:
        self.calls: List[Dict[str, Any]] = []

    async def embed(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        return SimpleNamespace(
            embeddings=[[0.1, 0.2, 0.3]],
            meta=SimpleNamespace(billed_units=SimpleNamespace(input_tokens=17)),
        )


class FakeHTTPResponse:
    def __init__(self, payload: Dict[str, Any], status_code: int = 200) -> None:
        self.payload = payload
        self.status_code = status_code

    def json(self) -> Dict[str, Any]:
        return self.payload


class FakeHTTPClient:
    def __init__(self, response: FakeHTTPResponse | None = None,
                 error: Exception | None = None) -> None:
        self.response = response
        self.error = error
        self.calls: List[Dict[str, Any]] = []

    async def post(self, url: str, **kwargs: Any) -> FakeHTTPResponse:
        self.calls.append({"url": url, **kwargs})
        if self.error:
            raise self.error
        assert self.response is not None
        return self.response


class StatusError(Exception):
    def __init__(self, status_code: int, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code


def _user(tier: SubscriptionTier = SubscriptionTier.FOUNDER_PRO) -> UserContext:
    return UserContext(
        user_id="u_test",
        role=UserRole.FOUNDER,
        subscription_tier=tier,
        credits_remaining=100,
        project_id="p_test",
        project_stage="mvp",
        industry="saas",
        tech_stack=[],
        past_feedback=[],
        training_progress={},
        time_logged_today=0,
        tasks_completed_week=0,
    )


def _req(task: TaskType = TaskType.CHAT, **kwargs: Any) -> AIRequest:
    return AIRequest(task_type=task, user_context=_user(), input_data={}, **kwargs)


def _model(provider: ModelProvider):
    return ModelRouter().model_configs[provider]


def test_missing_provider_key_fails_before_client_call() -> None:
    async def run() -> None:
        try:
            await call_provider_model(
                _model(ModelProvider.OPENAI_GPT4_MINI),
                "prompt",
                _req(),
                env={},
                clients={"openai": FakeOpenAIClient()},
            )
        except ProviderConfigError as exc:
            assert "OPENAI_API_KEY" in str(exc)
            return
        raise AssertionError("missing API key did not raise ProviderConfigError")

    asyncio.run(run())


def test_openai_payload_and_response_normalization() -> None:
    async def run() -> None:
        client = FakeOpenAIClient()
        response = await call_provider_model(
            _model(ModelProvider.OPENAI_GPT4_MINI),
            "structured prompt",
            _req(max_tokens=123, require_structured_output=True),
            env={"OPENAI_API_KEY": "sk-test"},
            clients={"openai": client},
        )
        assert response.text == "OpenAI normalized response"
        assert response.tokens == 42
        assert response.confidence == 1.0
        call = client.completions.calls[0]
        assert call["model"] == "gpt-4o-mini"
        assert call["max_tokens"] == 123
        assert call["messages"] == [{"role": "user", "content": "structured prompt"}]
        assert call["response_format"] == {"type": "json_object"}

    asyncio.run(run())


def test_anthropic_payload_and_response_normalization() -> None:
    async def run() -> None:
        client = FakeAnthropicClient()
        response = await call_provider_model(
            _model(ModelProvider.ANTHROPIC_HAIKU),
            "prompt",
            _req(max_tokens=50),
            env={"ANTHROPIC_API_KEY": "sk-ant-test"},
            clients={"anthropic": client},
        )
        assert response.text == "Anthropic normalized response"
        assert response.tokens == 24
        assert client.messages.calls[0]["model"] == "claude-haiku-4-5-20251001"
        assert client.messages.calls[0]["messages"] == [{"role": "user", "content": "prompt"}]

    asyncio.run(run())


def test_cohere_embeddings_are_normalized_without_network() -> None:
    async def run() -> None:
        client = FakeCohereClient()
        response = await call_provider_model(
            _model(ModelProvider.COHERE_EMBED),
            "embedding target",
            _req(TaskType.EMBEDDINGS),
            env={"COHERE_API_KEY": "co-test"},
            clients={"cohere": client},
        )
        assert json.loads(response.text) == {"embeddings": [[0.1, 0.2, 0.3]]}
        assert response.tokens == 17
        assert client.calls[0] == {
            "texts": ["embedding target"],
            "model": "embed-english-v3.0",
            "input_type": "search_document",
        }

    asyncio.run(run())


def test_openrouter_and_gemini_http_payloads_are_normalized() -> None:
    async def run() -> None:
        openrouter = FakeHTTPClient(FakeHTTPResponse({
            "choices": [{"message": {"content": "OpenRouter response"}}],
            "usage": {"total_tokens": 8},
        }))
        openrouter_response = await call_provider_model(
            _model(ModelProvider.OPENROUTER_FREE),
            "fallback prompt",
            _req(max_tokens=77),
            env={"OPENROUTER_API_KEY": "or-test"},
            clients={"openrouter": openrouter},
        )
        assert openrouter_response.text == "OpenRouter response"
        assert openrouter_response.tokens == 8
        assert openrouter.calls[0]["json"]["model"] == "meta-llama/llama-3.3-70b-instruct:free"
        assert openrouter.calls[0]["headers"]["Authorization"] == "Bearer or-test"

        gemini = FakeHTTPClient(FakeHTTPResponse({
            "candidates": [{"content": {"parts": [{"text": "Gemini response"}]}}],
            "usageMetadata": {"totalTokenCount": 9},
        }))
        gemini_response = await call_provider_model(
            _model(ModelProvider.GEMINI_FLASH_LITE),
            "light prompt",
            _req(max_tokens=25),
            env={"GEMINI_API_KEY": "gm-test"},
            clients={"gemini": gemini},
        )
        assert gemini_response.text == "Gemini response"
        assert gemini_response.tokens == 9
        assert "gemini-2.0-flash-lite:generateContent?key=gm-test" in gemini.calls[0]["url"]
        assert gemini.calls[0]["json"]["generationConfig"] == {"maxOutputTokens": 25}

    asyncio.run(run())


def test_provider_errors_are_normalized() -> None:
    async def run() -> None:
        try:
            await call_provider_model(
                _model(ModelProvider.OPENAI_GPT4_MINI),
                "prompt",
                _req(),
                env={"OPENAI_API_KEY": "sk-test"},
                clients={"openai": SimpleNamespace(
                    chat=SimpleNamespace(
                        completions=SimpleNamespace(
                            create=lambda **_: (_ for _ in ()).throw(StatusError(401, "bad key"))
                        )
                    )
                )},
            )
        except ProviderAuthError:
            pass
        else:
            raise AssertionError("auth failure was not normalized")

        try:
            await call_provider_model(
                _model(ModelProvider.OPENROUTER_FREE),
                "prompt",
                _req(),
                env={"OPENROUTER_API_KEY": "or-test"},
                clients={"openrouter": FakeHTTPClient(error=TimeoutError("slow provider"))},
            )
        except ProviderTimeoutError:
            return
        raise AssertionError("timeout was not normalized")

    asyncio.run(run())


def test_ai_command_layer_falls_back_to_next_provider_adapter() -> None:
    async def run() -> None:
        os.environ["OPENAI_API_KEY"] = "sk-test"
        os.environ["ANTHROPIC_API_KEY"] = "sk-ant-test"
        try:
            openai = SimpleNamespace(
                chat=SimpleNamespace(
                    completions=SimpleNamespace(
                        create=lambda **_: (_ for _ in ()).throw(StatusError(429, "quota"))
                    )
                )
            )
            anthropic = FakeAnthropicClient()
            brain = AICommandLayer(
                ModelRouter(),
                PromptEngine(),
                SafetyEngine(),
                provider_clients={"openai": openai, "anthropic": anthropic},
            )
            chain = [
                _model(ModelProvider.OPENAI_GPT4),
                _model(ModelProvider.ANTHROPIC_CLAUDE),
            ]
            response = await brain._execute_with_retry(chain, "prompt", _req(TaskType.UNICORN_ANALYSIS))
            assert response.output == "Anthropic normalized response"
            assert response.model_used == "claude-sonnet-4-6"
            assert response.metadata["attempt"] == 2
            assert response.metadata["provider"] == "anthropic_claude"
        finally:
            os.environ.pop("OPENAI_API_KEY", None)
            os.environ.pop("ANTHROPIC_API_KEY", None)

    asyncio.run(run())


def main() -> int:
    tests = [
        test_missing_provider_key_fails_before_client_call,
        test_openai_payload_and_response_normalization,
        test_anthropic_payload_and_response_normalization,
        test_cohere_embeddings_are_normalized_without_network,
        test_openrouter_and_gemini_http_payloads_are_normalized,
        test_provider_errors_are_normalized,
        test_ai_command_layer_falls_back_to_next_provider_adapter,
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print(f"\nAll {len(tests)} provider adapter tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
