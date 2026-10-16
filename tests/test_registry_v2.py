"""Registry v2 metadata, validation, and approval/billing semantics."""

from __future__ import annotations

import json

import pytest

from model_registry import ModelRegistry, RegistryError


def _write(tmp_path, models, policies=None, providers=None):
    registry = {
        "schema_version": 1, "version": "t-1", "updated_at": "2026-01-01T00:00:00Z", "owner": "test",
        "providers": providers or [
            {"id": "p", "adapter": "openai_compatible", "api_key_env": "P_KEY", "base_url": "https://p.example/v1"},
        ],
        "models": models,
    }
    policy_doc = {
        "schema_version": 1, "version": "p-1", "updated_at": "2026-01-01T00:00:00Z", "owner": "test",
        "defaults": {
            "complexity": "short_generation", "required_capabilities": ["text"],
            "minimum_quality_score": 0, "routing_objective": "balanced",
            "max_input_tokens": 1000, "max_output_tokens": 100, "timeout_seconds": 30,
            "max_attempts": 2, "same_provider_retries": 0, "cache_ttl_seconds": 0,
            "structured_output": False,
        },
        "tasks": {"any_task": {}, **(policies or {})},
    }
    registry_path = tmp_path / "registry.json"
    policy_path = tmp_path / "policies.json"
    registry_path.write_text(json.dumps(registry))
    policy_path.write_text(json.dumps(policy_doc))
    return ModelRegistry(str(registry_path), str(policy_path))


def _model(model_id: str, **overrides) -> dict:
    base = {
        "id": model_id, "provider": "p", "upstream_model": model_id,
        "enabled": True, "user_selectable": True, "quality_tier": "standard",
        "quality_score": 80, "latency_score": 60, "context_window": 128000,
        "max_output_tokens": 4096, "capabilities": ["text"],
    }
    base.update(overrides)
    return base


def test_billing_class_derives_free_only_from_zero_pricing(tmp_path):
    registry = _write(tmp_path, [
        _model("free", input_cost_per_million=0.0, output_cost_per_million=0.0),
        _model("paid", input_cost_per_million=1.0, output_cost_per_million=2.0),
        _model("unpriced"),
    ])
    assert registry.models["free"].billing_class == "free"
    assert registry.models["free"].is_free is True
    assert registry.models["paid"].billing_class == "paid"
    # Unknown pricing must never be treated as free.
    assert registry.models["unpriced"].billing_class == "paid"


def test_free_model_with_a_price_is_rejected(tmp_path):
    with pytest.raises(RegistryError, match="classed free but declares a non-zero price"):
        _write(tmp_path, [_model("bad", billing_class="free", input_cost_per_million=1.0)])


def test_unknown_billing_class_and_auth_are_rejected(tmp_path):
    with pytest.raises(RegistryError, match="unknown billing_class"):
        _write(tmp_path, [_model("bad", billing_class="cheap")])
    with pytest.raises(RegistryError, match="unsupported auth mode"):
        _write(tmp_path, [_model("m")], providers=[
            {"id": "p", "adapter": "openai_compatible", "api_key_env": "P_KEY", "auth": "magic"},
        ])
    with pytest.raises(RegistryError, match="unsupported adapter"):
        _write(tmp_path, [_model("m")], providers=[
            {"id": "p", "adapter": "made_up", "api_key_env": "P_KEY"},
        ])


def test_discovered_and_disabled_models_are_inert(tmp_path):
    registry = _write(tmp_path, [
        _model("approved"),
        _model("discovered", approval_status="discovered"),
        _model("disabled", approval_status="disabled"),
    ])
    assert registry.models["discovered"].enabled is False
    assert registry.models["discovered"].approved is False
    assert registry.models["disabled"].enabled is False
    ids = [m.id for m in registry.eligible_models("any_task")]  # task policy added below
    assert "discovered" not in ids


def test_capability_flags_must_be_backed_by_the_capability_set(tmp_path):
    with pytest.raises(RegistryError, match="declares streaming=true but omits the capability"):
        _write(tmp_path, [_model("m", streaming=True)])
    registry = _write(tmp_path, [_model("m", capabilities=["text", "streaming"])])
    assert registry.models["m"].streaming is True


def test_policy_billing_class_and_data_handling_filter_candidates(tmp_path):
    registry = _write(
        tmp_path,
        [
            _model("free", input_cost_per_million=0.0, output_cost_per_million=0.0, data_handling="no_training"),
            _model("paid", input_cost_per_million=1.0, output_cost_per_million=2.0, data_handling="retention_bounded"),
        ],
        policies={"t": {"allowed_billing_classes": ["free"], "required_data_handling": "no_training"}},
    )
    ids = [m.id for m in registry.eligible_models("t")]
    assert ids == ["free"]


def test_supported_regions_is_declared_not_inferred(tmp_path):
    registry = _write(tmp_path, [_model("m", supported_regions=["us-east-1", "eu-central-1"])])
    model = registry.models["m"]
    assert model.supports_region("us-east-1") is True
    assert model.supports_region("ap-south-1") is False


def test_provider_resolved_auth_defaults_from_adapter(tmp_path):
    registry = _write(tmp_path, [_model("m")], providers=[
        {"id": "p", "adapter": "anthropic_messages", "api_key_env": "P_KEY"},
        {"id": "b", "adapter": "bedrock_converse", "api_key_env": ""},
    ])
    assert registry.providers["p"].resolved_auth == "anthropic"
    assert registry.providers["b"].resolved_auth == "sigv4"
    assert registry.providers["b"].requires_api_key is False
