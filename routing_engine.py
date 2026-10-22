"""Profitability-aware, capability-safe model routing engine."""

from __future__ import annotations

import json
import os
import hashlib
import threading
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional

from execution_controls import ExecutionAuthorizationError, ProviderCircuitBreaker
from model_registry import ModelDefinition, ModelRegistry, RegistryError, TaskPolicy

def _exclude_unconfigured() -> bool:
    """Whether to drop credential-less providers from the attempt chain.

    Defaults on; set ``AI_ROUTER_EXCLUDE_UNCONFIGURED=false`` to restore the old
    behaviour of appending unconfigured providers as last-resort attempts.
    """
    return os.getenv("AI_ROUTER_EXCLUDE_UNCONFIGURED", "true").strip().lower() in {"1", "true", "yes", "on"}


class ComplexityTier(Enum):
    REASONING = "reasoning"
    LONG_GENERATION = "long_generation"
    SHORT_GENERATION = "short_generation"
    CLASSIFICATION = "classification"
    CODE_GENERATION = "code_generation"
    EMBEDDING = "embedding"


@dataclass(frozen=True)
class ComplexityAssessment:
    tier: str
    score: float
    signals: Dict[str, float]


class TaskComplexityClassifier:
    """Deterministic request classifier that stays open to future models/providers."""

    def classify(self, request: Any, policy: TaskPolicy) -> ComplexityAssessment:
        if policy.complexity == ComplexityTier.EMBEDDING.value:
            return ComplexityAssessment(ComplexityTier.EMBEDDING.value, 0.2, {"embedding": 1.0})
        payload = getattr(request, "input_data", {}) or {}
        raw = json.dumps(payload, default=str)
        chars = len(raw)
        nesting = self._depth(payload)
        lowered = raw.lower()
        code_signal = 1.0 if any(token in lowered for token in ("```", "function ", "class ", "import ", "schema", "api route", "repository")) else 0.0
        reasoning_signal = min(1.0, sum(token in lowered for token in ("compare", "why", "evidence", "tradeoff", "assumption", "contradiction", "validate", "strategy")) / 4.0)
        context_signal = min(1.0, chars / 40_000)
        nesting_signal = min(1.0, nesting / 8.0)
        output_signal = min(1.0, float(getattr(request, "max_tokens", 0) or 0) / 10_000)
        policy_signal = 1.0 if policy.complexity in {ComplexityTier.REASONING.value, ComplexityTier.CODE_GENERATION.value, ComplexityTier.LONG_GENERATION.value} else 0.0
        score = round(min(1.0, 0.15 * policy_signal + 0.25 * context_signal + 0.15 * nesting_signal + 0.25 * code_signal + 0.15 * reasoning_signal + 0.05 * output_signal), 3)
        if code_signal and score >= 0.20: tier = ComplexityTier.CODE_GENERATION.value
        elif score >= 0.68: tier = ComplexityTier.REASONING.value
        elif chars >= 18_000 or output_signal >= 0.65: tier = ComplexityTier.LONG_GENERATION.value
        elif score <= 0.16 and chars < 2_000: tier = ComplexityTier.CLASSIFICATION.value
        else: tier = policy.complexity
        return ComplexityAssessment(tier, score, {"policy": policy_signal, "context": context_signal, "nesting": nesting_signal, "code": code_signal, "reasoning": reasoning_signal, "output": output_signal})

    def _depth(self, value: Any, current: int = 0) -> int:
        if isinstance(value, dict): return max([current] + [self._depth(v, current + 1) for v in value.values()])
        if isinstance(value, list): return max([current] + [self._depth(v, current + 1) for v in value])
        return current


class RoutingFeedbackStore:
    """Thread-safe EWMA feedback used as a bounded routing signal."""
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._values: Dict[str, Dict[str, float]] = {}

    def record(self, model_id: str, *, success: bool, latency_ms: float, quality: float = 1.0) -> None:
        with self._lock:
            prior = self._values.get(model_id, {"success": 1.0, "latency": 1000.0, "quality": 0.8, "samples": 0.0})
            alpha = 0.15
            self._values[model_id] = {"success": prior["success"] * (1-alpha) + float(success) * alpha, "latency": prior["latency"] * (1-alpha) + max(1.0, latency_ms) * alpha, "quality": prior["quality"] * (1-alpha) + max(0.0, min(1.0, quality)) * alpha, "samples": prior["samples"] + 1}

    def adjustment(self, model_id: str) -> float:
        value = self._values.get(model_id)
        if not value or value["samples"] < 3: return 0.0
        latency = max(-1.0, min(1.0, (2000.0 - value["latency"]) / 2000.0))
        return max(-8.0, min(8.0, (value["success"] - 0.9) * 20 + (value["quality"] - 0.8) * 15 + latency * 2))


@dataclass
class ModelConfig:
    id: str
    provider: str
    model_name: str
    max_context_length: int
    strengths: List[str]
    use_cases: List[Any] = field(default_factory=list)
    api_key_env: str = ""
    api_key_envs: List[str] = field(default_factory=list)
    adapter: str = ""
    base_url: str = ""
    region: str = ""
    region_env: str = ""
    auth: str = ""
    billing_class: str = "paid"
    approval_status: str = "approved"
    quality_score: float = 70
    latency_score: float = 50
    capabilities: List[str] = field(default_factory=list)
    input_cost_per_million: Optional[float] = None
    output_cost_per_million: Optional[float] = None
    user_selectable: bool = False
    lease_id: str = ""
    traffic_percent: float = 0.0
    daily_spend_cap_usd: Optional[float] = None
    pricing_source: str = "registry"
    pending_reconciliation: bool = False


class ModelRouter:
    """Rank eligible models by quality, latency, health, and provider spend.

    Profitability here means infrastructure efficiency. The Router has no
    customer revenue, plan, subscription, payment, or credit information.
    """

    def __init__(self, registry: Optional[ModelRegistry] = None) -> None:
        self.registry = registry or ModelRegistry()
        self.circuit_breaker = ProviderCircuitBreaker()
        self.complexity_classifier = TaskComplexityClassifier()
        self.feedback = RoutingFeedbackStore()
        self.runtime_controls = self._load_runtime_controls()
        self.model_configs: Dict[str, ModelConfig] = {
            model.id: self._to_config(model) for model in self.registry.models.values()
        }
        self._validate_coverage()

    @staticmethod
    def _load_runtime_controls() -> Dict[str, Any]:
        path = os.getenv("ROUTING_RUNTIME_CONFIG", os.path.join(os.path.dirname(__file__), "config", "routing_runtime.json"))
        try:
            with open(path, "r", encoding="utf-8") as handle:
                value = json.load(handle)
                return value if isinstance(value, dict) else {}
        except (OSError, ValueError):
            return {}

    def classify_request(self, request: Any) -> ComplexityAssessment:
        return self.complexity_classifier.classify(request, self.policy_for(request))

    def record_feedback(self, model_id: str, *, success: bool, latency_ms: float, quality: float = 1.0) -> None:
        self.feedback.record(model_id, success=success, latency_ms=latency_ms, quality=quality)

    def _to_config(self, model: ModelDefinition) -> ModelConfig:
        provider = self.registry.provider_for(model)
        base_url = os.getenv(provider.base_url_env, provider.base_url) if provider.base_url_env else provider.base_url
        base_url = os.path.expandvars(base_url)
        return ModelConfig(
            id=model.id,
            provider=model.provider,
            model_name=model.upstream_model,
            max_context_length=model.context_window,
            strengths=sorted(model.tags),
            api_key_env=provider.api_key_env,
            api_key_envs=list(provider.api_key_envs),
            adapter=provider.adapter,
            base_url=base_url,
            region=provider.region,
            region_env=provider.region_env,
            auth=provider.resolved_auth,
            billing_class=model.billing_class,
            approval_status=model.approval_status,
            quality_score=model.quality_score,
            latency_score=model.latency_score,
            capabilities=sorted(model.capabilities),
            input_cost_per_million=model.input_cost_per_million,
            output_cost_per_million=model.output_cost_per_million,
            user_selectable=model.user_selectable,
            lease_id=model.lease_id,
            traffic_percent=model.traffic_percent,
            daily_spend_cap_usd=model.daily_spend_cap_usd,
            pricing_source=model.pricing_source,
            pending_reconciliation=model.pending_reconciliation,
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

    def _canary_config(self, request: Any) -> Optional[ModelConfig]:
        """Choose at most one bounded auto-canary model for this request.

        The bucket is stable for a user/task/model tuple. That keeps a canary
        cohort stable across retries while ensuring a new model cannot receive
        traffic merely because it was discovered first.
        """
        grant = getattr(request.user_context, "execution_grant", None)
        allowed = {str(item) for item in getattr(grant, "allowed_model_ids", ()) or ()}
        identity = str(getattr(request.user_context, "user_id", ""))
        selected: List[tuple[float, float, str, ModelConfig]] = []
        for model in self.registry.auto_canary_models(request.task_type.value):
            config = self.model_configs.get(model.id)
            if config is None or (allowed and model.id not in allowed):
                continue
            bucket = int(
                hashlib.sha256(
                    f"{identity}:{request.task_type.value}:{model.id}".encode()
                ).hexdigest()[:8],
                16,
            ) % 10_000 / 100
            if bucket < max(0.0, min(100.0, float(model.traffic_percent or 0))):
                selected.append((bucket, -model.priority, model.id, config))
        if not selected:
            return None
        selected.sort()
        return selected[0][3]

    def _is_configured(self, config: ModelConfig) -> bool:
        model = self.registry.models[config.id]
        return self.registry.is_provider_configured(model)

    def _grant_permits(self, grant: Any, config: ModelConfig) -> bool:
        """Grant-level billing-class and data-handling authorization.

        This is what makes a free-tier grant unable to silently escalate: a
        candidate the grant does not permit is removed from the chain entirely,
        so the fallback loop can never cross from a free model into a paid one.
        """
        if not grant.permits_billing_class(config.billing_class):
            return False
        model = self.registry.models[config.id]
        return grant.permits_data_handling(model.data_handling)

    @staticmethod
    def _economy_score(config: ModelConfig) -> float:
        if config.input_cost_per_million is None or config.output_cost_per_million is None:
            return 40.0
        combined = config.input_cost_per_million + config.output_cost_per_million
        return max(0.0, min(100.0, 100.0 - combined * 2.5))

    def _rank(self, candidates: List[ModelConfig], policy: TaskPolicy, profile: str, assessment: Optional[ComplexityAssessment] = None) -> List[ModelConfig]:
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
        if objective in {"economy", "profitability"}:
            candidates = [
                config for config in candidates
                if config.input_cost_per_million is not None
                and config.output_cost_per_million is not None
            ]
            if not candidates:
                raise RegistryError("no cost-complete model is available for cost-based routing")

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
            if assessment:
                # Harder requests bias toward quality, while still retaining
                # task quality floors and infrastructure-efficiency scoring.
                value += assessment.score * (quality - 70.0) * 0.12
            value += self.feedback.adjustment(config.id)
            # A task's preferred list is a deterministic tie-breaker. The
            # caller's explicit quality/economy/latency profile remains the
            # primary objective so profitability routing is observable.
            if config.id in preferred_index:
                value += max(0.0, 0.05 - preferred_index[config.id] * 0.01)
            return value, -self.registry.models[config.id].priority

        return sorted(candidates, key=score, reverse=True)

    def select_chain(self, request: Any) -> List[ModelConfig]:
        policy = self.policy_for(request)
        assessment = self.classify_request(request)
        canary_config = self._canary_config(request)
        candidates = self._rank(
            self._candidate_configs(request),
            policy,
            getattr(request, "execution_profile", "balanced"),
            assessment,
        )
        grant = getattr(request.user_context, "execution_grant", None)
        if grant is not None and candidates:
            permitted = [item for item in candidates if self._grant_permits(grant, item)]
            if not permitted:
                raise ExecutionAuthorizationError(
                    "no model is permitted by the execution grant billing/data policy for "
                    f"{request.task_type.value}"
                )
            candidates = permitted
        disabled = set(self.runtime_controls.get("disabled_models") or [])
        candidates = [item for item in candidates if item.id not in disabled]
        if canary_config is not None:
            if (
                (grant is None or self._grant_permits(grant, canary_config))
                and canary_config.id not in disabled
            ):
                candidates = [canary_config] + [
                    item for item in candidates if item.id != canary_config.id
                ]
        canary = (self.runtime_controls.get("canaries") or {}).get(request.task_type.value) or {}
        canary_id = canary.get("model_id")
        canary_pct = max(0.0, min(100.0, float(canary.get("percentage") or 0)))
        if canary_id and canary_pct and any(item.id == canary_id for item in candidates):
            identity = f"{getattr(request.user_context, 'user_id', '')}:{request.task_type.value}"
            bucket = int(hashlib.sha256(identity.encode()).hexdigest()[:8], 16) % 10_000 / 100
            if bucket < canary_pct:
                candidates.sort(key=lambda item: item.id != canary_id)
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
        # Prefer providers that actually have credentials so the router never
        # attempts a model that can only fail with a missing-key error. When no
        # provider is configured (e.g. local dev) fall back to the full ranked
        # chain so behaviour and error messages stay unchanged.
        if configured and _exclude_unconfigured():
            chain = configured
        else:
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
