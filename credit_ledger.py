"""
Durable credit reservation/debit boundary for central AI execution.

The AI command path reserves credits before calling a provider and records an
offsetting refund if the provider call fails. The SQLAlchemy implementation uses
row locks so concurrent billable calls cannot overspend a user's stored balance.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Dict, Optional, Protocol


User = None
BillingEventTypeEnum = None
CreditLedgerRow = None


class CreditLedgerError(RuntimeError):
    """Base class for credit ledger failures."""


class CreditLedgerUnavailable(CreditLedgerError):
    """A billable operation cannot be recorded durably."""


class InsufficientCredits(CreditLedgerError):
    """User does not have enough stored credits for the requested operation."""


@dataclass
class CreditReservation:
    user_id: str
    task_type: str
    operation_id: str
    cost: int
    from_subscription: int
    from_payg: int
    credits_after: int
    plan_id: str = ""
    ledger_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class CreditLedger(Protocol):
    def reserve(self, *, user_context: Any, task_type: str, cost: int,
                operation_id: str, metadata: Optional[Dict[str, Any]] = None) -> CreditReservation:
        ...

    def refund(self, reservation: CreditReservation, *, reason: str = "") -> None:
        ...


class NoopCreditLedger:
    """Development/test ledger that records no durable state."""

    def reserve(self, *, user_context: Any, task_type: str, cost: int,
                operation_id: str, metadata: Optional[Dict[str, Any]] = None) -> CreditReservation:
        return CreditReservation(
            user_id=str(getattr(user_context, "user_id", "")),
            task_type=task_type,
            operation_id=operation_id,
            cost=cost,
            from_subscription=cost,
            from_payg=0,
            credits_after=max(0, int(getattr(user_context, "credits_remaining", 0) or 0) - cost),
            plan_id=str(getattr(getattr(user_context, "subscription_tier", ""), "value", "")),
            metadata=metadata or {},
        )

    def refund(self, reservation: CreditReservation, *, reason: str = "") -> None:
        return None


class ProductionCreditLedgerRequired:
    """Fail closed for production billable AI calls until a durable ledger is attached."""

    def reserve(self, *, user_context: Any, task_type: str, cost: int,
                operation_id: str, metadata: Optional[Dict[str, Any]] = None) -> CreditReservation:
        if cost <= 0:
            return NoopCreditLedger().reserve(
                user_context=user_context,
                task_type=task_type,
                cost=cost,
                operation_id=operation_id,
                metadata=metadata,
            )
        raise CreditLedgerUnavailable("durable credit ledger is required for billable AI operations")

    def refund(self, reservation: CreditReservation, *, reason: str = "") -> None:
        return None


class SQLAlchemyCreditLedger:
    """Credit ledger backed by the existing users and credit_ledger tables."""

    def __init__(self, session: Any) -> None:
        self.session = session

    def reserve(self, *, user_context: Any, task_type: str, cost: int,
                operation_id: str, metadata: Optional[Dict[str, Any]] = None) -> CreditReservation:
        if cost <= 0:
            return NoopCreditLedger().reserve(
                user_context=user_context,
                task_type=task_type,
                cost=cost,
                operation_id=operation_id,
                metadata=metadata,
            )

        user = self._locked_user(str(getattr(user_context, "user_id", "")))
        subscription = int(getattr(user, "subscription_credits_remaining", 0) or 0)
        payg = int(getattr(user, "payg_credits_balance", 0) or 0)
        total = subscription + payg
        if total < cost:
            raise InsufficientCredits(
                f"insufficient credits for {task_type}: required {cost}, available {total}"
            )

        from_subscription = min(subscription, cost)
        from_payg = cost - from_subscription
        user.subscription_credits_remaining = subscription - from_subscription
        user.payg_credits_balance = payg - from_payg
        user.total_credits_used = int(getattr(user, "total_credits_used", 0) or 0) + cost
        credits_after = user.subscription_credits_remaining + user.payg_credits_balance

        ledger = self._ledger_row(
            user_id=getattr(user, "id"),
            event_type="credits_deducted",
            credits_delta=-cost,
            credits_after=credits_after,
            from_subscription=from_subscription,
            from_payg=from_payg,
            task_type=task_type,
            operation_id=operation_id,
            plan_id=str(getattr(user, "plan_id", "") or ""),
            description=f"Reserved {cost} credit(s) for {task_type}",
        )
        self.session.add(ledger)
        self.session.commit()

        return CreditReservation(
            user_id=str(getattr(user, "id")),
            task_type=task_type,
            operation_id=operation_id,
            cost=cost,
            from_subscription=from_subscription,
            from_payg=from_payg,
            credits_after=credits_after,
            plan_id=str(getattr(user, "plan_id", "") or ""),
            ledger_id=str(getattr(ledger, "id", "") or ""),
            metadata=metadata or {},
        )

    def refund(self, reservation: CreditReservation, *, reason: str = "") -> None:
        if reservation.cost <= 0:
            return

        user = self._locked_user(reservation.user_id)
        user.subscription_credits_remaining = int(
            getattr(user, "subscription_credits_remaining", 0) or 0
        ) + reservation.from_subscription
        user.payg_credits_balance = int(
            getattr(user, "payg_credits_balance", 0) or 0
        ) + reservation.from_payg
        user.total_credits_used = max(
            0,
            int(getattr(user, "total_credits_used", 0) or 0) - reservation.cost,
        )
        credits_after = user.subscription_credits_remaining + user.payg_credits_balance

        ledger = self._ledger_row(
            user_id=getattr(user, "id"),
            event_type="credits_refunded",
            credits_delta=reservation.cost,
            credits_after=credits_after,
            from_subscription=reservation.from_subscription,
            from_payg=reservation.from_payg,
            task_type=reservation.task_type,
            operation_id=reservation.operation_id,
            plan_id=reservation.plan_id,
            description=reason or f"Refunded {reservation.cost} credit(s) for {reservation.task_type}",
        )
        self.session.add(ledger)
        self.session.commit()

    def _locked_user(self, user_id: str) -> Any:
        if not user_id:
            raise CreditLedgerUnavailable("user id is required for credit ledger debit")
        user_model = self._user_model()

        user = (
            self.session.query(user_model)
            .filter(user_model.id == user_id)
            .with_for_update()
            .one_or_none()
        )
        if user is None:
            raise CreditLedgerUnavailable(f"user {user_id} not found for credit ledger debit")
        return user

    def _ledger_row(self, *, user_id: Any, event_type: str, credits_delta: int,
                    credits_after: int, from_subscription: int, from_payg: int,
                    task_type: str, operation_id: str, plan_id: str,
                    description: str) -> Any:
        event_enum, ledger_model = self._ledger_models()

        return ledger_model(
            user_id=user_id,
            event_type=event_enum(event_type),
            credits_delta=credits_delta,
            credits_after=credits_after,
            from_subscription=from_subscription,
            from_payg=from_payg,
            usd_charged_payg=Decimal("0"),
            task_type=task_type,
            operation_id=operation_id,
            plan_id=plan_id,
            description=description,
        )

    def _user_model(self) -> Any:
        global User
        if User is None:
            try:
                from database_schema import User as SchemaUser
            except ImportError as exc:
                raise CreditLedgerUnavailable("database schema is unavailable for credit ledger debit") from exc
            User = SchemaUser
        return User

    def _ledger_models(self) -> tuple[Any, Any]:
        global BillingEventTypeEnum, CreditLedgerRow
        if BillingEventTypeEnum is None or CreditLedgerRow is None:
            try:
                from database_schema import BillingEventTypeEnum as SchemaEventEnum
                from database_schema import CreditLedger as SchemaCreditLedger
            except ImportError as exc:
                raise CreditLedgerUnavailable("database schema is unavailable for credit ledger write") from exc
            BillingEventTypeEnum = SchemaEventEnum
            CreditLedgerRow = SchemaCreditLedger
        return BillingEventTypeEnum, CreditLedgerRow


class SQLAlchemySessionFactoryCreditLedger:
    """Open a short-lived SQLAlchemy session per credit ledger operation."""

    def __init__(self, session_factory: Any) -> None:
        self.session_factory = session_factory

    def reserve(self, *, user_context: Any, task_type: str, cost: int,
                operation_id: str, metadata: Optional[Dict[str, Any]] = None) -> CreditReservation:
        session = self.session_factory()
        try:
            return SQLAlchemyCreditLedger(session).reserve(
                user_context=user_context,
                task_type=task_type,
                cost=cost,
                operation_id=operation_id,
                metadata=metadata,
            )
        finally:
            session.close()

    def refund(self, reservation: CreditReservation, *, reason: str = "") -> None:
        session = self.session_factory()
        try:
            SQLAlchemyCreditLedger(session).refund(reservation, reason=reason)
        finally:
            session.close()


def default_credit_ledger() -> CreditLedger:
    if os.environ.get("ENVIRONMENT", "development").lower() in {"production", "staging"}:
        return ProductionCreditLedgerRequired()
    return NoopCreditLedger()
