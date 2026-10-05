"""Credit outcomes and expiry are idempotent."""

from uuid import uuid4

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.events import IncomingEvent, MalformedMessage, parse_incoming
from app.models import Order, OutboxEvent, ProcessedEvent
from app.services.orders import apply_incoming, handle_delivery
from tests.helpers import COURIER_ID, insert_order


def _event(order_id, event_type, *, event_id=None, reason=None):
    return IncomingEvent(
        event_id=event_id or uuid4(),
        event_type=event_type,
        correlation_id=uuid4(),
        order_id=order_id,
        reason=reason,
    )


def _apply(api, event):
    with api["session_factory"]() as db:
        apply_incoming(db, event)
        db.commit()


def _status(api, order_id):
    with api["session_factory"]() as db:
        return db.get(Order, order_id).status


def _types(api):
    with api["session_factory"]() as db:
        return list(db.scalars(select(OutboxEvent.event_type).order_by(OutboxEvent.id)))


def test_credit_reserved_opens_a_pending_order_once(api):
    order_id = insert_order(api["session_factory"], status="PENDING_CREDIT")
    event = _event(order_id, "credit.reserved")

    _apply(api, event)
    _apply(api, event)

    assert _status(api, order_id) == "OPEN"
    assert _types(api) == ["order.opened"]
    with api["session_factory"]() as db:
        assert db.scalar(select(func.count()).select_from(ProcessedEvent)) == 1


def test_a_second_reservation_event_does_not_open_the_order_again(api):
    order_id = insert_order(api["session_factory"], status="PENDING_CREDIT")
    _apply(api, _event(order_id, "credit.reserved"))
    _apply(api, _event(order_id, "credit.reserved"))

    assert _types(api) == ["order.opened"]


def test_credit_failure_rejects_without_opening(api):
    order_id = insert_order(api["session_factory"], status="PENDING_CREDIT")

    _apply(api, _event(order_id, "credit.reservation_failed", reason="insufficient balance"))

    assert _status(api, order_id) == "REJECTED"
    with api["session_factory"]() as db:
        order = db.get(Order, order_id)
        event = db.scalars(select(OutboxEvent)).one()
        assert order.rejection_reason == "insufficient balance"
        assert event.event_type == "order.rejected"
        assert event.payload["reason"] == "insufficient balance"
    feed = api["client"].get(
        "/orders/open",
        headers={"Authorization": "Bearer user:33333333-3333-3333-3333-333333333333"},
    )
    assert feed.json()["total"] == 0


def test_credit_failure_after_open_does_not_change_the_order(api):
    order_id = insert_order(api["session_factory"], status="OPEN")

    _apply(api, _event(order_id, "credit.reservation_failed", reason="late"))

    assert _status(api, order_id) == "OPEN"
    assert _types(api) == []


def test_expiry_applies_once_and_skips_accepted_orders(api):
    open_id = insert_order(api["session_factory"], status="OPEN")
    accepted_id = insert_order(
        api["session_factory"], status="ACCEPTED", courier_id=COURIER_ID
    )
    expiry = _event(open_id, "order.created")

    _apply(api, expiry)
    _apply(api, expiry)
    _apply(api, _event(accepted_id, "order.created"))

    assert _status(api, open_id) == "EXPIRED"
    assert _status(api, accepted_id) == "ACCEPTED"
    assert _types(api) == ["order.expired"]


def test_malformed_message_is_rejected(api):
    with api["session_factory"]() as db:
        with pytest.raises(MalformedMessage):
            handle_delivery(db, b"not-json")
        assert db.scalar(select(func.count()).select_from(ProcessedEvent)) == 0


def test_unrelated_integrity_errors_are_not_treated_as_duplicates(api, monkeypatch):
    body = (
        b'{"event_id":"11111111-1111-1111-1111-111111111111",'
        b'"event_type":"credit.reserved","schema_version":1,'
        b'"occurred_at":"2026-10-05T00:00:00Z",'
        b'"correlation_id":"22222222-2222-2222-2222-222222222222",'
        b'"payload":{"order_id":"33333333-3333-3333-3333-333333333333"}}'
    )

    def fail(_db, _event):
        raise IntegrityError("INSERT", {}, Exception("ck_orders_status"))

    monkeypatch.setattr("app.services.orders.apply_incoming", fail)
    with api["session_factory"]() as db:
        with pytest.raises(IntegrityError):
            handle_delivery(db, body)


def test_parse_incoming_requires_the_v1_contract():
    body = (
        b'{"event_id":"11111111-1111-1111-1111-111111111111",'
        b'"event_type":"credit.reserved","schema_version":1,'
        b'"occurred_at":"2026-10-05T00:00:00Z",'
        b'"correlation_id":"22222222-2222-2222-2222-222222222222",'
        b'"payload":{"order_id":"33333333-3333-3333-3333-333333333333"}}'
    )
    parsed = parse_incoming(body)
    assert parsed.event_type == "credit.reserved"

    broken = body.replace(b'"schema_version":1', b'"schema_version":2')
    with pytest.raises(MalformedMessage):
        parse_incoming(broken)

