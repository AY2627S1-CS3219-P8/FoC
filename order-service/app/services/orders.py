"""Business logic for errand requests and incoming credit or expiry messages."""

import hashlib
import json
import logging
from dataclasses import dataclass
from uuid import UUID, uuid4

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from app.clients import Identity, SupplierServiceClient, SupplierUnavailableError
from app.events import IncomingEvent, enqueue_event, isoformat_utc, parse_incoming
from app.messaging import ORDER_TTL
from app.models import Order, ProcessedEvent, utc_now
from app.schemas import DeliveryLocation, OrderCreate

logger = logging.getLogger(__name__)

# Western edge includes the seeded Engineering stores (Cheers at E3 is 103.753).
# Northern edge includes University Town, which the old box cut off.
NUS_CAMPUS_BOUNDS = {
    "min_latitude": 1.288,
    "max_latitude": 1.310,
    "min_longitude": 103.750,
    "max_longitude": 103.788,
}

TERMINAL_STATUSES = frozenset({"COMPLETED", "CANCELLED", "EXPIRED", "REJECTED"})
REQUESTER_CANCELLABLE = frozenset({"PENDING_CREDIT", "OPEN", "ACCEPTED"})
DESTINATION_MUTABLE = frozenset({"PENDING_CREDIT", "OPEN", "ACCEPTED"})
EXPIRABLE = frozenset({"PENDING_CREDIT", "OPEN"})


@dataclass(frozen=True)
class CreateOrderResult:
    """Outcome of an order creation attempt."""

    order: Order
    created: bool


def hash_request(payload: OrderCreate) -> str:
    """Return a stable hash for idempotent replay comparisons."""

    encoded = json.dumps(
        payload.model_dump(mode="json"), sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def delivery_within_campus(latitude: float, longitude: float) -> bool:
    """Return whether the delivery coordinates fall within the supported campus."""

    return (
        NUS_CAMPUS_BOUNDS["min_latitude"] <= latitude <= NUS_CAMPUS_BOUNDS["max_latitude"]
        and NUS_CAMPUS_BOUNDS["min_longitude"]
        <= longitude
        <= NUS_CAMPUS_BOUNDS["max_longitude"]
    )


def normalize_idempotency_key(value: str) -> str:
    key = value.strip()
    if not key:
        raise HTTPException(status_code=422, detail="Idempotency-Key must not be blank")
    if len(key) > 128:
        raise HTTPException(
            status_code=422, detail="Idempotency-Key must be at most 128 characters"
        )
    return key


def parse_correlation_id(value: str | None) -> UUID:
    if value is None or not value.strip():
        return uuid4()
    try:
        return UUID(value.strip())
    except ValueError:
        raise HTTPException(status_code=422, detail="X-Correlation-ID must be a UUID") from None


def create_order(
    payload: OrderCreate,
    requester: Identity,
    idempotency_key: str,
    correlation_id: UUID,
    db: Session,
    supplier_directory: SupplierServiceClient,
) -> CreateOrderResult:
    """Create an errand request or replay an idempotent submission."""

    request_hash = hash_request(payload)
    existing = _find_existing(db, requester.id, idempotency_key)
    if existing is not None:
        return _replay(existing, request_hash)

    _require_active_supplier(supplier_directory, payload.pickup_supplier_id)
    if not delivery_within_campus(payload.delivery.latitude, payload.delivery.longitude):
        raise HTTPException(status_code=422, detail="Delivery location is not supported")

    now = utc_now()
    order = Order(
        requester_id=requester.id,
        pickup_supplier_id=payload.pickup_supplier_id,
        delivery_label=payload.delivery.label,
        delivery_latitude=payload.delivery.latitude,
        delivery_longitude=payload.delivery.longitude,
        delivery_details=payload.delivery.details,
        item_description=payload.item_description,
        credit_amount=payload.credit_amount,
        status="PENDING_CREDIT",
        idempotency_key=idempotency_key,
        request_hash=request_hash,
        correlation_id=correlation_id,
        expires_at=now + ORDER_TTL,
        created_at=now,
        updated_at=now,
    )
    db.add(order)
    db.flush()
    enqueue_event(
        db,
        event_type="order.created",
        order=order,
        correlation_id=correlation_id,
        extra={"expires_at": isoformat_utc(order.expires_at)},
    )
    try:
        _commit(db)
    except IntegrityError as exc:
        db.rollback()
        replay = _find_existing(db, requester.id, idempotency_key)
        if replay is None:
            raise HTTPException(
                status_code=503, detail="Database temporarily unavailable"
            ) from exc
        return _replay(replay, request_hash)
    db.refresh(order)
    return CreateOrderResult(order=order, created=True)


def list_open_orders(
    db: Session, actor: Identity, *, limit: int, offset: int
) -> tuple[list[Order], int]:
    """Open errands other people can accept. Pending credit stays hidden."""

    filters = (Order.status == "OPEN", Order.requester_id != actor.id)
    return _page(db, filters, limit=limit, offset=offset)


def list_my_orders(
    db: Session, actor: Identity, *, role: str, limit: int, offset: int
) -> tuple[list[Order], int]:
    if role == "requester":
        filters = (Order.requester_id == actor.id,)
    else:
        filters = (Order.courier_id == actor.id,)
    return _page(db, filters, limit=limit, offset=offset)


def get_order(db: Session, order_id: UUID, actor: Identity) -> Order:
    order = db.get(Order, order_id)
    if order is None or not _can_view(order, actor):
        raise HTTPException(status_code=404, detail="Order not found")
    return order


def change_delivery(
    db: Session, order_id: UUID, actor: Identity, delivery: DeliveryLocation
) -> Order:
    order = _lock_visible(db, order_id, actor)
    if order.requester_id != actor.id:
        raise HTTPException(
            status_code=403,
            detail="Only the requester can change the delivery destination",
        )
    if order.status not in DESTINATION_MUTABLE:
        _illegal(order, "change the destination of")
    if not delivery_within_campus(delivery.latitude, delivery.longitude):
        raise HTTPException(status_code=422, detail="Delivery location is not supported")
    order.delivery_label = delivery.label
    order.delivery_latitude = delivery.latitude
    order.delivery_longitude = delivery.longitude
    order.delivery_details = delivery.details
    order.updated_at = utc_now()
    _commit(db)
    db.refresh(order)
    return order


def accept_order(db: Session, order_id: UUID, actor: Identity) -> Order:
    order = _lock(db, order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="Order not found")
    if actor.id == order.requester_id:
        raise HTTPException(
            status_code=403, detail="The requester cannot accept their own order"
        )
    if order.status == "ACCEPTED" and order.courier_id == actor.id:
        return order
    # A competing courier already saw this errand in the open feed. 409 tells
    # them they lost, which a 404 would hide.
    if order.status == "ACCEPTED":
        _illegal(order, "accept")
    if order.status != "OPEN":
        if not _can_view(order, actor):
            raise HTTPException(status_code=404, detail="Order not found")
        _illegal(order, "accept")
    now = utc_now()
    order.status = "ACCEPTED"
    order.courier_id = actor.id
    order.accepted_at = now
    order.updated_at = now
    enqueue_event(
        db, event_type="order.accepted", order=order, correlation_id=order.correlation_id
    )
    _commit(db)
    db.refresh(order)
    return order


def pick_up_order(db: Session, order_id: UUID, actor: Identity) -> Order:
    order = _lock_visible(db, order_id, actor)
    if order.status == "PICKED_UP" and order.courier_id == actor.id:
        return order
    if order.courier_id != actor.id:
        raise HTTPException(
            status_code=403, detail="Only the assigned courier can pick up this order"
        )
    if order.status != "ACCEPTED":
        _illegal(order, "pick up")
    now = utc_now()
    order.status = "PICKED_UP"
    order.picked_up_at = now
    order.updated_at = now
    enqueue_event(
        db, event_type="order.picked_up", order=order, correlation_id=order.correlation_id
    )
    _commit(db)
    db.refresh(order)
    return order


def complete_order(db: Session, order_id: UUID, actor: Identity) -> Order:
    order = _lock_visible(db, order_id, actor)
    if order.status == "COMPLETED" and order.requester_id == actor.id:
        return order
    if order.requester_id != actor.id:
        raise HTTPException(
            status_code=403, detail="Only the requester can complete this order"
        )
    if order.status != "PICKED_UP":
        _illegal(order, "complete")
    now = utc_now()
    order.status = "COMPLETED"
    order.completed_at = now
    order.updated_at = now
    enqueue_event(
        db, event_type="order.completed", order=order, correlation_id=order.correlation_id
    )
    _commit(db)
    db.refresh(order)
    return order


def cancel_order(db: Session, order_id: UUID, actor: Identity) -> Order:
    order = _lock_visible(db, order_id, actor)
    if order.status == "CANCELLED" and order.cancelled_by == actor.id:
        return order
    if order.status in TERMINAL_STATUSES:
        _illegal(order, "cancel")
    requester_may = (
        actor.id == order.requester_id and order.status in REQUESTER_CANCELLABLE
    )
    if not requester_may and actor.role != "admin":
        if actor.id == order.requester_id and order.status == "PICKED_UP":
            raise HTTPException(
                status_code=403,
                detail="An order can only be cancelled before it is picked up",
            )
        raise HTTPException(status_code=403, detail="You cannot cancel this order")
    previous_status = order.status
    now = utc_now()
    order.status = "CANCELLED"
    order.cancelled_at = now
    order.cancelled_by = actor.id
    order.updated_at = now
    enqueue_event(
        db,
        event_type="order.cancelled",
        order=order,
        correlation_id=order.correlation_id,
        extra={"cancelled_by": str(actor.id), "previous_status": previous_status},
    )
    _commit(db)
    db.refresh(order)
    return order


def apply_incoming(db: Session, event: IncomingEvent) -> None:
    """Apply one credit or expiry message. Repeated event ids do nothing."""

    if db.get(ProcessedEvent, event.event_id) is not None:
        return
    order = db.scalar(select(Order).where(Order.id == event.order_id).with_for_update())
    if order is not None:
        if event.event_type == "credit.reserved":
            _mark_open(db, order)
        elif event.event_type == "credit.reservation_failed":
            _mark_rejected(db, order, event.reason)
        elif event.event_type == "order.created":
            _mark_expired(db, order)
    db.add(ProcessedEvent(event_id=event.event_id, processed_at=utc_now()))


def handle_delivery(db: Session, body: bytes) -> None:
    """Parse and apply one message, committing the result."""

    event = parse_incoming(body)
    try:
        apply_incoming(db, event)
        _commit(db)
    except IntegrityError as exc:
        db.rollback()
        if not _is_duplicate_processed_event(exc):
            raise


def _is_duplicate_processed_event(exc: IntegrityError) -> bool:
    """True only when this event id was already recorded. Other constraint failures must retry."""

    orig = exc.orig
    constraint = getattr(getattr(orig, "diag", None), "constraint_name", None)
    if constraint == "processed_events_pkey":
        return True
    return "processed_events" in str(orig).lower() and "unique" in str(orig).lower()


def _mark_open(db: Session, order: Order) -> None:
    if order.status != "PENDING_CREDIT":
        return
    order.status = "OPEN"
    order.updated_at = utc_now()
    enqueue_event(
        db, event_type="order.opened", order=order, correlation_id=order.correlation_id
    )


def _mark_rejected(db: Session, order: Order, reason: str | None) -> None:
    if order.status != "PENDING_CREDIT":
        return
    order.status = "REJECTED"
    order.rejection_reason = (reason or "insufficient balance")[:500]
    order.updated_at = utc_now()
    enqueue_event(
        db,
        event_type="order.rejected",
        order=order,
        correlation_id=order.correlation_id,
        extra={"reason": order.rejection_reason},
    )


def _mark_expired(db: Session, order: Order) -> None:
    if order.status not in EXPIRABLE:
        return
    now = utc_now()
    order.status = "EXPIRED"
    order.expired_at = now
    order.updated_at = now
    enqueue_event(
        db, event_type="order.expired", order=order, correlation_id=order.correlation_id
    )


def _page(
    db: Session, filters: tuple, *, limit: int, offset: int
) -> tuple[list[Order], int]:
    total = db.scalar(select(func.count()).select_from(Order).where(*filters)) or 0
    items = list(
        db.scalars(
            select(Order)
            .where(*filters)
            .order_by(Order.created_at.desc(), Order.id.desc())
            .limit(limit)
            .offset(offset)
        )
    )
    return items, total


def _find_existing(db: Session, requester_id: UUID, idempotency_key: str) -> Order | None:
    try:
        return db.scalar(
            select(Order).where(
                Order.requester_id == requester_id,
                Order.idempotency_key == idempotency_key,
            )
        )
    except OperationalError:
        db.rollback()
        raise


def _replay(existing: Order, request_hash: str) -> CreateOrderResult:
    if existing.request_hash != request_hash:
        raise HTTPException(
            status_code=409, detail="Idempotency key reused with different request"
        )
    return CreateOrderResult(order=existing, created=False)


def _require_active_supplier(
    supplier_directory: SupplierServiceClient, supplier_id: UUID
) -> None:
    try:
        active = supplier_directory.is_active(supplier_id)
    except SupplierUnavailableError:
        raise HTTPException(
            status_code=503, detail="Pickup locations are temporarily unavailable"
        ) from None
    if not active:
        raise HTTPException(status_code=422, detail="Pickup location is not supported")


def _lock(db: Session, order_id: UUID) -> Order | None:
    return db.scalar(select(Order).where(Order.id == order_id).with_for_update())


def _lock_visible(db: Session, order_id: UUID, actor: Identity) -> Order:
    order = _lock(db, order_id)
    if order is None or not _can_view(order, actor):
        raise HTTPException(status_code=404, detail="Order not found")
    return order


def _can_view(order: Order, actor: Identity) -> bool:
    return (
        actor.role == "admin"
        or actor.id == order.requester_id
        or actor.id == order.courier_id
    )


def _illegal(order: Order, action: str) -> None:
    logger.warning(
        "illegal_order_transition order_id=%s status=%s action=%s",
        order.id,
        order.status,
        action,
    )
    raise HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail=f"Cannot {action} an order with status {order.status}",
    )


def _commit(db: Session) -> None:
    try:
        db.commit()
    except OperationalError:
        db.rollback()
        raise
