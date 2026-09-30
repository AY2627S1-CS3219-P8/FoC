# AI Assistance Disclosure:
# Tool: Codex (model: GPT-6), date: 2026-09-30
# Scope: Writing implementation code — implement category resolution, active/deleted UUID lookup, and PostgreSQL index-aligned active-duplicate queries with autoflush disabled.
# Scope: Writing implementation code; Refactoring and documentation improvements — add supplier and category-assignment insertion helpers using bound longitude-first SRID 4326 points, normalized values, aware timestamps, version 1, and null deletion state while leaving transaction ownership in the service.
# Author review: Keith confirmed review of all affected changes.
# Details: ../../ai/usage-log.md; ai-20260930-009; ai-20260930-010

"""Supplier queries and inserts; transaction ownership stays with the service."""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from geoalchemy2 import Geography
from sqlalchemy import cast, func, insert, literal_column, select
from sqlalchemy.orm import Session

from app.models import Category, Supplier, supplier_category
from app.schemas import SupplierSeedResult


# Keep these expressions aligned with uq_supplier_active_name_location.
_LONGITUDE = func.ST_X(literal_column("location::geometry"))
_LATITUDE = func.ST_Y(literal_column("location::geometry"))


def normalized_name(expression):
    """PostgreSQL normalization used by the active duplicate index."""
    return func.lower(func.btrim(expression))


@dataclass(frozen=True)
class SupplierIdentity:
    supplier_id: UUID
    longitude: float
    latitude: float


def resolve_category_ids(session: Session, names: Iterable[str]) -> dict[str, UUID]:
    """Return existing controlled definitions; absent names remain absent."""
    with session.no_autoflush:
        return dict(session.execute(
            select(Category.name, Category.id).where(Category.name.in_(tuple(names)))
        ).all())


def find_identity(session: Session, supplier_id: UUID) -> SupplierIdentity | None:
    """Find immutable coordinates, including for deleted identities."""
    with session.no_autoflush:
        row = session.execute(select(Supplier.id, _LONGITUDE, _LATITUDE).where(
            Supplier.id == supplier_id
        )).one_or_none()
    return SupplierIdentity(*row) if row is not None else None


def duplicate_key(session: Session, name: str, longitude: float, latitude: float):
    """Normalize batch candidates in the database, using its case/space rules."""
    with session.no_autoflush:
        name = session.scalar(select(normalized_name(name)))
    return name, float(longitude), float(latitude)


def find_active_duplicates(
    session: Session, name: str, longitude: float, latitude: float,
) -> tuple[UUID, ...]:
    """Match the partial unique index exactly, without proximity or rounding."""
    with session.no_autoflush:
        return tuple(session.scalars(select(Supplier.id).where(
            Supplier.deleted_at.is_(None),
            normalized_name(Supplier.name) == normalized_name(name),
            _LONGITUDE == float(longitude),
            _LATITUDE == float(latitude),
        ).order_by(Supplier.id)))


def insert_supplier(
    session: Session, supplier_id: UUID, values: SupplierSeedResult,
    timestamp: datetime,
) -> None:
    """Insert a new identity with bound longitude/latitude, never an upsert."""
    scalars = values.model_dump(exclude={"location"})
    point = cast(func.ST_SetSRID(func.ST_MakePoint(
        float(values.location.longitude), float(values.location.latitude),
    ), 4326), Geography(geometry_type="POINT", srid=4326))
    session.execute(insert(Supplier.__table__).values(
        **scalars, id=supplier_id, location=point,
        created_at=timestamp, updated_at=timestamp, version=1, deleted_at=None,
    ))


def insert_category_assignments(
    session: Session, supplier_id: UUID, category_ids: tuple[UUID, ...],
) -> None:
    """Insert all resolved assignments in the service's existing transaction."""
    if category_ids:
        session.execute(insert(supplier_category), [
            {"supplier_id": supplier_id, "category_id": category_id}
            for category_id in category_ids
        ])
