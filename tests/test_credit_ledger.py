"""
Credit ledger contract tests. Standalone (no pytest dependency): run with
    python3 tests/test_credit_ledger.py
Exit 0 = all asserts passed. Uses fake sessions/clients only.
"""

from __future__ import annotations

import asyncio
import os
import sys
from types import SimpleNamespace
from typing import Any, Dict, List

# Allow running from repo root or tests/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ai_router_core import (  # noqa: E402
    AICommandLayer,
    AIRequest,
    ModelRouter,
    PromptEngine,
    SafetyEngine,
    SubscriptionTier,
    TaskType,
    UserContext,
    UserRole,
)
from credit_ledger import (  # noqa: E402
    CreditLedgerUnavailable,
    CreditReservation,
    InsufficientCredits,
    ProductionCreditLedgerRequired,
)


class FakeReservationLedger:
    def __init__(self) -> None:
        self.reservations: List[CreditReservation] = []
        self.refunds: List[tuple[CreditReservation, str]] = []

    def reserve(self, *, user_context: Any, task_type: str, cost: int,
                operation_id: str, metadata: Dict[str, Any] | None = None) -> CreditReservation:
        reservation = CreditReservation(
            user_id=user_context.user_id,
            task_type=task_type,
            operation_id=operation_id,
            cost=cost,
            from_subscription=cost,
            from_payg=0,
            credits_after=user_context.credits_remaining - cost,
            ledger_id=f"ledger-{len(self.reservations) + 1}",
            metadata=metadata or {},
        )
        self.reservations.append(reservation)
        return reservation

    def refund(self, reservation: CreditReservation, *, reason: str = "") -> None:
        self.refunds.append((reservation, reason))


class FakeProviderCompletions:
    def __init__(self, *, error: Exception | None = None) -> None:
        self.error = error
        self.calls: List[Dict[str, Any]] = []

    async def create(self, **kwargs: Any) -> Any:
        self.calls.append(kwargs)
        if self.error:
            raise self.error
        return SimpleNamespace(
            choices=[SimpleNamespace(message=SimpleNamespace(content="provider ok"))],
            usage=SimpleNamespace(total_tokens=25),
        )


class FakeOpenAIClient:
    def __init__(self, *, error: Exception | None = None) -> None:
        self.completions = FakeProviderCompletions(error=error)
        self.chat = SimpleNamespace(completions=self.completions)


class FakeUser:
    def __init__(self, *, subscription: int, payg: int,
                 user_id: str = "user-db", total_used: int = 0) -> None:
        self.id = user_id
        self.subscription_credits_remaining = subscription
        self.payg_credits_balance = payg
        self.total_credits_used = total_used
        self.plan_id = "founder_pro"


class FakeQuery:
    def __init__(self, user: FakeUser | None) -> None:
        self.user = user
        self.locked = False

    def filter(self, *_args: Any, **_kwargs: Any) -> "FakeQuery":
        return self

    def with_for_update(self) -> "FakeQuery":
        self.locked = True
        return self

    def one_or_none(self) -> FakeUser | None:
        return self.user


class FakeSession:
    def __init__(self, user: FakeUser | None) -> None:
        self.user = user
        self.query_obj = FakeQuery(user)
        self.added: List[Any] = []
        self.commits = 0

    def query(self, _model: Any) -> FakeQuery:
        return self.query_obj

    def add(self, row: Any) -> None:
        self.added.append(row)

    def commit(self) -> None:
        self.commits += 1


def _user(credits: int = 100, tier: SubscriptionTier = SubscriptionTier.FOUNDER_PRO) -> UserContext:
    return UserContext(
        user_id="user-1",
        role=UserRole.FOUNDER,
        subscription_tier=tier,
        credits_remaining=credits,
        project_id="p_test",
        project_stage="mvp",
        industry="saas",
        tech_stack=[],
        past_feedback=[],
        training_progress={},
        time_logged_today=0,
        tasks_completed_week=0,
    )


def _req(task: TaskType = TaskType.UNICORN_ANALYSIS, credits: int = 100) -> AIRequest:
    return AIRequest(task_type=task, user_context=_user(credits=credits), input_data={})


def test_production_ledger_fails_closed_for_billable_calls() -> None:
    ledger = ProductionCreditLedgerRequired()
    try:
        ledger.reserve(
            user_context=_user(),
            task_type=TaskType.UNICORN_ANALYSIS.value,
            cost=2,
            operation_id=TaskType.UNICORN_ANALYSIS.value,
        )
    except CreditLedgerUnavailable as exc:
        assert "durable credit ledger" in str(exc)
        return
    raise AssertionError("production ledger did not fail closed for billable call")


def test_command_layer_reserves_and_keeps_debit_on_provider_success() -> None:
    async def run() -> None:
        os.environ["OPENAI_API_KEY"] = "sk-test"
        try:
            ledger = FakeReservationLedger()
            provider = FakeOpenAIClient()
            brain = AICommandLayer(
                ModelRouter(),
                PromptEngine(),
                SafetyEngine(),
                provider_clients={"openai": provider},
                credit_ledger=ledger,
            )

            response = await brain.process_request(_req())
            assert response.output == "provider ok"
            assert response.credits_consumed == 2
            assert len(ledger.reservations) == 1
            assert ledger.refunds == []
            assert response.metadata["credit_ledger_id"] == "ledger-1"
            assert response.metadata["credits_after"] == 98
        finally:
            os.environ.pop("OPENAI_API_KEY", None)

    asyncio.run(run())


def test_command_layer_refunds_when_all_providers_fail() -> None:
    async def run() -> None:
        os.environ["OPENAI_API_KEY"] = "sk-test"
        os.environ["ANTHROPIC_API_KEY"] = "sk-ant-test"
        try:
            ledger = FakeReservationLedger()
            failing = SimpleNamespace(
                chat=SimpleNamespace(
                    completions=SimpleNamespace(
                        create=lambda **_: (_ for _ in ()).throw(RuntimeError("provider down"))
                    )
                )
            )
            brain = AICommandLayer(
                ModelRouter(),
                PromptEngine(),
                SafetyEngine(),
                provider_clients={"openai": failing, "anthropic": failing},
                credit_ledger=ledger,
            )

            try:
                await brain.process_request(_req())
            except Exception:
                pass
            else:
                raise AssertionError("provider failure unexpectedly succeeded")

            assert len(ledger.reservations) == 1
            assert len(ledger.refunds) == 1
            reservation, reason = ledger.refunds[0]
            assert reservation.cost == 2
            assert "Provider failed" in reason
        finally:
            os.environ.pop("OPENAI_API_KEY", None)
            os.environ.pop("ANTHROPIC_API_KEY", None)

    asyncio.run(run())


def test_command_layer_does_not_reserve_when_safety_blocks() -> None:
    async def run() -> None:
        ledger = FakeReservationLedger()
        brain = AICommandLayer(
            ModelRouter(),
            PromptEngine(),
            SafetyEngine(),
            provider_clients={"openai": FakeOpenAIClient()},
            credit_ledger=ledger,
        )
        try:
            await brain.process_request(_req(credits=0))
        except PermissionError as exc:
            assert "Insufficient credits" in str(exc)
        else:
            raise AssertionError("insufficient credits did not block before reservation")
        assert ledger.reservations == []
        assert ledger.refunds == []

    asyncio.run(run())


def test_sqlalchemy_ledger_uses_row_lock_and_subscription_first_debit() -> None:
    import credit_ledger

    class FakeBillingEventTypeEnum:
        CREDITS_DEDUCTED = "credits_deducted"
        CREDITS_REFUNDED = "credits_refunded"

        def __new__(cls, value: str) -> str:
            return value

    class FakeCreditLedgerRow:
        def __init__(self, **kwargs: Any) -> None:
            self.__dict__.update(kwargs)
            self.id = "ledger-row-1"

    old_user = getattr(credit_ledger, "User", None)
    old_event = getattr(credit_ledger, "BillingEventTypeEnum", None)
    old_row = getattr(credit_ledger, "CreditLedgerRow", None)
    credit_ledger.User = SimpleNamespace(id="id")  # type: ignore[attr-defined]
    credit_ledger.BillingEventTypeEnum = FakeBillingEventTypeEnum  # type: ignore[attr-defined]
    credit_ledger.CreditLedgerRow = FakeCreditLedgerRow  # type: ignore[attr-defined]
    try:
        user = FakeUser(subscription=1, payg=5, total_used=4)
        session = FakeSession(user)
        ledger = credit_ledger.SQLAlchemyCreditLedger(session)
        reservation = ledger.reserve(
            user_context=SimpleNamespace(user_id="user-db"),
            task_type=TaskType.UNICORN_ANALYSIS.value,
            cost=2,
            operation_id=TaskType.UNICORN_ANALYSIS.value,
        )
        assert session.query_obj.locked is True
        assert session.commits == 1
        assert user.subscription_credits_remaining == 0
        assert user.payg_credits_balance == 4
        assert user.total_credits_used == 6
        assert reservation.from_subscription == 1
        assert reservation.from_payg == 1
        row = session.added[0]
        assert row.event_type == "credits_deducted"
        assert row.credits_delta == -2
        assert row.credits_after == 4
    finally:
        if old_user is None:
            delattr(credit_ledger, "User")
        else:
            credit_ledger.User = old_user  # type: ignore[attr-defined]
        if old_event is None:
            delattr(credit_ledger, "BillingEventTypeEnum")
        else:
            credit_ledger.BillingEventTypeEnum = old_event  # type: ignore[attr-defined]
        if old_row is None:
            credit_ledger.CreditLedgerRow = None  # type: ignore[attr-defined]
        else:
            credit_ledger.CreditLedgerRow = old_row  # type: ignore[attr-defined]


def test_sqlalchemy_ledger_rejects_insufficient_stored_credits() -> None:
    import credit_ledger

    old_user = getattr(credit_ledger, "User", None)
    credit_ledger.User = SimpleNamespace(id="id")  # type: ignore[attr-defined]
    try:
        user = FakeUser(subscription=0, payg=1)
        session = FakeSession(user)
        ledger = credit_ledger.SQLAlchemyCreditLedger(session)
        try:
            ledger.reserve(
                user_context=SimpleNamespace(user_id="user-db"),
                task_type=TaskType.UNICORN_ANALYSIS.value,
                cost=2,
                operation_id=TaskType.UNICORN_ANALYSIS.value,
            )
        except InsufficientCredits:
            assert session.query_obj.locked is True
            assert session.added == []
            assert session.commits == 0
            return
        raise AssertionError("insufficient stored credits did not raise")
    finally:
        if old_user is None:
            delattr(credit_ledger, "User")
        else:
            credit_ledger.User = old_user  # type: ignore[attr-defined]


def main() -> int:
    tests = [
        test_production_ledger_fails_closed_for_billable_calls,
        test_command_layer_reserves_and_keeps_debit_on_provider_success,
        test_command_layer_refunds_when_all_providers_fail,
        test_command_layer_does_not_reserve_when_safety_blocks,
        test_sqlalchemy_ledger_uses_row_lock_and_subscription_first_debit,
        test_sqlalchemy_ledger_rejects_insufficient_stored_credits,
    ]
    for test in tests:
        test()
        print(f"PASS {test.__name__}")
    print(f"\nAll {len(tests)} credit ledger tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
