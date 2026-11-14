"""The command layer is a process-wide singleton; its telemetry log must not
grow for the life of the process."""

from __future__ import annotations

from ai_router_core import AICommandLayer, ModelRouter, PromptEngine, SafetyEngine


def test_execution_log_is_bounded(monkeypatch) -> None:
    monkeypatch.setenv("AI_EXECUTION_LOG_MAX_ENTRIES", "100")
    command_layer = AICommandLayer(ModelRouter(), PromptEngine(), SafetyEngine())
    for index in range(250):
        command_layer.execution_log.append({"event": "provider_attempt", "request_id": str(index)})
    assert len(command_layer.execution_log) == 100
    assert command_layer.execution_log[0]["request_id"] == "150"
