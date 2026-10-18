"""Catalog activation, bounded canary leases, and admin mutation contracts."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from ai_router_core import AIRequest, ModelRouter, TaskType, UserContext, UserRole
from provider_catalog import (
    apply_registry_overlay,
    lease_budget,
    provider_status,
    refresh_provider_catalog,
    runtime_path,
    set_auto_provision,
    update_model_lease,
)


def _now(days_ago: float = 0) -> str:
    return (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()


def _lease(model_id: str, *, status: str = "active", **overrides):
    row = {
        "lease_id": model_id,
        "model_id": model_id,
        "provider_id": "openrouter",
        "upstream_model": model_id.rsplit(":", 1)[-1],
        "enabled": True,
        "user_selectable": status == "approved",
        "quality_tier": "standard",
        "quality_score": 90,
        "latency_score": 80,
        "context_window": 128_000,
        "max_output_tokens": 4096,
        "capabilities": ["text"],
        "input_cost_per_million": 1.0,
        "output_cost_per_million": 2.0,
        "billing_class": "paid",
        "approval_status": "auto_canary" if status != "approved" else "approved",
        "pricing_source": "provider_feed",
        "pricing_version": "test",
        "pending_reconciliation": False,
        "traffic_percent": 0.0 if status == "approved" else 100.0,
        "daily_spend_cap_usd": 5.0,
        "spend_today_usd": 0.0,
        "spend_date": datetime.now(timezone.utc).date().isoformat(),
        "calls": 0,
        "errors": 0,
        "discovered_at": _now(3),
        "updated_at": _now(),
        "status": status,
        "version": 1,
        "promotion_eligible": False,
        "last_action": "discovered",
        "last_action_reason": "test",
    }
    row.update(overrides)
    return row


def _seed_runtime(*leases, policy=None):
    path = runtime_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    state = {
        "schema_version": 1,
        "updated_at": _now(),
        "policy": {"auto_provision_enabled": True, "version": 1, "settings": {}, **(policy or {})},
        "providers": {},
        "model_leases": {lease["model_id"]: lease for lease in leases},
    }
    path.write_text(json.dumps(state), encoding="utf-8")
    return state


@pytest.fixture(autouse=True)
def _isolated_runtime(tmp_path, monkeypatch):
    monkeypatch.setenv("AI_PROVIDER_RUNTIME_PATH", str(tmp_path / "provider_runtime.json"))
    monkeypatch.setenv("AI_PROVIDER_AUTO_CONFIG", "true")
    monkeypatch.setenv("AI_AUTO_PROVIDER_DISCOVERY", "true")


def test_provider_status_distinguishes_missing_and_partial_configuration() -> None:
    env = {"AZURE_OPENAI_API_KEY": "super-secret-value", "AZURE_OPENAI_API_VERSION": "2024-10-21"}
    payload = provider_status(env=env)
    by_id = {row["id"]: row for row in payload["providers"]}

    assert by_id["openai"]["status"] == "not_detected"
    assert by_id["openai"]["detected"] is False
    assert by_id["azure_openai"]["status"] == "misconfigured"
    assert by_id["azure_openai"]["detected"] is True
    assert by_id["azure_openai"]["missing_env"] == [
        "AZURE_OPENAI_BASE_URL",
        "AZURE_OPENAI_DEPLOYMENTS",
    ]
    serialized = json.dumps(payload)
    assert "super-secret-value" not in serialized
    assert "present_env" in by_id["azure_openai"]


def test_complete_provider_signature_is_ready_without_echoing_values() -> None:
    env = {
        "AZURE_OPENAI_API_KEY": "super-secret-value",
        "AZURE_OPENAI_BASE_URL": "https://example.openai.azure.com",
        "AZURE_OPENAI_DEPLOYMENTS": "gpt-4.1",
        "AZURE_OPENAI_API_VERSION": "2024-10-21",
    }
    payload = provider_status(
        credential_reports={"azure_openai": {"ok": True, "detail": "authorized"}},
        env=env,
    )
    azure = next(row for row in payload["providers"] if row["id"] == "azure_openai")
    assert azure["status"] == "ready"
    assert azure["configured"] is True
    assert azure["missing_env"] == []
    assert "super-secret-value" not in json.dumps(payload)


def test_overlay_adds_discovered_model_as_non_selectable_auto_canary(monkeypatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "test")
    lease = _lease("auto:openrouter:vendor/canary")
    _seed_runtime(lease)

    document = apply_registry_overlay(
        {"version": "test", "providers": [], "models": []},
        env={"OPENROUTER_API_KEY": "test"},
    )
    model = next(row for row in document["models"] if row["id"] == lease["model_id"])
    assert model["approval_status"] == "auto_canary"
    assert model["user_selectable"] is False
    assert model["lease_id"] == lease["model_id"]
    assert model["traffic_percent"] == 100.0

    router = ModelRouter()
    chain = router.select_chain(_request(TaskType.CHAT))
    assert chain[0].id == lease["model_id"]
    assert chain[0].lease_id == lease["model_id"]


def test_kill_switch_stops_canary_traffic_and_preserves_promoted_pool(monkeypatch) -> None:
    monkeypatch.setenv("OPENROUTER_API_KEY", "test")
    active = _lease("auto:openrouter:vendor/canary")
    promoted = _lease(
        "auto:openrouter:vendor/promoted",
        status="approved",
        upstream_model="vendor/promoted",
    )
    _seed_runtime(active, promoted)
    result = set_auto_provision(False, actor="test", reason="operator pause")
    assert result["ok"] is True

    router = ModelRouter()
    ids = [row.id for row in router.select_chain(_request(TaskType.CHAT))]
    assert active["model_id"] not in ids
    assert promoted["model_id"] in ids


@pytest.mark.asyncio
async def test_kill_switch_skips_new_discovery(monkeypatch) -> None:
    _seed_runtime(_lease("auto:openrouter:vendor/canary"))
    set_auto_provision(False, actor="test", reason="pause discovery")
    result = await refresh_provider_catalog(env={"OPENROUTER_API_KEY": "test"})
    assert result["skipped"] is True
    assert result["reason"] == "auto_provision_disabled"


def test_lease_mutations_require_reason_and_enforce_versions() -> None:
    lease = _lease("auto:openrouter:vendor/canary")
    _seed_runtime(lease)

    missing_reason = update_model_lease("openrouter", lease["model_id"], "disable")
    assert missing_reason == {"ok": False, "status": 400, "error": "lease_action_reason_required"}

    repriced = update_model_lease(
        "openrouter",
        lease["model_id"],
        "reprice",
        reason="correct provider feed",
        input_cost_per_million=0.5,
        output_cost_per_million=1.5,
        expected_version=1,
    )
    assert repriced["ok"] is True
    assert repriced["lease"]["pricing_source"] == "manual_override"
    assert repriced["lease"]["version"] == 2
    assert repriced["lease"]["billing_class"] == "paid"

    stale = update_model_lease(
        "openrouter",
        lease["model_id"],
        "disable",
        reason="stale write",
        expected_version=1,
    )
    assert stale["ok"] is False
    assert stale["status"] == 409
    assert stale["error"] == "stale_lease_version"


def test_promotion_requires_evidence_unless_overridden() -> None:
    lease = _lease("auto:openrouter:vendor/canary", calls=0)
    _seed_runtime(lease)
    denied = update_model_lease("openrouter", lease["model_id"], "promote", reason="early")
    assert denied["ok"] is False
    assert denied["error"] == "promotion_criteria_not_met"

    _seed_runtime(_lease("auto:openrouter:vendor/canary", calls=20, errors=0))
    promoted = update_model_lease(
        "openrouter",
        lease["model_id"],
        "promote",
        reason="health and spend verified",
    )
    assert promoted["ok"] is True
    assert promoted["lease"]["status"] == "approved"
    assert promoted["lease"]["traffic_percent"] == 0.0
    assert promoted["lease"]["user_selectable"] is True


def test_manual_zero_price_repricing_never_classifies_a_model_as_free() -> None:
    lease = _lease("auto:openrouter:vendor/canary")
    _seed_runtime(lease)
    repriced = update_model_lease(
        "openrouter",
        lease["model_id"],
        "reprice",
        reason="operator confirmed zero price",
        input_cost_per_million=0.0,
        output_cost_per_million=0.0,
    )
    assert repriced["ok"] is True
    assert repriced["lease"]["pricing_source"] == "manual_override"
    assert repriced["lease"]["billing_class"] == "paid"


def test_policy_updates_require_reason_and_reject_stale_versions() -> None:
    denied = set_auto_provision(True, actor="test")
    assert denied == {"ok": False, "status": 400, "error": "policy_reason_required"}

    first = set_auto_provision(True, actor="test", reason="enable", expected_version=1)
    assert first["ok"] is True
    assert first["policy"]["version"] == 2
    stale = set_auto_provision(False, actor="test", reason="stale", expected_version=1)
    assert stale["ok"] is False
    assert stale["status"] == 409


def test_lease_budget_enforces_daily_cap() -> None:
    from execution_controls import ExecutionAuthorizationError

    lease = _lease("auto:openrouter:vendor/canary", daily_spend_cap_usd=1.0)
    _seed_runtime(lease)
    reservation = lease_budget.reserve(lease["model_id"], 0.4)
    lease_budget.settle(reservation, 0.35)
    lease_budget.reserve(lease["model_id"], 0.5)
    with pytest.raises(ExecutionAuthorizationError):
        lease_budget.reserve(lease["model_id"], 0.5)


def _request(task: TaskType) -> AIRequest:
    context = UserContext(
        user_id="canary-user",
        role=UserRole.FOUNDER,
        project_id="project",
        project_stage="mvp",
        industry="saas",
        tech_stack=[],
        past_feedback=[],
        training_progress={},
        time_logged_today=0,
        tasks_completed_week=0,
    )
    return AIRequest(task_type=task, user_context=context, input_data={})
