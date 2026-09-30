# AI Assistance Disclosure:
# Tool: Codex (model: GPT-6), date: 2026-09-30
# Scope: Writing implementation code — implement category resolution, active/deleted UUID lookup, and PostgreSQL index-aligned active-duplicate queries with autoflush disabled.
# Scope: Writing implementation code; Refactoring and documentation improvements — add supplier and category-assignment insertion helpers using bound longitude-first SRID 4326 points, normalized values, aware timestamps, version 1, and null deletion state while leaving transaction ownership in the service.
# Scope: Writing implementation code; Refactoring and documentation improvements — implement active-only detail lookup, immutable supplier/category values, named PostGIS coordinates, and eager categories with caller-owned transactions. (ai-20260930-013)
# Scope: Writing implementation code; Refactoring and documentation improvements — implement active filtered pages and matching totals with name/UUID ordering, and share coordinate projection, select-in categories, and immutable mapping with detail reads. (ai-20260930-014)
# Scope: Writing implementation code; Refactoring and documentation improvements — implement direct ordered category ID/name retrieval as immutable values, independent of supplier assignments and without autoflush. (ai-20260930-015)
# Author review: Keith confirmed review of all affected changes.
# Details: ../../ai/usage-log.md; ai-20260930-009; ai-20260930-010; ai-20260930-013; ai-20260930-014; ai-20260930-015

"""Supplier queries and inserts; transaction ownership stays with the service."""

from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime, time
from uuid import UUID

from geoalchemy2 import Geography, Geometry
from sqlalchemy import cast, func, insert, literal_column, select
from sqlalchemy.orm import Session, selectinload

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


@dataclass(frozen=True)
class CategoryRead:
    id: UUID
    name: str


@dataclass(frozen=True)
class SupplierRead:
    """Detached detail value; accessing fields never requires a session."""

    id: UUID
    name: str
    area: str
    description: str | None
    building: str | None
    floor: str | None
    image_key: str | None
    opening_time: time | None
    closing_time: time | None
    closing_day_offset: int | None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None
    version: int
    latitude: float
    longitude: float
    categories: tuple[CategoryRead, ...]


@dataclass(frozen=True)
class SupplierPage:
    items: tuple[SupplierRead, ...]
    total: int
    limit: int
    offset: int


def _read_statement():
    """Project coordinates together with suppliers and batch-load categories."""
    point = cast(Supplier.location, Geometry("POINT", srid=4326))
    return select(
        Supplier,
        func.ST_Y(point).label("latitude"),
        func.ST_X(point).label("longitude"),
    ).options(selectinload(Supplier.categories))


def _read_value(supplier: Supplier, latitude: float, longitude: float) -> SupplierRead:
    return SupplierRead(
        id=supplier.id, name=supplier.name, area=supplier.area,
        description=supplier.description, building=supplier.building,
        floor=supplier.floor, image_key=supplier.image_key,
        opening_time=supplier.opening_time, closing_time=supplier.closing_time,
        closing_day_offset=supplier.closing_day_offset,
        created_at=supplier.created_at, updated_at=supplier.updated_at,
        deleted_at=supplier.deleted_at, version=supplier.version,
        latitude=latitude, longitude=longitude,
        categories=tuple(sorted(
            (CategoryRead(category.id, category.name) for category in supplier.categories),
            key=lambda category: (category.name, category.id),
        )),
    )


def find_active_detail(session: Session, supplier_id: UUID) -> SupplierRead | None:
    """Read an active identity without flushing or owning the transaction."""
    statement = _read_statement().where(
        Supplier.id == supplier_id, Supplier.deleted_at.is_(None),
    )
    with session.no_autoflush:
        row = session.execute(statement).one_or_none()
        return _read_value(*row) if row is not None else None


def list_active_suppliers(
    session: Session, *, area: str | None = None,
    category_ids: Iterable[UUID] = (), limit: int, offset: int,
) -> SupplierPage:
    """Count and page identical predicates; pagination is validated by the service."""
    predicates = [Supplier.deleted_at.is_(None)]
    if area is not None:
        predicates.append(Supplier.area == area)
    selected = tuple(set(category_ids))
    if selected:
        predicates.append(Supplier.categories.any(Category.id.in_(selected)))
    statement = _read_statement().where(*predicates).order_by(
        Supplier.name, Supplier.id,
    ).offset(offset).limit(limit)
    with session.no_autoflush:
        total = session.scalar(select(func.count()).select_from(Supplier).where(*predicates))
        items = tuple(_read_value(*row) for row in session.execute(statement))
    return SupplierPage(items=items, total=total, limit=limit, offset=offset)


def list_categories(session: Session) -> tuple[CategoryRead, ...]:
    """Read all migration-managed choices, independent of supplier assignments."""
    with session.no_autoflush:
        return tuple(CategoryRead(*row) for row in session.execute(
            select(Category.id, Category.name).order_by(Category.name, Category.id)
        ))


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
