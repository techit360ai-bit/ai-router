"""Profitability-aware, capability-safe model routing engine."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from execution_controls import ProviderCircuitBreaker
from model_registry import ModelDefinition, ModelRegistry, RegistryError, TaskPolicy


class ComplexityTier(Enum):
    REASONING = "reasoning"
    LONG_GENERATION = "long_generation"
    SHORT_GENERATION = "short_generation"
    CLASSIFICATION = "classification"
    CODE_GENERATION = "code_generation"
    EMBEDDING = "embedding"


@dataclass
class ModelConfig:
    id: str
    provider: str
    model_name: str
    max_context_length: int
    strengths: List[str]
    use_cases: List[Any] = field(default_factory=list)
    api_key_env: str = ""
    adapter: str = ""
    base_url: str = ""
    quality_score: float = 70
    latency_score: float = 50
    capabilities: List[str] = field(default_factory=list)
    input_cost_per_million: Optional[float] = None
    output_cost_per_million: Optional[float] = None
    user_selectable: bool = False


class ModelRouter:
    """Rank eligible models by quality, latency, health, and provider spend.

    Profitability here means infrastructure efficiency. The Router has no
    customer revenue, plan, subscription, payment, or credit information.
    """

    def __init__(self, registry: Optional[ModelRegistry] = None) -> None:
        self.registry = registry or ModelRegistry()
        self.circuit_breaker = ProviderCircuitBreaker()
        self.model_configs: Dict[str, ModelConfig] = {
            model.id: self._to_config(model) for model in self.registry.models.values()
        }
        self._validate_coverage()

    def _to_config(self, model: ModelDefinition) -> ModelConfig:
        provider = self.registry.provider_for(model)
        base_url = os.path.expandvars(provider.base_url)
        return ModelConfig(
            id=model.id,
            provider=model.provider,
            model_name=model.upstream_model,
            max_context_length=model.context_window,
            strengths=sorted(model.tags),
            api_key_env=provider.api_key_env,
            adapter=provider.adapter,
            base_url=base_url,
            quality_score=model.quality_score,
            latency_score=model.latency_score,
            capabilities=sorted(model.capabilities),
            input_cost_per_million=model.input_cost_per_million,
            output_cost_per_million=model.output_cost_per_million,
            user_selectable=model.user_selectable,
        )

    def _validate_coverage(self) -> None:
        for task_type, policy in self.registry.task_policies.items():
            if not self.registry.eligible_models(task_type):
                raise RegistryError(f"no model satisfies task policy: {task_type}")
            if policy.max_attempts < 1:
                raise RegistryError(f"task policy has invalid max_attempts: {task_type}")

    def policy_for(self, request: Any) -> TaskPolicy:
        return self.registry.task_policy(request.task_type.value)

    def _candidate_configs(self, request: Any) -> List[ModelConfig]:
        grant = getattr(request.user_context, "execution_grant", None)
        requested_model = (
            getattr(request, "requested_model", None)
            or request.input_data.get("model_id")
            or request.input_data.get("requested_model")
        )
        models = self.registry.eligible_models(
            request.task_type.value,
            requested_model=str(requested_model) if requested_model else None,
            allowed_models=grant.allowed_model_ids if grant else (),
        )
        return [self.model_configs[model.id] for model in models]

    def _is_configured(self, config: ModelConfig) -> bool:
        model = self.registry.models[config.id]
        return self.registry.is_provider_configured(model)

    @staticmethod
    def _economy_score(config: ModelConfig) -> float:
        if config.input_cost_per_million is None or config.output_cost_per_million is None:
            return 40.0
        combined = config.input_cost_per_million + config.output_cost_per_million
        return max(0.0, min(100.0, 100.0 - combined * 2.5))

    def _rank(self, candidates: List[ModelConfig], policy: TaskPolicy, profile: str) -> List[ModelConfig]:
        if policy.complexity == ComplexityTier.EMBEDDING.value and policy.preferred_models:
            preferred_index = {model_id: index for index, model_id in enumerate(policy.preferred_models)}
            return sorted(
                candidates,
                key=lambda config: (preferred_index.get(config.id, len(preferred_index)),
                                    self.registry.models[config.id].priority),
            )
        objective = profile if profile in {
            "quality", "economy", "latency", "balanced", "profitability"
        } else policy.routing_objective

        preferred_index = {model_id: index for index, model_id in enumerate(policy.preferred_models)}

        def score(config: ModelConfig) -> tuple[float, int]:
            quality = config.quality_score
            latency = config.latency_score
            economy = self._economy_score(config)
            if objective == "quality":
                value = quality * 0.75 + latency * 0.10 + economy * 0.15
            elif objective in {"economy", "profitability"}:
                value = quality * 0.45 + latency * 0.15 + economy * 0.40
            elif objective == "latency":
                value = quality * 0.30 + latency * 0.60 + economy * 0.10
            else:
                value = quality * 0.50 + latency * 0.25 + economy * 0.25
            # A task's preferred list is a deterministic tie-breaker. The
            # caller's explicit quality/economy/latency profile remains the
            # primary objective so profitability routing is observable.
            if config.id in preferred_index:
                value += max(0.0, 0.05 - preferred_index[config.id] * 0.01)
            return value, -self.registry.models[config.id].priority

        return sorted(candidates, key=score, reverse=True)

    def select_chain(self, request: Any) -> List[ModelConfig]:
        policy = self.policy_for(request)
        candidates = self._rank(
            self._candidate_configs(request),
            policy,
            getattr(request, "execution_profile", "balanced"),
        )
        grant = getattr(request.user_context, "execution_grant", None)
        budget = policy.max_provider_cost_usd
        if grant and grant.max_provider_cost_usd is not None:
            budget = min(budget, grant.max_provider_cost_usd) if budget is not None else grant.max_provider_cost_usd
        if budget is not None:
            grant_input = grant.max_input_tokens if grant else None
            grant_output = grant.max_output_tokens if grant else None
            estimated_input = max(
                1,
                len(json.dumps(getattr(request, "input_data", {}), default=str).encode("utf-8")) // 4,
            )
            input_tokens = min(policy.max_input_tokens, grant_input or policy.max_input_tokens, estimated_input)
            output_tokens = min(policy.max_output_tokens, grant_output or policy.max_output_tokens)
            candidates = [
                config for config in candidates
                if self._within_provider_budget(config, input_tokens, output_tokens, budget)
            ]

        configured = [
            config for config in candidates
            if self._is_configured(config)
            and self.circuit_breaker.is_available(f"{config.provider}:{config.model_name}")
        ]
        unconfigured = [config for config in candidates if config not in configured]
        chain = configured + unconfigured
        if not chain:
            raise RegistryError(f"no eligible model chain for {request.task_type.value}")
        return chain[: policy.max_attempts]

    @staticmethod
    def _within_provider_budget(
        config: ModelConfig,
        input_tokens: int,
        output_tokens: int,
        budget: float,
    ) -> bool:
        if config.input_cost_per_million is None or config.output_cost_per_million is None:
            return False
        estimate = (
            input_tokens / 1_000_000 * config.input_cost_per_million
            + output_tokens / 1_000_000 * config.output_cost_per_million
        )
        return estimate <= budget

    def select_model(self, request: Any) -> ModelConfig:
        return self.select_chain(request)[0]

    def list_models(self, task_type: Optional[str] = None) -> List[Dict[str, Any]]:
        return [
            {
                "id": model.id,
                "provider": model.provider,
                "quality_tier": model.quality_tier,
                "quality_score": model.quality_score,
                "context_window": model.context_window,
                "max_output_tokens": model.max_output_tokens,
                "capabilities": sorted(model.capabilities),
                "user_selectable": model.user_selectable,
                "configured": self.registry.is_provider_configured(model),
                "tags": sorted(model.tags),
            }
            for model in self.registry.selectable_models(task_type)
        ]
