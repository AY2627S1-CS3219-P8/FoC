"""Transport-independent Credit domain operations.

The numbered ``AUDIT`` comments expose validation, locking, mutation, and
ledger stages. This module knows nothing about RabbitMQ event names, event
parsing, HTTP request schemas, or outbox publication. Callers own transactions.
"""

import re
from dataclasses import dataclass
from typing import Literal
from uuid import UUID, uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import CreditAccount, CreditReservation, CreditTransaction, utc_now


class CreditDomainError(RuntimeError):
    """Base class for deterministic Credit-domain failures."""


class CreditAccountNotFound(CreditDomainError):
    """A requested Credit account does not exist."""


class CreditIdentifierConflict(CreditDomainError):
    """User and student identifiers contradict an existing account."""


class CreditStateConflict(CreditDomainError):
    """An operation contradicts a durable reservation or balance state."""


class InvalidCreditAdjustment(CreditDomainError):
    """An administrator adjustment would violate a balance invariant."""


@dataclass(frozen=True)
class ReservationResult:
    """Domain result; the application layer chooses an integration event."""

    outcome: Literal["RESERVED", "REJECTED"]
    reason: str | None = None
    replayed: bool = False


@dataclass(frozen=True)
class ResolutionResult:
    """Result of transferring or releasing a reservation."""

    replayed: bool = False


def get_account(db: Session, user_id: UUID) -> CreditAccount:
    account = db.get(CreditAccount, user_id)
    if account is None:
        raise CreditAccountNotFound("Credit account not found")
    return account


def list_transactions(
    db: Session, user_id: UUID, *, limit: int, offset: int
) -> tuple[list[CreditTransaction], int]:
    filters = (CreditTransaction.affected_user_id == user_id,)
    total = db.scalar(
        select(func.count()).select_from(CreditTransaction).where(*filters)
    ) or 0
    items = list(
        db.scalars(
            select(CreditTransaction)
            .where(*filters)
            .order_by(
                CreditTransaction.created_at.desc(), CreditTransaction.id.desc()
            )
            .limit(limit)
            .offset(offset)
        )
    )
    return items, total


def _locked_account(db: Session, user_id: UUID) -> CreditAccount | None:
    return db.scalar(
        select(CreditAccount)
        .where(CreditAccount.user_id == user_id)
        .with_for_update()
    )


def _audit_transaction(
    db: Session,
    *,
    affected_user_id: UUID,
    transaction_type: str,
    outcome: str,
    amount: int,
    available_delta: int,
    reserved_delta: int,
    reason: str,
    correlation_id: UUID,
    operation_id: UUID | None = None,
    order_id: UUID | None = None,
    counterparty_user_id: UUID | None = None,
    actor_user_id: UUID | None = None,
) -> CreditTransaction:
    transaction = CreditTransaction(
        event_id=operation_id,
        order_id=order_id,
        affected_user_id=affected_user_id,
        counterparty_user_id=counterparty_user_id,
        actor_user_id=actor_user_id,
        transaction_type=transaction_type,
        outcome=outcome,
        amount=amount,
        available_delta=available_delta,
        reserved_delta=reserved_delta,
        reason=reason,
        correlation_id=correlation_id,
    )
    db.add(transaction)
    return transaction


def create_account(
    db: Session,
    *,
    user_id: UUID,
    nus_student_number: str,
    initial_allocation: int,
    actor_user_id: UUID | None = None,
    operation_id: UUID | None = None,
    correlation_id: UUID | None = None,
) -> CreditAccount:
    """Idempotently create one account and grant its initial allocation."""

    # AUDIT 1 - Reject invalid inputs before staging database changes.
    normalized_student_number = nus_student_number.strip().upper()
    if initial_allocation <= 0:
        raise ValueError("initial_allocation must be positive")
    if not re.fullmatch(r"[AU][0-9]{7}[A-Z]", normalized_student_number):
        raise ValueError("nus_student_number has an invalid format")

    # AUDIT 2 - Lock both account identifiers and reject conflicting mappings.
    by_user = _locked_account(db, user_id)
    by_student_number = db.scalar(
        select(CreditAccount)
        .where(CreditAccount.nus_student_number == normalized_student_number)
        .with_for_update()
    )
    if by_user is not None and by_user.nus_student_number != normalized_student_number:
        raise CreditIdentifierConflict(
            "User already has a different credit account identifier"
        )
    if by_student_number is not None and by_student_number.user_id != user_id:
        raise CreditIdentifierConflict(
            "Student number already belongs to another credit account"
        )

    # AUDIT 3 - Create a zero-balance account only on first provisioning.
    account = by_user or by_student_number
    if account is None:
        account = CreditAccount(
            user_id=user_id,
            nus_student_number=normalized_student_number,
            available_balance=0,
            reserved_balance=0,
            status="active",
        )
        db.add(account)

    # AUDIT 4 - The allocation timestamp is the durable idempotency marker.
    if account.initial_allocation_granted_at is not None:
        return account

    # AUDIT 5 - Grant and ledger the initial credits in one transaction.
    granted_at = utc_now()
    account.available_balance += initial_allocation
    account.initial_allocation_granted_at = granted_at
    account.updated_at = granted_at
    _audit_transaction(
        db,
        operation_id=operation_id,
        affected_user_id=account.user_id,
        actor_user_id=actor_user_id,
        transaction_type="INITIAL_ALLOCATION",
        outcome="SUCCEEDED",
        amount=initial_allocation,
        available_delta=initial_allocation,
        reserved_delta=0,
        reason="INITIAL_ACCOUNT_ALLOCATION",
        correlation_id=correlation_id or operation_id or uuid4(),
    )
    return account


def reserve_credits(
    db: Session,
    *,
    order_id: UUID,
    requester_id: UUID,
    amount: int,
    operation_id: UUID,
    correlation_id: UUID,
) -> ReservationResult:
    """Place an order-sized hold or return a durable rejection outcome."""

    if amount <= 0:
        raise ValueError("Reservation amount must be positive")

    # AUDIT 1 - Order UUID is the semantic idempotency key for a hold.
    reservation = db.scalar(
        select(CreditReservation)
        .where(CreditReservation.order_id == order_id)
        .with_for_update()
    )
    if reservation is not None:
        if reservation.requester_id != requester_id or reservation.amount != amount:
            raise CreditStateConflict(
                "Order reservation conflicts with requester or credit amount"
            )
        if reservation.status != "ACTIVE":
            raise CreditStateConflict(
                f"Cannot reserve an order already {reservation.status.lower()}"
            )
        return ReservationResult(outcome="RESERVED", replayed=True)

    # AUDIT 2 - Lock the account before reading or moving its balance.
    account = _locked_account(db, requester_id)
    rejection_reason: str | None = None
    if account is None:
        rejection_reason = "ACCOUNT_NOT_FOUND"
    elif account.status != "active":
        rejection_reason = "ACCOUNT_NOT_ACTIVE"
    elif account.available_balance < amount:
        rejection_reason = "INSUFFICIENT_CREDIT"

    # AUDIT 3 - A normal refusal is ledgered, not raised as a system failure.
    if rejection_reason is not None:
        _audit_transaction(
            db,
            operation_id=operation_id,
            order_id=order_id,
            affected_user_id=requester_id,
            transaction_type="RESERVATION",
            outcome="REJECTED",
            amount=amount,
            available_delta=0,
            reserved_delta=0,
            reason=rejection_reason,
            correlation_id=correlation_id,
        )
        return ReservationResult(outcome="REJECTED", reason=rejection_reason)

    assert account is not None

    # AUDIT 4 - Move, never mint: the requester's total credit is unchanged.
    account.available_balance -= amount
    account.reserved_balance += amount
    account.updated_at = utc_now()
    db.add(
        CreditReservation(
            order_id=order_id,
            requester_id=requester_id,
            amount=amount,
            status="ACTIVE",
            correlation_id=correlation_id,
        )
    )

    # AUDIT 5 - Record the signed balance movement for reconciliation.
    _audit_transaction(
        db,
        operation_id=operation_id,
        order_id=order_id,
        affected_user_id=requester_id,
        transaction_type="RESERVATION",
        outcome="SUCCEEDED",
        amount=amount,
        available_delta=-amount,
        reserved_delta=amount,
        reason="ORDER_CREDIT_RESERVED",
        correlation_id=correlation_id,
    )
    return ReservationResult(outcome="RESERVED")


def transfer_reserved_credits(
    db: Session,
    *,
    order_id: UUID,
    requester_id: UUID,
    courier_id: UUID,
    amount: int,
    operation_id: UUID,
    correlation_id: UUID,
    settlement_reason: Literal["ORDER_COMPLETED", "ORDER_CANCELLED_AFTER_PICKUP"],
) -> ResolutionResult:
    """Settle one active reservation from its requester to its courier."""

    if amount <= 0:
        raise ValueError("Settlement amount must be positive")

    # AUDIT 1 - Lock and validate the reservation before touching balances.
    reservation = db.scalar(
        select(CreditReservation)
        .where(CreditReservation.order_id == order_id)
        .with_for_update()
    )
    if reservation is None:
        raise CreditStateConflict("No reservation exists for order settlement")
    if requester_id == courier_id:
        raise CreditStateConflict("Requester and courier must be distinct accounts")
    if reservation.requester_id != requester_id or reservation.amount != amount:
        raise CreditStateConflict("Settlement conflicts with the original reservation")
    if reservation.status == "TRANSFERRED":
        if reservation.courier_id != courier_id:
            raise CreditStateConflict("Reservation was transferred to another courier")
        return ResolutionResult(replayed=True)
    if reservation.status != "ACTIVE":
        raise CreditStateConflict("A released reservation cannot be transferred")

    # AUDIT 2 - Lock both accounts in database UUID order to avoid deadlocks.
    account_rows = list(
        db.scalars(
            select(CreditAccount)
            .where(CreditAccount.user_id.in_([requester_id, courier_id]))
            .order_by(CreditAccount.user_id)
            .with_for_update()
        )
    )
    accounts = {account.user_id: account for account in account_rows}
    requester = accounts.get(requester_id)
    courier = accounts.get(courier_id)
    if requester is None or courier is None:
        raise CreditStateConflict("Requester or courier credit account does not exist")
    if courier.status != "active":
        raise CreditStateConflict("Courier credit account must be active")
    if requester.reserved_balance < reservation.amount:
        raise CreditStateConflict("Requester reserved balance is inconsistent")

    # AUDIT 3 - Settle reserved credit to the courier without minting credit.
    requester.reserved_balance -= reservation.amount
    courier.available_balance += reservation.amount
    resolved_at = utc_now()
    requester.updated_at = resolved_at
    courier.updated_at = resolved_at
    reservation.courier_id = courier_id
    reservation.status = "TRANSFERRED"
    reservation.resolved_at = resolved_at

    # AUDIT 4 - Ledger each side with the business reason for settlement.
    _audit_transaction(
        db,
        operation_id=operation_id,
        order_id=order_id,
        affected_user_id=requester_id,
        counterparty_user_id=courier_id,
        transaction_type="TRANSFER",
        outcome="SUCCEEDED",
        amount=amount,
        available_delta=0,
        reserved_delta=-amount,
        reason=f"{settlement_reason}_REQUESTER_DEBIT",
        correlation_id=correlation_id,
    )
    _audit_transaction(
        db,
        operation_id=operation_id,
        order_id=order_id,
        affected_user_id=courier_id,
        counterparty_user_id=requester_id,
        transaction_type="TRANSFER",
        outcome="SUCCEEDED",
        amount=amount,
        available_delta=amount,
        reserved_delta=0,
        reason=f"{settlement_reason}_COURIER_CREDIT",
        correlation_id=correlation_id,
    )
    return ResolutionResult()


def release_reserved_credits(
    db: Session,
    *,
    order_id: UUID,
    requester_id: UUID,
    amount: int,
    operation_id: UUID,
    correlation_id: UUID,
    release_reason: Literal["ORDER_CANCELLED", "ORDER_EXPIRED"],
) -> ResolutionResult:
    """Return one active reservation to its requester."""

    if amount <= 0:
        raise ValueError("Release amount must be positive")

    # AUDIT 1 - Lock and verify the exact reservation for this order.
    reservation = db.scalar(
        select(CreditReservation)
        .where(CreditReservation.order_id == order_id)
        .with_for_update()
    )
    if reservation is None:
        raise CreditStateConflict("No reservation exists for order release")
    if reservation.requester_id != requester_id or reservation.amount != amount:
        raise CreditStateConflict("Release conflicts with the original reservation")
    if reservation.status == "RELEASED":
        return ResolutionResult(replayed=True)
    if reservation.status != "ACTIVE":
        raise CreditStateConflict("A transferred reservation cannot be released")

    # AUDIT 2 - Lock the owner; suspension does not forfeit held credit.
    requester = _locked_account(db, requester_id)
    if requester is None:
        raise CreditStateConflict("Reservation owner credit account does not exist")
    if requester.reserved_balance < reservation.amount:
        raise CreditStateConflict("Requester reserved balance is inconsistent")

    # AUDIT 3 - Reverse the hold without changing requester total credit.
    requester.reserved_balance -= reservation.amount
    requester.available_balance += reservation.amount
    resolved_at = utc_now()
    requester.updated_at = resolved_at
    reservation.status = "RELEASED"
    reservation.resolved_at = resolved_at

    # AUDIT 4 - Ledger the release for reconciliation.
    _audit_transaction(
        db,
        operation_id=operation_id,
        order_id=order_id,
        affected_user_id=requester_id,
        transaction_type="RELEASE",
        outcome="SUCCEEDED",
        amount=amount,
        available_delta=amount,
        reserved_delta=-amount,
        reason=release_reason,
        correlation_id=correlation_id,
    )
    return ResolutionResult()


def adjust_account(
    db: Session,
    *,
    user_id: UUID,
    actor_user_id: UUID,
    amount: int,
    reason: str,
    correlation_id: UUID,
) -> CreditAccount:
    """Apply an authorized administrator correction to available credit."""

    # AUDIT 1 - Validate domain inputs; authentication belongs at the API edge.
    normalized_reason = reason.strip()
    if amount == 0 or abs(amount) > 1000:
        raise InvalidCreditAdjustment(
            "Adjustment amount must be between -1000 and 1000 and non-zero"
        )
    if not 5 <= len(normalized_reason) <= 500:
        raise InvalidCreditAdjustment(
            "Adjustment reason must contain between 5 and 500 characters"
        )

    # AUDIT 2 - Lock the account and preserve the non-negative invariant.
    account = _locked_account(db, user_id)
    if account is None:
        raise CreditAccountNotFound("Credit account not found")
    adjusted_balance = account.available_balance + amount
    if adjusted_balance < 0:
        raise InvalidCreditAdjustment(
            "Adjustment would make available credit negative"
        )

    # AUDIT 3 - Apply the signed available-balance change.
    account.available_balance = adjusted_balance
    account.updated_at = utc_now()

    # AUDIT 4 - Ledger actor, amount, reason, and correlation identifier.
    _audit_transaction(
        db,
        affected_user_id=user_id,
        actor_user_id=actor_user_id,
        transaction_type="ADMIN_ADJUSTMENT",
        outcome="SUCCEEDED",
        amount=abs(amount),
        available_delta=amount,
        reserved_delta=0,
        reason=normalized_reason,
        correlation_id=correlation_id,
    )
    return account
