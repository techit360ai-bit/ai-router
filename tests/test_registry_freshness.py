"""Provider routing registry integrity and freshness contracts."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ai_router_core import AIRequest, TaskType, UserContext, UserRole  # noqa: E402
from model_registry import ModelRegistry, RegistryError  # noqa: E402
from routing_engine import ModelRouter  # noqa: E402


ROOT = Path(__file__).resolve().parents[1]


def _copy_registry_files(tmp_path: Path) -> tuple[Path, Path]:
    model_path = tmp_path / "models.json"
    policy_path = tmp_path / "tasks.json"
    model_path.write_text((ROOT / "config" / "model_registry.json").read_text(encoding="utf-8"), encoding="utf-8")
    policy_path.write_text((ROOT / "config" / "task_policies.json").read_text(encoding="utf-8"), encoding="utf-8")
    return model_path, policy_path


def _request() -> AIRequest:
    context = UserContext(
        user_id="u_test", role=UserRole.FOUNDER, project_id="p_test",
        project_stage="mvp", industry="saas", tech_stack=[], past_feedback=[],
        training_progress={}, time_logged_today=0, tasks_completed_week=0,
    )
    return AIRequest(task_type=TaskType.CHAT, user_context=context, input_data={}, execution_profile="profitability")


def test_registry_exposes_versioned_routing_metadata() -> None:
    metadata = ModelRegistry().routing_metadata()

    assert metadata["registry_version"] == "2026-08-10.1"
    assert metadata["task_policy_version"] == "2026-08-10.1"
    assert metadata["registry_updated_at"]
    assert metadata["owner"] == "platform-routing"


def test_production_rejects_stale_registry(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    model_path, policy_path = _copy_registry_files(tmp_path)
    registry = json.loads(model_path.read_text(encoding="utf-8"))
    registry["updated_at"] = "2020-01-01T00:00:00Z"
    model_path.write_text(json.dumps(registry), encoding="utf-8")
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("MODEL_REGISTRY_MAX_AGE_DAYS", "1")

    with pytest.raises(RegistryError, match="stale"):
        ModelRegistry(str(model_path), str(policy_path))


def test_invalid_registry_schema_fails_closed(tmp_path: Path) -> None:
    model_path, policy_path = _copy_registry_files(tmp_path)
    registry = json.loads(model_path.read_text(encoding="utf-8"))
    registry["schema_version"] = 2
    model_path.write_text(json.dumps(registry), encoding="utf-8")

    with pytest.raises(RegistryError, match="schema_version"):
        ModelRegistry(str(model_path), str(policy_path))


def test_incomplete_model_metadata_fails_closed(tmp_path: Path) -> None:
    model_path, policy_path = _copy_registry_files(tmp_path)
    registry = json.loads(model_path.read_text(encoding="utf-8"))
    registry["models"][0].pop("context_window")
    model_path.write_text(json.dumps(registry), encoding="utf-8")

    with pytest.raises(RegistryError, match="incomplete"):
        ModelRegistry(str(model_path), str(policy_path))


def test_cost_based_routing_excludes_models_without_cost_metadata() -> None:
    router = ModelRouter()
    chain = router.select_chain(_request())

    assert chain
    assert all(model.input_cost_per_million is not None for model in chain)
    assert all(model.output_cost_per_million is not None for model in chain)
