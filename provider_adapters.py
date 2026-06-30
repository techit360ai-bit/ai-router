"""
Provider adapter boundary for the central AI command path.

The router core owns model selection and credits. This module owns the narrow
provider contract: build a provider request, call the configured client, and
normalize success/errors into a stable shape for AICommandLayer.
"""

from __future__ import annotations

import asyncio
import inspect
import json
import os
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Mapping, Optional


class ProviderError(RuntimeError):
    """Base class for provider boundary failures."""


class ProviderConfigError(ProviderError):
    """Provider cannot be called because local configuration is incomplete."""


class ProviderAuthError(ProviderError):
    """Provider rejected the configured credentials."""


class ProviderRateLimitError(ProviderError):
    """Provider rejected the request due to quota or rate limiting."""


class ProviderTimeoutError(ProviderError):
    """Provider request exceeded the configured timeout."""


class ProviderResponseError(ProviderError):
    """Provider returned an invalid or unusable response."""


@dataclass
class ProviderResponse:
    text: str
    tokens: int
    confidence: float
    duration_ms: int
    raw: Dict[str, Any] = field(default_factory=dict)

    def as_ai_output(self) -> Dict[str, Any]:
        return {
            "text": self.text,
            "tokens": self.tokens,
            "confidence": self.confidence,
            "duration_ms": self.duration_ms,
        }


OPENAI_PROVIDERS = {"openai_gpt4", "openai_gpt4_mini"}
ANTHROPIC_PROVIDERS = {"anthropic_claude", "anthropic_claude_haiku"}
COHERE_PROVIDERS = {"cohere_embed"}
GEMINI_PROVIDERS = {"gemini_flash", "gemini_flash_lite"}
OPENROUTER_PROVIDERS = {"openrouter_free"}


def _value(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, Mapping):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _provider_value(model_config: Any) -> str:
    provider = _value(model_config, "provider")
    return str(_value(provider, "value", provider))


def _model_name(model_config: Any) -> str:
    model_name = _value(model_config, "model_name")
    if not model_name:
        raise ProviderConfigError("model config is missing model_name")
    return str(model_name)


def _api_key(model_config: Any, env: Mapping[str, str]) -> str:
    api_key_env = _value(model_config, "api_key_env", "") or ""
    if not api_key_env:
        return ""
    api_key = env.get(str(api_key_env), "")
    if not api_key:
        raise ProviderConfigError(f"missing provider API key: {api_key_env}")
    return api_key


def _max_tokens(request: Any) -> int:
    return int(_value(request, "max_tokens", 2000) or 2000)


def _requires_json(request: Any) -> bool:
    return bool(_value(request, "require_structured_output", False))


def _timeout_seconds() -> float:
    raw = os.environ.get("PROVIDER_TIMEOUT", "30")
    try:
        return float(raw)
    except ValueError as exc:
        raise ProviderConfigError("PROVIDER_TIMEOUT must be numeric") from exc


def _first(items: Any) -> Any:
    if not items:
        return None
    try:
        return items[0]
    except (KeyError, IndexError, TypeError):
        return None


def _join_text_parts(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, str):
                parts.append(item)
            else:
                text = _value(item, "text")
                if text:
                    parts.append(str(text))
        return "".join(parts)
    return str(content)


def _usage_tokens(usage: Any, *keys: str) -> int:
    total = 0
    for key in keys:
        value = _value(usage, key, 0) or 0
        try:
            total += int(value)
        except (TypeError, ValueError):
            pass
    return total


def _error_message(exc: BaseException) -> str:
    message = str(exc)
    if message:
        return message
    return exc.__class__.__name__


def _provider_error(exc: BaseException, provider: str) -> ProviderError:
    if isinstance(exc, ProviderError):
        return exc
    name = exc.__class__.__name__.lower()
    status = _value(exc, "status_code", _value(exc, "status", None))
    message = _error_message(exc)
    detail = f"{provider} provider error: {message}"

    if isinstance(exc, (TimeoutError, asyncio.TimeoutError)) or "timeout" in name:
        return ProviderTimeoutError(detail)
    if status in (401, 403) or "auth" in name or "permission" in name:
        return ProviderAuthError(detail)
    if status == 429 or "ratelimit" in name or "rate_limit" in name:
        return ProviderRateLimitError(detail)
    return ProviderResponseError(detail)


def _openai_payload(model: str, prompt: str, request: Any) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "max_tokens": _max_tokens(request),
    }
    if _requires_json(request):
        payload["response_format"] = {"type": "json_object"}
    return payload


def _anthropic_payload(model: str, prompt: str, request: Any) -> Dict[str, Any]:
    return {
        "model": model,
        "max_tokens": _max_tokens(request),
        "messages": [{"role": "user", "content": prompt}],
    }


def _gemini_payload(prompt: str, request: Any) -> Dict[str, Any]:
    return {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"maxOutputTokens": _max_tokens(request)},
    }


async def _openai_client(api_key: str, timeout: float) -> Any:
    try:
        from openai import AsyncOpenAI  # type: ignore
    except ImportError as exc:
        raise ProviderConfigError("openai SDK is not installed") from exc
    return AsyncOpenAI(api_key=api_key, timeout=timeout)


async def _anthropic_client(api_key: str, timeout: float) -> Any:
    try:
        from anthropic import AsyncAnthropic  # type: ignore
    except ImportError as exc:
        raise ProviderConfigError("anthropic SDK is not installed") from exc
    return AsyncAnthropic(api_key=api_key, timeout=timeout)


async def _cohere_client(api_key: str) -> Any:
    try:
        import cohere  # type: ignore
    except ImportError as exc:
        raise ProviderConfigError("cohere SDK is not installed") from exc
    if not hasattr(cohere, "AsyncClient"):
        raise ProviderConfigError("cohere SDK does not expose AsyncClient")
    return cohere.AsyncClient(api_key)


async def _http_client(timeout: float) -> Any:
    try:
        import httpx  # type: ignore
    except ImportError as exc:
        raise ProviderConfigError("httpx is not installed") from exc
    return httpx.AsyncClient(timeout=timeout)


async def _maybe_await(value: Any) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


async def _close_created_client(client: Any, created: bool) -> None:
    if created and hasattr(client, "aclose"):
        await _maybe_await(client.aclose())


def _normalize_openai(response: Any, duration_ms: int) -> ProviderResponse:
    choice = _first(_value(response, "choices", []))
    message = _value(choice, "message", {})
    text = _join_text_parts(_value(message, "content", ""))
    usage = _value(response, "usage", {})
    tokens = _usage_tokens(usage, "total_tokens")
    if not text:
        raise ProviderResponseError("openai response did not include message text")
    return ProviderResponse(
        text=text,
        tokens=tokens,
        confidence=1.0,
        duration_ms=duration_ms,
        raw={
            "prompt_tokens": _value(usage, "prompt_tokens"),
            "completion_tokens": _value(usage, "completion_tokens"),
        },
    )


def _normalize_anthropic(response: Any, duration_ms: int) -> ProviderResponse:
    text = _join_text_parts(_value(response, "content", []))
    usage = _value(response, "usage", {})
    tokens = _usage_tokens(usage, "input_tokens", "output_tokens")
    if not text:
        raise ProviderResponseError("anthropic response did not include content text")
    return ProviderResponse(
        text=text,
        tokens=tokens,
        confidence=1.0,
        duration_ms=duration_ms,
        raw={
            "prompt_tokens": _value(usage, "input_tokens"),
            "completion_tokens": _value(usage, "output_tokens"),
        },
    )


def _normalize_cohere(response: Any, duration_ms: int) -> ProviderResponse:
    embeddings = _value(response, "embeddings", [])
    meta = _value(response, "meta", {})
    billed_units = _value(meta, "billed_units", {})
    tokens = _usage_tokens(billed_units, "input_tokens")
    if not embeddings:
        raise ProviderResponseError("cohere response did not include embeddings")
    return ProviderResponse(
        text=json.dumps({"embeddings": embeddings}),
        tokens=tokens,
        confidence=1.0,
        duration_ms=duration_ms,
        raw={"prompt_tokens": tokens, "completion_tokens": 0},
    )


def _normalize_openai_compatible(response: Mapping[str, Any], provider: str,
                                 duration_ms: int) -> ProviderResponse:
    choice = _first(response.get("choices", []))
    message = _value(choice, "message", {})
    text = _join_text_parts(_value(message, "content", ""))
    tokens = _usage_tokens(response.get("usage", {}), "total_tokens")
    if not text:
        raise ProviderResponseError(f"{provider} response did not include message text")
    usage = response.get("usage", {})
    return ProviderResponse(
        text=text,
        tokens=tokens,
        confidence=1.0,
        duration_ms=duration_ms,
        raw={
            "prompt_tokens": _value(usage, "prompt_tokens"),
            "completion_tokens": _value(usage, "completion_tokens"),
        },
    )


def _normalize_gemini(response: Mapping[str, Any], duration_ms: int) -> ProviderResponse:
    candidate = _first(response.get("candidates", []))
    content = _value(candidate, "content", {})
    parts = _value(content, "parts", [])
    text = _join_text_parts(parts)
    tokens = _usage_tokens(response.get("usageMetadata", {}), "totalTokenCount")
    if not text:
        raise ProviderResponseError("gemini response did not include content text")
    usage = response.get("usageMetadata", {})
    return ProviderResponse(
        text=text,
        tokens=tokens,
        confidence=1.0,
        duration_ms=duration_ms,
        raw={
            "prompt_tokens": _value(usage, "promptTokenCount"),
            "completion_tokens": _value(usage, "candidatesTokenCount"),
        },
    )


async def _post_json(client: Any, url: str, headers: Dict[str, str],
                     payload: Dict[str, Any], timeout: float,
                     provider: str) -> Mapping[str, Any]:
    response = await _maybe_await(client.post(url, headers=headers, json=payload, timeout=timeout))
    status_code = int(_value(response, "status_code", 200) or 200)
    data = await _maybe_await(response.json())
    if status_code in (401, 403):
        raise ProviderAuthError(f"{provider} rejected credentials")
    if status_code == 429:
        raise ProviderRateLimitError(f"{provider} rate limit exceeded")
    if status_code >= 400:
        raise ProviderResponseError(f"{provider} returned HTTP {status_code}: {data}")
    if not isinstance(data, Mapping):
        raise ProviderResponseError(f"{provider} response body was not a JSON object")
    return data


async def _call_openai(model_config: Any, prompt: str, request: Any,
                       api_key: str, clients: Mapping[str, Any],
                       elapsed_ms: Callable[[], int]) -> ProviderResponse:
    client = clients.get("openai")
    created = client is None
    if created:
        client = await _openai_client(api_key, _timeout_seconds())
    try:
        response = await _maybe_await(
            client.chat.completions.create(**_openai_payload(_model_name(model_config), prompt, request))
        )
        return _normalize_openai(response, elapsed_ms())
    finally:
        await _close_created_client(client, created)


async def _call_anthropic(model_config: Any, prompt: str, request: Any,
                          api_key: str, clients: Mapping[str, Any],
                          elapsed_ms: Callable[[], int]) -> ProviderResponse:
    client = clients.get("anthropic")
    created = client is None
    if created:
        client = await _anthropic_client(api_key, _timeout_seconds())
    try:
        response = await _maybe_await(
            client.messages.create(**_anthropic_payload(_model_name(model_config), prompt, request))
        )
        return _normalize_anthropic(response, elapsed_ms())
    finally:
        await _close_created_client(client, created)


async def _call_cohere(model_config: Any, prompt: str, api_key: str,
                       clients: Mapping[str, Any],
                       elapsed_ms: Callable[[], int]) -> ProviderResponse:
    client = clients.get("cohere")
    created = client is None
    if created:
        client = await _cohere_client(api_key)
    try:
        response = await _maybe_await(
            client.embed(texts=[prompt], model=_model_name(model_config), input_type="search_document")
        )
        return _normalize_cohere(response, elapsed_ms())
    finally:
        await _close_created_client(client, created)


async def _call_openrouter(model_config: Any, prompt: str, request: Any,
                           api_key: str, clients: Mapping[str, Any],
                           elapsed_ms: Callable[[], int]) -> ProviderResponse:
    client = clients.get("openrouter")
    created = client is None
    timeout = _timeout_seconds()
    if created:
        client = await _http_client(timeout)
    try:
        data = await _post_json(
            client,
            "https://openrouter.ai/api/v1/chat/completions",
            {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            _openai_payload(_model_name(model_config), prompt, request),
            timeout,
            "openrouter",
        )
        return _normalize_openai_compatible(data, "openrouter", elapsed_ms())
    finally:
        await _close_created_client(client, created)


async def _call_gemini(model_config: Any, prompt: str, request: Any,
                       api_key: str, clients: Mapping[str, Any],
                       elapsed_ms: Callable[[], int]) -> ProviderResponse:
    client = clients.get("gemini")
    created = client is None
    timeout = _timeout_seconds()
    if created:
        client = await _http_client(timeout)
    try:
        model = _model_name(model_config)
        data = await _post_json(
            client,
            f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}",
            {"Content-Type": "application/json"},
            _gemini_payload(prompt, request),
            timeout,
            "gemini",
        )
        return _normalize_gemini(data, elapsed_ms())
    finally:
        await _close_created_client(client, created)


async def call_provider_model(model_config: Any, prompt: str, request: Any,
                              *, env: Optional[Mapping[str, str]] = None,
                              clients: Optional[Mapping[str, Any]] = None) -> ProviderResponse:
    provider = _provider_value(model_config)
    env_map = os.environ if env is None else env
    client_map: Mapping[str, Any] = clients or {}
    api_key = _api_key(model_config, env_map)
    started = time.perf_counter()

    def elapsed_ms() -> int:
        return max(0, int((time.perf_counter() - started) * 1000))

    try:
        if provider in OPENAI_PROVIDERS:
            return await _call_openai(model_config, prompt, request, api_key, client_map, elapsed_ms)
        if provider in ANTHROPIC_PROVIDERS:
            return await _call_anthropic(model_config, prompt, request, api_key, client_map, elapsed_ms)
        if provider in COHERE_PROVIDERS:
            return await _call_cohere(model_config, prompt, api_key, client_map, elapsed_ms)
        if provider in OPENROUTER_PROVIDERS:
            return await _call_openrouter(model_config, prompt, request, api_key, client_map, elapsed_ms)
        if provider in GEMINI_PROVIDERS:
            return await _call_gemini(model_config, prompt, request, api_key, client_map, elapsed_ms)
        raise ProviderConfigError(f"unsupported model provider: {provider}")
    except ProviderError:
        raise
    except Exception as exc:  # noqa: BLE001 - normalize SDK-specific failures
        raise _provider_error(exc, provider) from exc
