# AI Assistance Disclosure:
# Tool: Codex (model: GPT-6), date: 2026-09-30
# Scope: Writing implementation code; Refactoring and documentation improvements — implement synchronous active detail reads with a safe transport-independent availability exception, preserving programming errors and caller-owned session cleanup.
# Scope: Writing implementation code; Refactoring and documentation improvements — implement default/bounded pagination with shared validation issues before queries and reuse the safe availability boundary for listing and detail reads. (ai-20260930-014)
# Scope: Writing implementation code; Refactoring and documentation improvements — expose controlled categories through the safe availability boundary and immutable approved areas in declared order without database access. (ai-20260930-015)
# Author review: Keith confirmed review of this file.
# Details: ../../ai/usage-log.md; ai-20260930-013; ai-20260930-014; ai-20260930-015

"""Transport-independent supplier reads using caller-owned synchronous sessions."""

from collections.abc import Iterable, Iterator
from contextlib import contextmanager
from uuid import UUID

from sqlalchemy.exc import DBAPIError, OperationalError, TimeoutError
from sqlalchemy.orm import Session

from app.repositories.suppliers import (
    CategoryRead, SupplierPage, SupplierRead, find_active_detail, list_active_suppliers,
    list_categories as read_categories,
)
from app.validation.errors import DomainValidationError, ValidationIssue
from app.validation.vocabulary import APPROVED_AREAS


class SupplierReadUnavailable(Exception):
    """Safe public failure; database diagnostics are not part of the contract."""

    def __init__(self) -> None:
        super().__init__("Supplier details are temporarily unavailable.")


def get_supplier(session: Session, supplier_id: UUID) -> SupplierRead | None:
    """Return active details or None; leave transaction cleanup to the caller."""
    with _read_failure_boundary():
        return find_active_detail(session, supplier_id)


def list_categories(session: Session) -> tuple[CategoryRead, ...]:
    """Return all controlled category choices, including unassigned categories."""
    with _read_failure_boundary():
        return read_categories(session)


def list_areas() -> tuple[str, ...]:
    """Return immutable approved choices in declared order without database access."""
    return APPROVED_AREAS


@contextmanager
def _read_failure_boundary() -> Iterator[None]:
    try:
        yield
    except TimeoutError:
        raise SupplierReadUnavailable() from None
    except DBAPIError as error:
        state = getattr(error.orig, "sqlstate", None)
        # Class 08 is a connection failure; class 53 is resource exhaustion.
        # Psycopg connection failures can have no server SQLSTATE at all.
        unavailable = (
            error.connection_invalidated
            or (state is not None and (state.startswith(("08", "53"))
                                      or state in {"57P01", "57P02", "57P03"}))
            or (isinstance(error, OperationalError) and state is None)
        )
        if not unavailable:
            raise
        raise SupplierReadUnavailable() from None


def list_suppliers(
    session: Session, *, area: str | None = None,
    category_ids: Iterable[UUID] = (), limit: int = 20, offset: int = 0,
) -> SupplierPage:
    """Validate pagination before querying; UUID parsing belongs to adapters."""
    issues = []
    if type(limit) is not int or not 1 <= limit <= 100:
        issues.append(ValidationIssue(
            ("query.limit",), "INVALID_PAGINATION", "Limit must be an integer from 1 to 100.",
        ))
    if type(offset) is not int or offset < 0:
        issues.append(ValidationIssue(
            ("query.offset",), "INVALID_PAGINATION", "Offset must be a nonnegative integer.",
        ))
    if issues:
        raise DomainValidationError(issues)
    with _read_failure_boundary():
        return list_active_suppliers(
            session, area=area, category_ids=category_ids, limit=limit, offset=offset,
        )
