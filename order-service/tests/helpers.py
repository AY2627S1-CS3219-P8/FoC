"""Test doubles and request builders."""

from datetime import datetime, timezone
from uuid import UUID, uuid4

from app.clients import Identity, InvalidSessionError, SupplierUnavailableError
from app.messaging import ORDER_TTL
from app.models import Order

REQUESTER_ID = UUID("11111111-1111-1111-1111-111111111111")
COURIER_ID = UUID("22222222-2222-2222-2222-222222222222")
OTHER_ID = UUID("33333333-3333-3333-3333-333333333333")
ADMIN_ID = UUID("44444444-4444-4444-4444-444444444444")
SUPPLIER_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")

ACTORS = {
    "requester": (REQUESTER_ID, "user"),
    "courier": (COURIER_ID, "user"),
    "other": (OTHER_ID, "user"),
    "admin": (ADMIN_ID, "admin"),
}


class FakeUserClient:
    def resolve_identity(self, token: str) -> Identity:
        kind, separator, raw = token.partition(":")
        if separator != ":" or kind not in {"user", "admin"}:
            raise InvalidSessionError
        try:
            user_id = UUID(raw)
        except ValueError:
            raise InvalidSessionError from None
        return Identity(id=user_id, role=kind, status="active")

    def close(self) -> None:
        return None


class FakeSupplierClient:
    def __init__(self, known: set[UUID]):
        self.known = known
        self.unavailable = False

    def is_active(self, supplier_id: UUID) -> bool:
        if self.unavailable:
            raise SupplierUnavailableError
        return supplier_id in self.known

    def close(self) -> None:
        return None


def auth_headers(user_id=REQUESTER_ID, role="user", **extra):
    headers = {"Authorization": f"Bearer {role}:{user_id}"}
    headers.update(extra)
    return headers


def order_headers(user_id=REQUESTER_ID, idempotency_key="create-order-1", **extra):
    return auth_headers(
        user_id,
        **{"Idempotency-Key": idempotency_key, **extra},
    )


def valid_payload(**overrides):
    payload = {
        "pickup_supplier_id": str(SUPPLIER_ID),
        "delivery": {
            "label": "PGP Tower",
            "latitude": 1.291,
            "longitude": 103.777,
            "details": "Leave at the lobby reception",
        },
        "item_description": "Two packets of instant noodles",
        "credit_amount": 5,
    }
    payload.update(overrides)
    return payload


def insert_order(session_factory, *, status, requester_id=REQUESTER_ID, courier_id=None, cancelled_by=None):
    now = datetime.now(timezone.utc)
    order = Order(
        requester_id=requester_id,
        pickup_supplier_id=SUPPLIER_ID,
        delivery_label="PGP Tower",
        delivery_latitude=1.291,
        delivery_longitude=103.777,
        delivery_details="Leave at the lobby reception",
        item_description="Two packets of instant noodles",
        credit_amount=5,
        status=status,
        idempotency_key=uuid4().hex,
        request_hash="seed",
        courier_id=courier_id,
        cancelled_by=cancelled_by,
        accepted_at=now if courier_id is not None else None,
        picked_up_at=now if status in {"PICKED_UP", "COMPLETED"} else None,
        completed_at=now if status == "COMPLETED" else None,
        cancelled_at=now if status == "CANCELLED" else None,
        expired_at=now if status == "EXPIRED" else None,
        correlation_id=uuid4(),
        expires_at=now + ORDER_TTL,
        created_at=now,
        updated_at=now,
    )
    with session_factory() as db:
        db.add(order)
        db.commit()
        db.refresh(order)
        return order.id
