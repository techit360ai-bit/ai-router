"""
Wave 6 provider execution tests.

Standalone:
    python3 tests/test_provider_execution.py
Pytest:
    python3 -m pytest tests/test_provider_execution.py
"""
from __future__ import annotations

import asyncio
import os
import sys
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ai_router_core import (  # noqa: E402
    AICommandLayer,
    AIRequest,
    AccountingTransactionError,
    ModelRouter,
    ProviderCallError,
    ProviderConfigurationError,
    PromptEngine,
    SafetyEngine,
    SubscriptionTier,
    TaskType,
    UsageLedgerRecorder,
    UserContext,
    UserRole,
)


def _ctx() -> UserContext:
    return UserContext(
        user_id="01890000-0000-7000-8000-0000000000aa",
        role=UserRole.FOUNDER,
        subscription_tier=SubscriptionTier.FOUNDER_PRO,
        credits_remaining=100,
        project_id="p_test",
        project_stage="mvp",
        industry="saas",
        tech_stack=[],
        past_feedback=[],
        training_progress={},
        time_logged_today=0,
        tasks_completed_week=0,
    )


def _layer() -> AICommandLayer:
    return AICommandLayer(ModelRouter(), PromptEngine(), SafetyEngine())


class FakeOpenAICompletions:
    def __init__(self, *, response: object | None = None, error: Exception | None = None) -> None:
        self.response = response
        self.error = error

    async def create(self, **_kwargs):
        if self.error:
            raise self.error
        return self.response


class FakeOpenAIClient:
    def __init__(self, *, response: object | None = None, error: Exception | None = None) -> None:
        completions = FakeOpenAICompletions(response=response, error=error)
        self.chat = SimpleNamespace(completions=completions)


class FakeAnthropicMessages:
    def __init__(self, *, response: object | None = None, error: Exception | None = None) -> None:
        self.response = response
        self.error = error

    async def create(self, **_kwargs):
        if self.error:
            raise self.error
        return self.response


class FakeAnthropicClient:
    def __init__(self, *, response: object | None = None, error: Exception | None = None) -> None:
        self.messages = FakeAnthropicMessages(response=response, error=error)


class FakeCreditLedger:
    def reserve(self, *, user_context, task_type, cost, operation_id, metadata=None):
        return SimpleNamespace(
            cost=cost,
            from_subscription=cost,
            from_payg=0,
            credits_after=user_context.credits_remaining - cost,
            ledger_id="ledger-test",
        )

    def refund(self, _reservation, *, reason: str = "") -> None:
        return None


def _req(task: TaskType = TaskType.UNICORN_ANALYSIS) -> AIRequest:
    return AIRequest(task_type=task, user_context=_ctx(), input_data={"idea": "x"})


async def _test_openai_provider_response_is_normalized() -> None:
    os.environ["OPENAI_API_KEY"] = "test-openai"
    os.environ["AI_USAGE_LEDGER_ENABLED"] = "false"
    layer = AICommandLayer(
        ModelRouter(),
        PromptEngine(),
        SafetyEngine(),
        provider_clients={"openai": FakeOpenAIClient(response=SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="real response"))],
            usage=SimpleNamespace(prompt_tokens=11, completion_tokens=7, total_tokens=18),
        ))},
    )

    response = await layer.process_request(_req(TaskType.UNICORN_ANALYSIS))

    assert response.output == "real response"
    assert response.tokens_used == 18
    assert response.metadata["provider"] == "openai_gpt4"
    assert response.metadata["prompt_tokens"] == 11
    assert response.metadata["completion_tokens"] == 7
    assert response.credits_consumed > 0

    os.environ.pop("OPENAI_API_KEY", None)
    os.environ.pop("AI_USAGE_LEDGER_ENABLED", None)


async def _test_fallback_uses_next_provider_after_failure() -> None:
    os.environ["OPENAI_API_KEY"] = "test-openai"
    os.environ["ANTHROPIC_API_KEY"] = "test-anthropic"
    os.environ["AI_USAGE_LEDGER_ENABLED"] = "false"
    layer = AICommandLayer(
        ModelRouter(),
        PromptEngine(),
        SafetyEngine(),
        provider_clients={
            "openai": FakeOpenAIClient(error=ProviderCallError("openai down")),
            "anthropic": FakeAnthropicClient(response=SimpleNamespace(
                content=[SimpleNamespace(text="anthropic response")],
                usage=SimpleNamespace(input_tokens=10, output_tokens=5),
            )),
        },
    )

    response = await layer.process_request(_req(TaskType.UNICORN_ANALYSIS))

    assert response.output == "anthropic response"
    assert response.model_used == "claude-sonnet-4-6"
    assert response.tokens_used == 15
    assert response.metadata["attempt"] == 2
    assert response.metadata["provider"] == "anthropic_claude"

    os.environ.pop("OPENAI_API_KEY", None)
    os.environ.pop("ANTHROPIC_API_KEY", None)
    os.environ.pop("AI_USAGE_LEDGER_ENABLED", None)


async def _test_missing_keys_fail_closed_without_placeholder() -> None:
    for key in ("OPENAI_API_KEY", "ANTHROPIC_API_KEY", "ALLOW_AI_PLACEHOLDER_RESPONSES"):
        os.environ.pop(key, None)
    os.environ["ENVIRONMENT"] = "production"
    os.environ["DATABASE_URL"] = "postgresql://example"
    layer = AICommandLayer(
        ModelRouter(),
        PromptEngine(),
        SafetyEngine(),
        credit_ledger=FakeCreditLedger(),
    )
    try:
        await layer.process_request(_req(TaskType.UNICORN_ANALYSIS))
    except ProviderConfigurationError as exc:
        assert "OPENAI_API_KEY" in str(exc) or "ANTHROPIC_API_KEY" in str(exc)
    else:
        raise AssertionError("missing provider keys must fail closed")
    finally:
        os.environ.pop("ENVIRONMENT", None)
        os.environ.pop("DATABASE_URL", None)


async def _test_usage_ledger_recorder_invoked() -> None:
    os.environ["OPENAI_API_KEY"] = "test-openai"
    os.environ["DATABASE_URL"] = "postgresql://example"
    layer = AICommandLayer(
        ModelRouter(),
        PromptEngine(),
        SafetyEngine(),
        provider_clients={"openai": FakeOpenAIClient(response=SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="ledger response"))],
            usage=SimpleNamespace(total_tokens=9),
        ))},
    )

    fake_recorder = AsyncMock()
    with patch("ai_router_core.UsageLedgerRecorder.from_env", return_value=fake_recorder):
        response = await layer.process_request(_req(TaskType.UNICORN_ANALYSIS))

    fake_recorder.record.assert_awaited_once()
    assert response.metadata.get("request_id")

    os.environ.pop("OPENAI_API_KEY", None)
    os.environ.pop("DATABASE_URL", None)


async def _test_missing_database_url_fails_closed_in_production() -> None:
    os.environ["OPENAI_API_KEY"] = "test-openai"
    os.environ["ENVIRONMENT"] = "production"
    os.environ.pop("DATABASE_URL", None)
    os.environ.pop("AI_USAGE_LEDGER_ENABLED", None)
    layer = AICommandLayer(
        ModelRouter(),
        PromptEngine(),
        SafetyEngine(),
        provider_clients={"openai": FakeOpenAIClient(response=SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="should not finish"))],
            usage=SimpleNamespace(total_tokens=4),
        ))},
    )

    try:
        await layer.process_request(_req(TaskType.UNICORN_ANALYSIS))
    except ProviderConfigurationError as exc:
        assert "DATABASE_URL" in str(exc)
    else:
        raise AssertionError("production ledger requires DATABASE_URL")
    finally:
        os.environ.pop("OPENAI_API_KEY", None)
        os.environ.pop("ENVIRONMENT", None)


def _test_credit_debit_uses_subscription_then_payg() -> None:
    class FakeSession:
        def __init__(self) -> None:
            self.calls = []
            self.user_row = SimpleNamespace(
                subscription_credits_remaining=2,
                payg_credits_balance=5,
                total_credits_used=0,
                plan_id="founder_pro",
            )

        def execute(self, statement, params=None):
            sql = str(statement)
            self.calls.append((sql, params or {}))
            if "SELECT subscription_credits_remaining" in sql:
                return SimpleNamespace(fetchone=lambda: self.user_row)
            return SimpleNamespace(fetchone=lambda: None)

    session = FakeSession()
    request = _req(TaskType.STARTUP_STRATEGY)
    response = SimpleNamespace(
        credits_consumed=3,
        metadata={"request_id": "req_test", "provider": "openai_gpt4"},
        model_used="gpt-4-turbo",
    )

    result = UsageLedgerRecorder._debit_credits(session, request, response)

    assert result == {"from_subscription": 2, "from_payg": 1, "credits_after": 4}
    update_params = session.calls[1][1]
    assert update_params["subscription_credits"] == 0
    assert update_params["payg_credits"] == 4
    ledger_params = session.calls[2][1]
    assert ledger_params["credits_delta"] == -3
    assert ledger_params["from_subscription"] == 2
    assert ledger_params["from_payg"] == 1


def _test_credit_debit_rejects_insufficient_durable_balance() -> None:
    class FakeSession:
        def execute(self, statement, params=None):
            return SimpleNamespace(fetchone=lambda: SimpleNamespace(
                subscription_credits_remaining=0,
                payg_credits_balance=1,
                total_credits_used=0,
                plan_id="founder_pro",
            ))

    response = SimpleNamespace(
        credits_consumed=3,
        metadata={"request_id": "req_test", "provider": "openai_gpt4"},
        model_used="gpt-4-turbo",
    )
    try:
        UsageLedgerRecorder._debit_credits(FakeSession(), _req(TaskType.STARTUP_STRATEGY), response)
    except AccountingTransactionError as exc:
        assert "insufficient durable credits" in str(exc)
    else:
        raise AssertionError("durable credit debit must reject insufficient DB balance")


def test_openai_provider_response_is_normalized() -> None:
    asyncio.run(_test_openai_provider_response_is_normalized())


def test_fallback_uses_next_provider_after_failure() -> None:
    asyncio.run(_test_fallback_uses_next_provider_after_failure())


def test_missing_keys_fail_closed_without_placeholder() -> None:
    asyncio.run(_test_missing_keys_fail_closed_without_placeholder())


def test_usage_ledger_recorder_invoked() -> None:
    asyncio.run(_test_usage_ledger_recorder_invoked())


def test_missing_database_url_fails_closed_in_production() -> None:
    asyncio.run(_test_missing_database_url_fails_closed_in_production())


def test_credit_debit_uses_subscription_then_payg() -> None:
    _test_credit_debit_uses_subscription_then_payg()


def test_credit_debit_rejects_insufficient_durable_balance() -> None:
    _test_credit_debit_rejects_insufficient_durable_balance()


def main() -> int:
    tests = [
        test_openai_provider_response_is_normalized,
        test_fallback_uses_next_provider_after_failure,
        test_missing_keys_fail_closed_without_placeholder,
        test_usage_ledger_recorder_invoked,
        test_missing_database_url_fails_closed_in_production,
        test_credit_debit_uses_subscription_then_payg,
        test_credit_debit_rejects_insufficient_durable_balance,
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print(f"\nAll {len(tests)} provider execution tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
