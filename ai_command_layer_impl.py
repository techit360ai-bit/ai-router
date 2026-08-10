"""Execution-only AI command layer.

No customer billing, credits, subscriptions, payments, plans, or paywalls are
implemented here. The caller may provide a signed execution grant; the Router
uses it only to validate task/model/resource authorization.
"""

from __future__ import annotations

import asyncio
import json
import os
import random
import time
from datetime import datetime
from typing import Any, Dict, List, Optional
from uuid import uuid4

from execution_controls import (
    ExecutionAuthorizationError,
    ExecutionGrantReplayGuard,
    ExecutionGrantVerifier,
    ExecutionRateLimiter,
    ResponseCache,
)
from output_validation import OutputValidationError, validate_output
from execution_telemetry import ExecutionTelemetryRecorder
from provider_adapters import (
    ProviderAuthError,
    ProviderConfigError,
    ProviderError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    call_provider_model,
)


class ExecutionCommandLayer:
    def __init__(self, model_router: Any, prompt_engine: Any, safety_engine: Any,
                 provider_clients: Optional[Dict[str, Any]] = None) -> None:
        self.model_router = model_router
        self.prompt_engine = prompt_engine
        self.safety_engine = safety_engine
        self.provider_clients = provider_clients or {}
        self.execution_log: List[Dict[str, Any]] = []
        self.environment = os.getenv("ENVIRONMENT", "development").strip().lower()
        self.allow_placeholder = os.getenv("ALLOW_AI_PLACEHOLDER_RESPONSES", "false").lower() in {
            "1", "true", "yes"
        }
        self.rate_limiter = ExecutionRateLimiter()
        self.cache = ResponseCache()
        self.grant_replay_guard = ExecutionGrantReplayGuard()
        self.telemetry = ExecutionTelemetryRecorder()

    async def process_request(self, request: Any) -> Any:
        started = time.perf_counter()
        policy = self.model_router.policy_for(request)
        grant = getattr(request.user_context, "execution_grant", None)

        if os.getenv("REQUIRE_AI_EXECUTION_GRANT", "false").lower() in {"1", "true", "yes"} and grant is None:
            raise ExecutionAuthorizationError("A backend execution grant is required")
        if grant is not None:
            ExecutionGrantVerifier.validate_request(
                grant,
                user_id=request.user_context.user_id,
                task_type=request.task_type.value,
            )
            self.grant_replay_guard.consume(grant)

        await self.rate_limiter.check(
            request.user_context.user_id,
            getattr(request.user_context, "workspace_id", None),
        )
        safety = await self.safety_engine.validate_request(request)
        if not safety.approved:
            raise PermissionError(f"Request blocked: {safety.reason}")

        max_output = min(int(request.max_tokens or policy.max_output_tokens), policy.max_output_tokens)
        if grant and grant.max_output_tokens is not None:
            max_output = min(max_output, grant.max_output_tokens)
        request.max_tokens = max(1, max_output)
        request.provider_timeout_seconds = policy.timeout_seconds

        context = {
            "user": request.user_context.to_prompt_context(),
            "input": request.input_data,
            "timestamp": datetime.now().isoformat(),
        }
        if request.ip_protected:
            context["ip_protection_notice"] = (
                "\nIP PROTECTION ACTIVE: This content is confidential. "
                "Do not retain or use for training.\n"
            )

        prompt = await self.prompt_engine.build_prompt(
            request.task_type, context, request.user_context.role
        )
        max_input_tokens = policy.max_input_tokens
        if grant and grant.max_input_tokens is not None:
            max_input_tokens = min(max_input_tokens, grant.max_input_tokens)
        estimated_input_tokens = max(1, len(prompt.encode("utf-8")) // 4)
        if estimated_input_tokens > max_input_tokens:
            raise ExecutionAuthorizationError(
                f"Input exceeds task token budget ({estimated_input_tokens} > {max_input_tokens})"
            )
        request_id = str(uuid4())
        cache_key = self.cache.key(
            user_id=request.user_context.user_id,
            workspace_id=getattr(request.user_context, "workspace_id", None),
            task_type=request.task_type.value,
            payload={
                "prompt": prompt,
                "profile": request.execution_profile,
                "requested_model": request.requested_model,
                "schema": request.output_schema or policy.output_schema,
            },
        )
        cache_allowed = (
            request.use_cache
            and not request.ip_protected
            and policy.cache_ttl_seconds > 0
        )
        if cache_allowed:
            cached = await self.cache.get(cache_key)
            if cached:
                return self._build_response(
                    request, cached, request_id, started, cached=True
                )

        chain = self.model_router.select_chain(request)
        response = await self._execute_with_fallback(chain, prompt, request, policy, request_id)
        if cache_allowed:
            await self.cache.set(cache_key, {
                "text": response.output,
                "model": response.model_used,
                "provider": response.provider,
                "prompt_tokens": response.prompt_tokens,
                "completion_tokens": response.completion_tokens,
                "total_tokens": response.tokens_used,
                "confidence": response.confidence_score,
                "duration_ms": response.execution_time_ms,
                "provider_cost_usd": response.provider_cost_usd,
                "metadata": response.metadata,
            }, policy.cache_ttl_seconds)
        await self._record_execution(request, response, started)
        return response

    async def _execute_with_fallback(self, chain: List[Any], prompt: str,
                                     request: Any, policy: Any, request_id: str) -> Any:
        last_exc: Optional[Exception] = None
        attempt_number = 0
        for config in chain:
            circuit_key = f"{config.provider}:{config.model_name}"
            retries = max(0, int(policy.same_provider_retries))
            for retry_number in range(retries + 1):
                attempt_number += 1
                attempt_started = time.perf_counter()
                try:
                    output = await asyncio.wait_for(
                        self._call_llm(config, prompt, request),
                        timeout=max(1.0, float(policy.timeout_seconds)),
                    )
                    schema = request.output_schema or policy.output_schema
                    if policy.structured_output or request.require_structured_output or schema:
                        validate_output(output["text"], schema or {"type": "object"})
                    self.model_router.circuit_breaker.record_success(circuit_key)
                    output["attempt"] = attempt_number
                    output["retry_number"] = retry_number
                    output["provider"] = config.provider
                    output["model"] = config.model_name
                    output["provider_cost_usd"] = self._provider_cost(config, output)
                    output["request_id"] = request_id
                    output["attempt_latency_ms"] = int((time.perf_counter() - attempt_started) * 1000)
                    await self._record_successful_attempt(
                        request, config, request_id, attempt_number, output, attempt_started
                    )
                    return self._build_response(request, output, request_id, time.perf_counter())
                except Exception as exc:  # noqa: BLE001 - fallback boundary
                    if isinstance(exc, (asyncio.TimeoutError, TimeoutError)):
                        exc = ProviderTimeoutError(
                            f"{config.provider} exceeded task timeout of {policy.timeout_seconds}s"
                        )
                    last_exc = exc
                    self.model_router.circuit_breaker.record_failure(circuit_key)
                    await self._record_failed_attempt(request, config, request_id, attempt_number, exc, attempt_started)
                    if not self._retryable(exc) or retry_number >= retries:
                        break
                    await asyncio.sleep(min(2.0, 0.25 * (2 ** retry_number) + random.random() * 0.15))
        if last_exc:
            raise last_exc
        raise RuntimeError("empty model chain")

    @staticmethod
    def _retryable(exc: Exception) -> bool:
        return isinstance(exc, (ProviderRateLimitError, ProviderTimeoutError))

    @staticmethod
    def _provider_cost(config: Any, output: Dict[str, Any]) -> Optional[float]:
        if config.input_cost_per_million is None or config.output_cost_per_million is None:
            return None
        return round(
            int(output.get("prompt_tokens") or 0) / 1_000_000 * config.input_cost_per_million
            + int(output.get("completion_tokens") or 0) / 1_000_000 * config.output_cost_per_million,
            8,
        )

    async def _call_llm(self, model_config: Any, prompt: str, request: Any) -> Dict[str, Any]:
        provider = str(model_config.provider)
        if model_config.api_key_env and not os.environ.get(model_config.api_key_env):
            if self.allow_placeholder and self.environment not in {"production", "staging"}:
                return {"text": f"AI placeholder response via {model_config.model_name}", "tokens": 0,
                        "prompt_tokens": 0, "completion_tokens": 0, "confidence": 0.0, "duration_ms": 0}
            raise ProviderConfigError(f"{provider} requires {model_config.api_key_env}")
        try:
            response = await call_provider_model(model_config, prompt, request, clients=self.provider_clients)
            output = response.as_ai_output()
            output["prompt_tokens"] = response.raw.get("prompt_tokens") or 0
            output["completion_tokens"] = response.raw.get("completion_tokens") or 0
            output["tokens"] = int(response.tokens or 0)
            return output
        except ProviderError:
            raise
        except Exception as exc:  # noqa: BLE001
            raise ProviderError(f"{provider} provider execution failed: {exc}") from exc

    def _build_response(self, request: Any, output: Dict[str, Any], request_id: str,
                        started: float, cached: bool = False) -> Any:
        from ai_router_core import AIResponse
        prompt_tokens = int(output.get("prompt_tokens") or 0)
        completion_tokens = int(output.get("completion_tokens") or 0)
        total_tokens = int(output.get("tokens") or prompt_tokens + completion_tokens)
        response = AIResponse(
            task_type=request.task_type,
            output=str(output.get("text") or ""),
            model_used=str(output.get("model") or output.get("model_used") or "unknown"),
            provider=str(output.get("provider") or "unknown"),
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            tokens_used=total_tokens,
            confidence_score=float(output.get("confidence", 1.0)),
            execution_time_ms=int(output.get("duration_ms") or ((time.perf_counter() - started) * 1000)),
            provider_cost_usd=output.get("provider_cost_usd"),
            cached=cached,
            metadata={
                **(output.get("metadata") or {}),
                "request_id": request_id,
                "attempt": output.get("attempt", 0),
                "retry_number": output.get("retry_number", 0),
                "cache_hit": cached,
                "provider_cost_usd": output.get("provider_cost_usd"),
            },
        )
        return response

    async def _record_failed_attempt(self, request: Any, config: Any, request_id: str,
                                     attempt: int, exc: Exception, started: float) -> None:
        event = {
            "event": "provider_attempt",
            "request_id": request_id,
            "attempt": attempt,
            "user_id": request.user_context.user_id,
            "workspace_id": getattr(request.user_context, "workspace_id", None),
            "task_type": request.task_type.value,
            "provider": config.provider,
            "model": config.model_name,
            "status": "failed",
            "error_type": type(exc).__name__,
            "error": str(exc)[:500],
            "latency_ms": int((time.perf_counter() - started) * 1000),
            "timestamp": datetime.now().isoformat(),
            "ip_protected": request.ip_protected,
        }
        self.execution_log.append(event)
        await self.telemetry.record_attempt(event)

    async def _record_successful_attempt(self, request: Any, config: Any, request_id: str,
                                         attempt: int, output: Dict[str, Any], started: float) -> None:
        event = {
            "event": "provider_attempt",
            "request_id": request_id,
            "attempt": attempt,
            "user_id": request.user_context.user_id,
            "workspace_id": getattr(request.user_context, "workspace_id", None),
            "task_type": request.task_type.value,
            "provider": config.provider,
            "model": config.model_name,
            "status": "success",
            "prompt_tokens": int(output.get("prompt_tokens") or 0),
            "completion_tokens": int(output.get("completion_tokens") or 0),
            "total_tokens": int(output.get("tokens") or 0),
            "provider_cost_usd": output.get("provider_cost_usd"),
            "latency_ms": int((time.perf_counter() - started) * 1000),
            "timestamp": datetime.now().isoformat(),
            "error_type": None,
            "error": None,
            "ip_protected": request.ip_protected,
        }
        self.execution_log.append(event)
        await self.telemetry.record_attempt(event)

    async def _record_execution(self, request: Any, response: Any, started: float) -> None:
        event = {
            "event": "ai_execution",
            "request_id": response.metadata.get("request_id"),
            "user_id": request.user_context.user_id,
            "workspace_id": getattr(request.user_context, "workspace_id", None),
            "task_type": request.task_type.value,
            "provider": response.provider,
            "model": response.model_used,
            "status": "success",
            "prompt_tokens": response.prompt_tokens,
            "completion_tokens": response.completion_tokens,
            "total_tokens": response.tokens_used,
            "provider_cost_usd": response.provider_cost_usd,
            "latency_ms": response.execution_time_ms,
            "cache_hit": response.cached,
            "ip_protected": request.ip_protected,
            "timestamp": datetime.now().isoformat(),
        }
        self.execution_log.append(event)
