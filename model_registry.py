"""Configuration-driven provider, model, and task policy registry.

The registry contains operational execution metadata only. Customer plans,
credits, subscriptions, payments, and paywalls deliberately do not belong here.
Provider prices are optional FinOps inputs used to optimize infrastructure spend;
they are never interpreted as customer prices.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Set


ROOT = Path(__file__).resolve().parent
DEFAULT_MODEL_REGISTRY = ROOT / "config" / "model_registry.json"
DEFAULT_TASK_POLICIES = ROOT / "config" / "task_policies.json"


class RegistryError(RuntimeError):
    """Configuration cannot produce a safe execution route."""


# --- schema v2 vocabularies -------------------------------------------------
# Explicit, closed vocabularies. Provider identity, authentication, billing
# class, and approval are always *declared* here - never inferred from an API
# key prefix, a model name, or a provider name.
BILLING_CLASSES = {"free", "paid", "metered"}
APPROVAL_STATUSES = {"discovered", "approved", "disabled"}
AUTH_MODES = {"bearer", "anthropic", "query", "sigv4", "bedrock_bearer", "azure", "none"}
CAPABILITY_FLAGS = ("streaming", "tool_calling", "structured_output", "vision")

# Adapter -> default auth mode. Only used when a provider does not declare
# `auth` explicitly, so existing registry files keep working unchanged.
DEFAULT_AUTH_BY_ADAPTER = {
    "openai_responses": "bearer",
    "openai_compatible": "bearer",
    "anthropic_messages": "anthropic",
    "gemini_generate": "query",
    "cohere_embed": "bearer",
    "bedrock_converse": "sigv4",
    "bedrock_bearer": "bedrock_bearer",
}

SUPPORTED_ADAPTERS = frozenset(DEFAULT_AUTH_BY_ADAPTER)


@dataclass(frozen=True)
class ProviderDefinition:
    id: str
    adapter: str
    api_key_env: str
    api_key_envs: Sequence[str] = field(default_factory=tuple)
    base_url: str = ""
    base_url_env: str = ""
    enabled_env: str = ""
    enabled: bool = True
    region: str = "global"
    region_env: str = ""
    auth: str = ""
    headers: Dict[str, str] = field(default_factory=dict)

    @property
    def resolved_auth(self) -> str:
        """Declared auth mode, or the adapter's documented default."""
        return self.auth or DEFAULT_AUTH_BY_ADAPTER.get(self.adapter, "bearer")

    @property
    def requires_api_key(self) -> bool:
        """AWS credential-chain providers carry no static API key."""
        return self.resolved_auth != "sigv4"


@dataclass(frozen=True)
class ModelDefinition:
    id: str
    provider: str
    upstream_model: str
    enabled: bool
    user_selectable: bool
    quality_tier: str
    quality_score: float
    latency_score: float
    context_window: int
    max_output_tokens: int
    capabilities: Set[str]
    input_cost_per_million: Optional[float] = None
    cached_input_cost_per_million: Optional[float] = None
    output_cost_per_million: Optional[float] = None
    priority: int = 100
    tags: Set[str] = field(default_factory=set)
    # --- schema v2 metadata (all optional; safe defaults for v1 documents) ---
    billing_class: str = "paid"
    approval_status: str = "approved"
    supported_regions: Sequence[str] = field(default_factory=tuple)
    data_handling: str = ""
    health_status: str = "unknown"
    pricing_version: str = ""
    streaming: bool = False
    tool_calling: bool = False
    structured_output: bool = False
    vision: bool = False

    def estimated_provider_cost(self, input_tokens: int, output_tokens: int) -> Optional[float]:
        if self.input_cost_per_million is None or self.output_cost_per_million is None:
            return None
        return (
            (max(0, input_tokens) / 1_000_000) * self.input_cost_per_million
            + (max(0, output_tokens) / 1_000_000) * self.output_cost_per_million
        )

    @property
    def is_free(self) -> bool:
        return self.billing_class == "free"

    @property
    def billable(self) -> bool:
        """Anything that is not classed `free` must be explicitly authorized."""
        return self.billing_class != "free"

    @property
    def approved(self) -> bool:
        return self.approval_status == "approved"

    def capability_flags(self) -> Dict[str, bool]:
        return {flag: bool(getattr(self, flag)) for flag in CAPABILITY_FLAGS}

    def supports_region(self, region: str) -> bool:
        if not self.supported_regions:
            return True
        candidate = (region or "").strip().lower()
        return candidate in {str(item).lower() for item in self.supported_regions}


@dataclass(frozen=True)
class TaskPolicy:
    task_type: str
    complexity: str
    required_capabilities: Set[str]
    minimum_quality_score: float
    routing_objective: str
    max_input_tokens: int
    max_output_tokens: int
    timeout_seconds: float
    max_provider_cost_usd: Optional[float]
    max_attempts: int
    same_provider_retries: int
    cache_ttl_seconds: int
    structured_output: bool
    output_schema: Optional[Dict[str, Any]] = None
    preferred_models: Sequence[str] = field(default_factory=tuple)
    forbidden_models: Set[str] = field(default_factory=set)
    # --- schema v2 policy dimensions (optional) ---
    allowed_billing_classes: Set[str] = field(default_factory=set)
    required_data_handling: str = ""
    max_latency_ms: Optional[float] = None


class ModelRegistry:
    """Loads versioned JSON configuration and exposes capability-safe routes."""

    def __init__(
        self,
        model_registry_path: Optional[str] = None,
        task_policy_path: Optional[str] = None,
    ) -> None:
        self.model_registry_path = Path(
            model_registry_path
            or os.getenv("MODEL_REGISTRY_PATH", str(DEFAULT_MODEL_REGISTRY))
        )
        self.task_policy_path = Path(
            task_policy_path
            or os.getenv("TASK_POLICY_PATH", str(DEFAULT_TASK_POLICIES))
        )
        self.version = ""
        self.task_policy_version = ""
        self.registry_updated_at = ""
        self.task_policy_updated_at = ""
        self.owner = ""
        self.providers: Dict[str, ProviderDefinition] = {}
        self.models: Dict[str, ModelDefinition] = {}
        self.task_policies: Dict[str, TaskPolicy] = {}
        self._load()

    @staticmethod
    def _read_json(path: Path) -> Dict[str, Any]:
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise RegistryError(f"registry file not found: {path}") from exc
        except json.JSONDecodeError as exc:
            raise RegistryError(f"invalid registry JSON {path}: {exc}") from exc
        if not isinstance(payload, dict):
            raise RegistryError(f"registry root must be an object: {path}")
        return payload

    def _load(self) -> None:
        registry = self._read_json(self.model_registry_path)
        policies = self._read_json(self.task_policy_path)
        self._validate_document_metadata(registry, "model registry")
        self._validate_document_metadata(policies, "task policy registry")
        self.version = str(registry.get("version") or "unversioned")
        self.task_policy_version = str(policies.get("version") or "unversioned")
        self.registry_updated_at = str(registry["updated_at"])
        self.task_policy_updated_at = str(policies["updated_at"])
        self.owner = str(registry["owner"])

        for raw in registry.get("providers", []):
            missing_provider = [field for field in ("id", "adapter", "api_key_env") if field not in raw]
            if missing_provider:
                raise RegistryError(f"provider metadata is incomplete: {', '.join(missing_provider)}")
            provider = ProviderDefinition(
                id=str(raw["id"]),
                adapter=str(raw["adapter"]),
                api_key_env=str(raw.get("api_key_env") or ""),
                api_key_envs=tuple(str(item) for item in (raw.get("api_key_envs") or [raw.get("api_key_env") or ""])),
                base_url=str(raw.get("base_url") or ""),
                base_url_env=str(raw.get("base_url_env") or ""),
                enabled_env=str(raw.get("enabled_env") or ""),
                enabled=bool(raw.get("enabled", True)),
                region=str(raw.get("region") or "global"),
                region_env=str(raw.get("region_env") or ""),
                auth=str(raw.get("auth") or "").strip().lower(),
                headers={str(k): str(v) for k, v in (raw.get("headers") or {}).items()},
            )
            if provider.auth and provider.auth not in AUTH_MODES:
                raise RegistryError(
                    f"provider {provider.id} declares unsupported auth mode: {provider.auth}"
                )
            if provider.adapter not in SUPPORTED_ADAPTERS:
                raise RegistryError(
                    f"provider {provider.id} declares unsupported adapter: {provider.adapter}"
                )
            if provider.id in self.providers:
                raise RegistryError(f"duplicate provider id: {provider.id}")
            self.providers[provider.id] = provider

        for raw in registry.get("models", []):
            required_model_fields = (
                "id", "provider", "upstream_model", "enabled", "user_selectable",
                "quality_tier", "quality_score", "latency_score", "context_window",
                "max_output_tokens", "capabilities",
            )
            missing_model = [field for field in required_model_fields if field not in raw]
            if missing_model:
                raise RegistryError(f"model metadata is incomplete: {', '.join(missing_model)}")
            capabilities = {str(item) for item in raw.get("capabilities", ["text"])}
            approval_status = str(raw.get("approval_status") or "").strip().lower()
            if not approval_status:
                approval_status = "disabled" if raw.get("enabled") is False else "approved"
            if approval_status not in APPROVAL_STATUSES:
                raise RegistryError(f"model {raw.get('id')} declares unknown approval_status: {approval_status}")
            # `enabled` is the effective gate and is derived from approval status
            # so the two can never diverge. Discovered/disabled models are inert.
            enabled = approval_status == "approved" and bool(raw.get("enabled", True))
            model = ModelDefinition(
                id=str(raw["id"]),
                provider=str(raw["provider"]),
                upstream_model=str(raw["upstream_model"]),
                enabled=enabled,
                user_selectable=bool(raw.get("user_selectable", False)) and enabled,
                quality_tier=str(raw.get("quality_tier") or "standard"),
                quality_score=float(raw.get("quality_score", 50)),
                latency_score=float(raw.get("latency_score", 50)),
                context_window=int(raw.get("context_window", 128_000)),
                max_output_tokens=int(raw.get("max_output_tokens", 8_192)),
                capabilities=capabilities,
                input_cost_per_million=self._optional_float(raw.get("input_cost_per_million")),
                cached_input_cost_per_million=self._optional_float(raw.get("cached_input_cost_per_million")),
                output_cost_per_million=self._optional_float(raw.get("output_cost_per_million")),
                priority=int(raw.get("priority", 100)),
                tags={str(item) for item in raw.get("tags", [])},
                billing_class=self._billing_class(raw),
                approval_status=approval_status,
                supported_regions=tuple(
                    str(item).strip().lower() for item in (raw.get("supported_regions") or []) if str(item).strip()
                ),
                data_handling=str(raw.get("data_handling") or ""),
                health_status=str(raw.get("health_status") or "unknown"),
                pricing_version=str(raw.get("pricing_version") or self.version),
                **self._flag_declarations(raw, capabilities),
            )
            if model.provider not in self.providers:
                raise RegistryError(f"model {model.id} references unknown provider {model.provider}")
            if model.id in self.models:
                raise RegistryError(f"duplicate model id: {model.id}")
            if not 0 <= model.quality_score <= 100 or not 0 <= model.latency_score <= 100:
                raise RegistryError(f"model quality/latency score is invalid: {model.id}")
            if model.context_window <= 0 or model.max_output_tokens <= 0 or not model.capabilities:
                raise RegistryError(f"model execution metadata is invalid: {model.id}")
            self.models[model.id] = model

        defaults = policies.get("defaults") or {}
        for task_type, raw_policy in (policies.get("tasks") or {}).items():
            merged = {**defaults, **(raw_policy or {})}
            self.task_policies[str(task_type)] = TaskPolicy(
                task_type=str(task_type),
                complexity=str(merged.get("complexity") or "short_generation"),
                required_capabilities={str(item) for item in merged.get("required_capabilities", ["text"])},
                minimum_quality_score=float(merged.get("minimum_quality_score", 0)),
                routing_objective=str(merged.get("routing_objective") or "balanced"),
                max_input_tokens=int(merged.get("max_input_tokens", 64_000)),
                max_output_tokens=int(merged.get("max_output_tokens", 4_000)),
                timeout_seconds=float(merged.get("timeout_seconds", 30)),
                max_provider_cost_usd=self._optional_float(merged.get("max_provider_cost_usd")),
                max_attempts=max(1, int(merged.get("max_attempts", 3))),
                same_provider_retries=max(0, int(merged.get("same_provider_retries", 1))),
                cache_ttl_seconds=max(0, int(merged.get("cache_ttl_seconds", 0))),
                structured_output=bool(merged.get("structured_output", False)),
                output_schema=merged.get("output_schema"),
                preferred_models=tuple(str(item) for item in merged.get("preferred_models", [])),
                forbidden_models={str(item) for item in merged.get("forbidden_models", [])},
                allowed_billing_classes={
                    str(item).strip().lower() for item in merged.get("allowed_billing_classes", []) if str(item).strip()
                },
                required_data_handling=str(merged.get("required_data_handling") or ""),
                max_latency_ms=self._optional_float(merged.get("max_latency_ms")),
            )

        if not self.providers or not self.models or not self.task_policies:
            raise RegistryError("provider, model, and task policy registries must not be empty")

    @staticmethod
    def _validate_document_metadata(document: Mapping[str, Any], name: str) -> None:
        if document.get("schema_version") != 1:
            raise RegistryError(f"{name} schema_version must be 1")
        for field in ("version", "updated_at", "owner"):
            if not isinstance(document.get(field), str) or not document[field].strip():
                raise RegistryError(f"{name} requires non-empty {field}")
        try:
            updated_at = datetime.fromisoformat(document["updated_at"].replace("Z", "+00:00"))
        except (TypeError, ValueError) as exc:
            raise RegistryError(f"{name} updated_at must be an ISO timestamp") from exc
        environment = os.getenv("ENVIRONMENT", "development").strip().lower()
        if environment not in {"production", "staging"}:
            return
        now = datetime.now(timezone.utc)
        if updated_at > now:
            raise RegistryError(f"{name} updated_at cannot be in the future")
        try:
            max_age_days = float(os.getenv("MODEL_REGISTRY_MAX_AGE_DAYS", "30"))
        except ValueError as exc:
            raise RegistryError("MODEL_REGISTRY_MAX_AGE_DAYS must be numeric") from exc
        if max_age_days < 0 or (now - updated_at).total_seconds() > max_age_days * 86400:
            raise RegistryError(f"{name} is stale for production routing")

    def routing_metadata(self) -> Dict[str, str]:
        return {
            "registry_version": self.version,
            "registry_updated_at": self.registry_updated_at,
            "task_policy_version": self.task_policy_version,
            "task_policy_updated_at": self.task_policy_updated_at,
            "owner": self.owner,
        }

    @staticmethod
    def _optional_float(value: Any) -> Optional[float]:
        if value is None or value == "":
            return None
        return float(value)

    @staticmethod
    def _billing_class(raw: Mapping[str, Any]) -> str:
        """Billing class is declared, or derived from pricing - never inferred
        from the provider name. Unknown pricing is treated as `paid`, so an
        unpriced model can never be treated as free by accident."""
        declared = str(raw.get("billing_class") or "").strip().lower()
        if declared:
            if declared not in BILLING_CLASSES:
                raise RegistryError(f"model {raw.get('id')} declares unknown billing_class: {declared}")
            if declared == "free":
                costs = (raw.get("input_cost_per_million"), raw.get("output_cost_per_million"))
                if any(cost is not None and float(cost) > 0 for cost in costs):
                    raise RegistryError(
                        f"model {raw.get('id')} is classed free but declares a non-zero price"
                    )
            return declared
        costs = (raw.get("input_cost_per_million"), raw.get("output_cost_per_million"))
        if costs[0] is not None and costs[1] is not None and float(costs[0]) == 0.0 and float(costs[1]) == 0.0:
            return "free"
        return "paid"

    @staticmethod
    def _flag_declarations(raw: Mapping[str, Any], capabilities: Set[str]) -> Dict[str, bool]:
        """Reconcile the explicit capability booleans with the capability set.

        A declared `true` flag must be backed by the capability; an omitted flag
        is derived from the capability set so this is backward compatible."""
        declarations: Dict[str, bool] = {}
        for flag in CAPABILITY_FLAGS:
            declared = raw.get(flag)
            present = flag in capabilities
            if declared is None:
                declarations[flag] = present
                continue
            value = bool(declared)
            if value and not present:
                raise RegistryError(
                    f"model {raw.get('id')} declares {flag}=true but omits the capability"
                )
            declarations[flag] = value
        return declarations

    def provider_for(self, model: ModelDefinition) -> ProviderDefinition:
        return self.providers[model.provider]

    def task_policy(self, task_type: str) -> TaskPolicy:
        policy = self.task_policies.get(task_type)
        if policy is None:
            raise RegistryError(f"no task policy configured for {task_type}")
        return policy

    def is_provider_configured(
        self,
        model: ModelDefinition,
        env: Optional[Mapping[str, str]] = None,
    ) -> bool:
        values = env or os.environ
        provider = self.provider_for(model)
        explicitly_enabled = True
        if provider.enabled_env:
            explicitly_enabled = str(values.get(provider.enabled_env, "")).strip().lower() in {
                "1", "true", "yes", "on",
            }
        return (
            provider.enabled
            and explicitly_enabled
            and (not provider.api_key_env or any(values.get(item) for item in provider.api_key_envs))
        )

    def selectable_models(self, task_type: Optional[str] = None) -> List[ModelDefinition]:
        policy = self.task_policy(task_type) if task_type else None
        return [
            model
            for model in self.models.values()
            if model.enabled
            and model.user_selectable
            and (policy is None or self._meets_policy(model, policy))
        ]

    def eligible_models(
        self,
        task_type: str,
        *,
        requested_model: Optional[str] = None,
        allowed_models: Optional[Iterable[str]] = None,
    ) -> List[ModelDefinition]:
        policy = self.task_policy(task_type)
        allowed = {str(item) for item in allowed_models or []}

        if requested_model:
            model = self.models.get(requested_model)
            if model is None or not model.enabled:
                raise RegistryError(f"requested model is unavailable: {requested_model}")
            if not model.user_selectable:
                raise RegistryError(f"requested model is not user-selectable: {requested_model}")
            if allowed and requested_model not in allowed:
                raise RegistryError(f"requested model is not allowed by the execution grant: {requested_model}")
            if not self._meets_policy(model, policy):
                raise RegistryError(f"requested model does not satisfy task policy: {requested_model}")
            return [model]

        candidates = [
            model
            for model in self.models.values()
            if model.enabled
            and (not allowed or model.id in allowed)
            and self._meets_policy(model, policy)
        ]
        preferred_index = {model_id: index for index, model_id in enumerate(policy.preferred_models)}
        candidates.sort(key=lambda model: (
            preferred_index.get(model.id, len(preferred_index) + model.priority),
            model.priority,
        ))
        return candidates

    @staticmethod
    def _meets_policy(model: ModelDefinition, policy: TaskPolicy) -> bool:
        if (
            model.id in policy.forbidden_models
            or not model.approved
            or model.quality_score < policy.minimum_quality_score
            or not policy.required_capabilities.issubset(model.capabilities)
            or model.context_window < policy.max_input_tokens
            or model.max_output_tokens < policy.max_output_tokens
        ):
            return False
        # Billing-class and data-handling policy dimensions are optional. When a
        # task declares them, a model that does not match is never a candidate -
        # this is what keeps a free-tier or data-region task from silently
        # routing to a paid or non-compliant model.
        if policy.allowed_billing_classes and model.billing_class not in policy.allowed_billing_classes:
            return False
        if policy.required_data_handling and model.data_handling != policy.required_data_handling:
            return False
        return True
