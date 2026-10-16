"""Provider adapter boundary for the execution-only AI command path.

This module builds provider requests and normalizes responses. It has no
customer billing, subscription, credit, payment, or paywall responsibilities.
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


# Transport features each adapter actually implements. This is a declaration of
# verified behaviour, not of provider marketing: the router never claims a
# capability (streaming, tools, structured output) it cannot honour.
_ADAPTER_FEATURES: Dict[str, frozenset[str]] = {
    "openai_responses": frozenset({"text", "structured_output", "embeddings"}),
    "openai_compatible": frozenset({"text", "structured_output"}),
    "anthropic_messages": frozenset({"text"}),
    "gemini_generate": frozenset({"text"}),
    "cohere_embed": frozenset({"embeddings"}),
    "bedrock_converse": frozenset({"text"}),
    "bedrock_bearer": frozenset({"text"}),
}


def adapter_features(adapter: str) -> set[str]:
    """Declared transport features for an adapter (verified by this module's tests)."""
    return set(_ADAPTER_FEATURES.get(str(adapter or ""), frozenset()))


def supports_streaming(adapter: str) -> bool:
    """Whether the adapter has a verified streaming path. None do yet."""
    return "streaming" in _ADAPTER_FEATURES.get(str(adapter or ""), frozenset())


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


def _value(obj: Any, key: str, default: Any = None) -> Any:
    if isinstance(obj, Mapping):
        return obj.get(key, default)
    return getattr(obj, key, default)


def _provider_value(model_config: Any) -> str:
    provider = _value(model_config, "provider")
    return str(_value(provider, "value", provider))


def _adapter_value(model_config: Any) -> str:
    return str(_value(model_config, "adapter", "") or "")


def _auth_mode(model_config: Any) -> str:
    """Declared auth mode, falling back to the adapter's registry default."""
    declared = str(_value(model_config, "auth", "") or "").strip().lower()
    if declared:
        return declared
    from model_registry import DEFAULT_AUTH_BY_ADAPTER

    return DEFAULT_AUTH_BY_ADAPTER.get(_adapter_value(model_config), "bearer")


def _region(model_config: Any) -> str:
    region = str(_value(model_config, "region", "") or "")
    region_env = str(_value(model_config, "region_env", "") or "")
    if region_env:
        region = os.getenv(region_env, "") or region
    return region or os.getenv("AWS_REGION", "us-east-1")


def _base_url(model_config: Any) -> str:
    value = os.path.expandvars(str(_value(model_config, "base_url", "") or ""))
    if not value or "${" in value:
        raise ProviderConfigError("openai-compatible provider is missing a valid base_url")
    return value


def _openai_compatible_headers(model_config: Any, api_key: str) -> Dict[str, str]:
    """Auth headers for OpenAI-compatible providers, chosen by declared auth mode.

    Azure OpenAI authenticates with an ``api-key`` header (or AAD bearer); every
    other compatible provider uses ``Authorization: Bearer``. The mode is declared
    in the registry, never sniffed from the key.
    """
    if _auth_mode(model_config) == "azure":
        return {"api-key": api_key, "Content-Type": "application/json"}
    return {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}


def _openai_compatible_url(model_config: Any) -> str:
    """Resolve the chat-completions URL, preserving any query string.

    Azure deployments embed ``?api-version=...`` after ``/chat/completions``; a
    naive ``endswith`` check would miss it and append a second path segment.
    """
    base_url = _base_url(model_config).rstrip("/")
    path, _, query = base_url.partition("?")
    if path.endswith("/chat/completions"):
        return base_url
    return f"{path}/chat/completions" + (f"?{query}" if query else "")


def _capabilities(model_config: Any) -> set[str]:
    return {str(item) for item in (_value(model_config, "capabilities", []) or [])}


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


def _timeout_seconds(request: Any = None) -> float:
    configured = _value(request, "provider_timeout_seconds", None) if request is not None else None
    if configured is not None:
        return float(configured)
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


def _openai_responses_payload(model: str, prompt: str, request: Any) -> Dict[str, Any]:
    payload: Dict[str, Any] = {
        "model": model,
        "input": prompt,
        "max_output_tokens": _max_tokens(request),
    }
    if _requires_json(request):
        payload["text"] = {"format": {"type": "json_object"}}
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


def _bedrock_converse_payload(model: str, prompt: str, request: Any) -> Dict[str, Any]:
    """Bedrock Converse API request body, shared by the SigV4 and bearer transports."""
    return {
        "modelId": model,
        "messages": [{"role": "user", "content": [{"text": prompt}]}],
        "inferenceConfig": {"maxTokens": _max_tokens(request)},
    }


async def _openai_client(api_key: str, timeout: float, base_url: str = "") -> Any:
    try:
        from openai import AsyncOpenAI  # type: ignore
    except ImportError as exc:
        raise ProviderConfigError("openai SDK is not installed") from exc
    options: Dict[str, Any] = {"api_key": api_key, "timeout": timeout}
    if base_url:
        options["base_url"] = base_url.rstrip("/")
    return AsyncOpenAI(**options)


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


async def _bedrock_client(region: str, timeout: float) -> Any:
    """AWS SDK client using the default credential chain (env, profile, IAM role).

    No static key is embedded: boto3 resolves AWS_ACCESS_KEY_ID/SECRET/TOKEN, the
    shared AWS profile, or the instance/task role at call time.
    """
    try:
        import boto3  # type: ignore
        from botocore.config import Config  # type: ignore
    except ImportError as exc:
        raise ProviderConfigError("boto3 is not installed") from exc
    config = Config(
        connect_timeout=max(1.0, timeout),
        read_timeout=max(1.0, timeout),
        retries={"max_attempts": 2},
    )
    return boto3.client("bedrock-runtime", region_name=region or None, config=config)


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


def _normalize_openai_responses(response: Any, duration_ms: int) -> ProviderResponse:
    text = _value(response, "output_text", "") or ""
    if not text:
        output_items = _value(response, "output", []) or []
        parts = []
        for item in output_items:
            for content in _value(item, "content", []) or []:
                value = _value(content, "text", "")
                if value:
                    parts.append(str(value))
        text = "\n".join(parts).strip()
    usage = _value(response, "usage", {})
    prompt_tokens = _value(usage, "input_tokens", _value(usage, "prompt_tokens", 0)) or 0
    completion_tokens = _value(usage, "output_tokens", _value(usage, "completion_tokens", 0)) or 0
    total_tokens = _value(usage, "total_tokens", int(prompt_tokens) + int(completion_tokens)) or 0
    if not text:
        raise ProviderResponseError("openai responses output did not include message text")
    return ProviderResponse(
        text=str(text),
        tokens=int(total_tokens),
        confidence=1.0,
        duration_ms=duration_ms,
        raw={"prompt_tokens": int(prompt_tokens), "completion_tokens": int(completion_tokens)},
    )


def _normalize_openai_embedding(response: Any, duration_ms: int) -> ProviderResponse:
    data = _value(response, "data", []) or []
    embeddings = [_value(item, "embedding", []) for item in data]
    embeddings = [item for item in embeddings if item]
    usage = _value(response, "usage", {})
    prompt_tokens = int(_value(usage, "prompt_tokens", _value(usage, "total_tokens", 0)) or 0)
    if not embeddings:
        raise ProviderResponseError("openai response did not include embeddings")
    return ProviderResponse(
        text=json.dumps({"embeddings": embeddings}),
        tokens=prompt_tokens,
        confidence=1.0,
        duration_ms=duration_ms,
        raw={"prompt_tokens": prompt_tokens, "completion_tokens": 0},
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


def _normalize_bedrock_converse(response: Any, duration_ms: int) -> ProviderResponse:
    output = _value(response, "output", {})
    message = _value(output, "message", {})
    content = _value(message, "content", []) or []
    text = "".join(str(_value(part, "text", "") or "") for part in content)
    usage = _value(response, "usage", {})
    prompt_tokens = int(_value(usage, "inputTokens", 0) or 0)
    completion_tokens = int(_value(usage, "outputTokens", 0) or 0)
    total_tokens = int(_value(usage, "totalTokens", prompt_tokens + completion_tokens) or 0)
    if not text:
        raise ProviderResponseError("bedrock response did not include content text")
    return ProviderResponse(
        text=text,
        tokens=total_tokens,
        confidence=1.0,
        duration_ms=duration_ms,
        raw={"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens},
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
    provider = _provider_value(model_config)
    client = clients.get(provider)
    created = client is None
    if created:
        configured_base_url = str(_value(model_config, "base_url", "") or "").strip()
        base_url = _base_url(model_config) if configured_base_url else ""
        client = await _openai_client(api_key, _timeout_seconds(request), base_url)
    try:
        model = _model_name(model_config)
        if "embedding" in _capabilities(model_config) and hasattr(client, "embeddings"):
            response = await _maybe_await(client.embeddings.create(model=model, input=prompt))
            return _normalize_openai_embedding(response, elapsed_ms())
        if _adapter_value(model_config) == "openai_responses" and hasattr(client, "responses"):
            response = await _maybe_await(
                client.responses.create(**_openai_responses_payload(model, prompt, request))
            )
            return _normalize_openai_responses(response, elapsed_ms())
        # Chat Completions remains a compatibility fallback for older SDKs and
        # existing injected clients used by local tests.
        response = await _maybe_await(
            client.chat.completions.create(**_openai_payload(model, prompt, request))
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
        client = await _anthropic_client(api_key, _timeout_seconds(request))
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


async def _call_openai_compatible(model_config: Any, prompt: str, request: Any,
                                  api_key: str, clients: Mapping[str, Any],
                                  elapsed_ms: Callable[[], int]) -> ProviderResponse:
    provider = _provider_value(model_config)
    client = clients.get(provider)
    created = client is None
    timeout = _timeout_seconds(request)
    if created:
        client = await _http_client(timeout)
    try:
        data = await _post_json(
            client,
            _openai_compatible_url(model_config),
            _openai_compatible_headers(model_config, api_key),
            _openai_payload(_model_name(model_config), prompt, request),
            timeout,
            provider,
        )
        return _normalize_openai_compatible(data, provider, elapsed_ms())
    finally:
        await _close_created_client(client, created)


async def _call_gemini(model_config: Any, prompt: str, request: Any,
                       api_key: str, clients: Mapping[str, Any],
                       elapsed_ms: Callable[[], int]) -> ProviderResponse:
    provider = _provider_value(model_config)
    client = clients.get(provider) or clients.get("gemini")
    created = client is None
    timeout = _timeout_seconds(request)
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
            provider,
        )
        return _normalize_gemini(data, elapsed_ms())
    finally:
        await _close_created_client(client, created)


async def _call_bedrock_converse(model_config: Any, prompt: str, request: Any,
                                 clients: Mapping[str, Any],
                                 elapsed_ms: Callable[[], int]) -> ProviderResponse:
    """Bedrock Runtime Converse using the AWS credential chain (SigV4)."""
    provider = _provider_value(model_config)
    client = clients.get(provider) or clients.get("bedrock")
    created = client is None
    if created:
        client = await _bedrock_client(_region(model_config), _timeout_seconds(request))
    try:
        payload = _bedrock_converse_payload(_model_name(model_config), prompt, request)
        if created:
            # boto3 is synchronous; keep the event loop free while it blocks.
            response = await asyncio.to_thread(client.converse, **payload)
        else:
            response = await _maybe_await(client.converse(**payload))
        return _normalize_bedrock_converse(response, elapsed_ms())
    finally:
        if created and hasattr(client, "close"):
            try:
                client.close()
            except Exception:  # noqa: BLE001 - closing a probe client must not mask the result
                pass


async def _call_bedrock_bearer(model_config: Any, prompt: str, request: Any,
                               api_key: str, clients: Mapping[str, Any],
                               elapsed_ms: Callable[[], int]) -> ProviderResponse:
    """Bedrock-compatible endpoints that authenticate with a bearer token."""
    provider = _provider_value(model_config)
    client = clients.get(provider) or clients.get("bedrock")
    created = client is None
    timeout = _timeout_seconds(request)
    if created:
        client = await _http_client(timeout)
    try:
        data = await _post_json(
            client,
            _base_url(model_config),
            {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            _bedrock_converse_payload(_model_name(model_config), prompt, request),
            timeout,
            provider,
        )
        return _normalize_bedrock_converse(data, elapsed_ms())
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
        adapter = _adapter_value(model_config)
        if adapter == "openai_responses":
            return await _call_openai(model_config, prompt, request, api_key, client_map, elapsed_ms)
        if adapter == "anthropic_messages":
            return await _call_anthropic(model_config, prompt, request, api_key, client_map, elapsed_ms)
        if adapter == "cohere_embed":
            return await _call_cohere(model_config, prompt, api_key, client_map, elapsed_ms)
        if adapter == "openai_compatible":
            return await _call_openai_compatible(
                model_config, prompt, request, api_key, client_map, elapsed_ms
            )
        if adapter == "gemini_generate":
            return await _call_gemini(model_config, prompt, request, api_key, client_map, elapsed_ms)
        if adapter == "bedrock_converse":
            return await _call_bedrock_converse(model_config, prompt, request, client_map, elapsed_ms)
        if adapter == "bedrock_bearer":
            return await _call_bedrock_bearer(
                model_config, prompt, request, api_key, client_map, elapsed_ms
            )
        raise ProviderConfigError(f"unsupported provider adapter: {adapter or provider}")
    except ProviderError:
        raise
    except Exception as exc:  # noqa: BLE001 - normalize SDK-specific failures
        raise _provider_error(exc, provider) from exc
