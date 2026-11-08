"""Courier cancellation and the order status history."""

import json
from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Order, OrderStatusHistory, OutboxEvent
from app.services.orders import expire_overdue_orders, handle_delivery


SUPPLIER_ID = "11111111-1111-4111-8111-111111111111"
DELIVERY = {
    "label": "COM1 Level 2",
    "latitude": 1.295,
    "longitude": 103.773,
    "details": "Outside the lobby",
}


def _auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def _create(client, token: str, key: str | None = None) -> dict:
    response = client.post(
        "/orders",
        headers={**_auth(token), "Idempotency-Key": key or str(uuid4())},
        json={
            "pickup_supplier_id": SUPPLIER_ID,
            "delivery": DELIVERY,
            "item_description": "kopi",
            "credit_amount": 8,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def _reserve(session_factory, order_id: str) -> None:
    body = json.dumps(
        {
            "event_id": str(uuid4()),
            "event_type": "credit.reserved",
            "schema_version": 1,
            "occurred_at": "2026-11-08T07:00:00Z",
            "correlation_id": str(uuid4()),
            "payload": {"order_id": order_id},
        }
    ).encode()
    db = session_factory()
    try:
        handle_delivery(db, body)
    finally:
        db.close()


def _reject(session_factory, order_id: str) -> None:
    body = json.dumps(
        {
            "event_id": str(uuid4()),
            "event_type": "credit.reservation_failed",
            "schema_version": 1,
            "occurred_at": "2026-11-08T07:00:00Z",
            "correlation_id": str(uuid4()),
            "payload": {"order_id": order_id, "reason": "insufficient balance"},
        }
    ).encode()
    db = session_factory()
    try:
        handle_delivery(db, body)
    finally:
        db.close()


def _events(db: Session, order_id: UUID, event_type: str) -> list[OutboxEvent]:
    return list(
        db.scalars(
            select(OutboxEvent)
            .where(OutboxEvent.order_id == order_id, OutboxEvent.event_type == event_type)
            .order_by(OutboxEvent.id)
        )
    )


def _history(db: Session, order_id: UUID) -> list[OrderStatusHistory]:
    return list(
        db.scalars(
            select(OrderStatusHistory)
            .where(OrderStatusHistory.order_id == order_id)
            .order_by(OrderStatusHistory.id)
        )
    )


def _open_and_accept(client, session_factory, directory):
    requester_token, _requester = directory.add()
    courier_token, courier = directory.add()
    created = _create(client, requester_token)
    order_id = created["id"]
    _reserve(session_factory, order_id)
    accepted = client.post(f"/orders/{order_id}/accept", headers=_auth(courier_token))
    assert accepted.status_code == 200, accepted.text
    return requester_token, courier_token, courier, order_id


def test_courier_cancel_before_pickup_reopens_the_order(client, directory, session_factory):
    requester_token, courier_token, courier, order_id = _open_and_accept(
        client, session_factory, directory
    )
    before = client.get(f"/orders/{order_id}", headers=_auth(requester_token)).json()

    cancelled = client.post(f"/orders/{order_id}/cancel", headers=_auth(courier_token))

    assert cancelled.status_code == 200, cancelled.text
    body = cancelled.json()
    assert body["status"] == "OPEN"
    assert body["courier_id"] is None
    assert body["accepted_at"] is None
    assert body["expires_at"] >= before["expires_at"]
    renewed = datetime.fromisoformat(body["expires_at"])
    if renewed.tzinfo is None:
        renewed = renewed.replace(tzinfo=timezone.utc)
    assert renewed > datetime.now(timezone.utc) + timedelta(minutes=59)

    db = session_factory()
    try:
        events = _events(db, UUID(order_id), "order.reopened")
        assert len(events) == 1
        assert events[0].payload["previous_status"] == "ACCEPTED"
        assert events[0].payload["previous_courier_id"] == str(courier.id)
        assert events[0].payload["reason"] == "courier_cancelled"
        assert "courier_id" not in events[0].payload
        assert _events(db, UUID(order_id), "order.cancelled") == []
    finally:
        db.close()

    listed = client.get("/orders/open", headers=_auth(courier_token))
    assert listed.status_code == 200
    assert order_id in {item["id"] for item in listed.json()["items"]}


def test_courier_cancel_after_pickup_reopens_without_paying_the_courier(
    client, directory, session_factory
):
    _requester_token, courier_token, courier, order_id = _open_and_accept(
        client, session_factory, directory
    )
    picked = client.post(f"/orders/{order_id}/pickup", headers=_auth(courier_token))
    assert picked.status_code == 200, picked.text

    cancelled = client.post(f"/orders/{order_id}/cancel", headers=_auth(courier_token))

    assert cancelled.status_code == 200, cancelled.text
    body = cancelled.json()
    assert body["status"] == "OPEN"
    assert body["courier_id"] is None
    assert body["accepted_at"] is None
    assert body["picked_up_at"] is None

    db = session_factory()
    try:
        events = _events(db, UUID(order_id), "order.reopened")
        assert len(events) == 1
        assert events[0].payload["previous_status"] == "PICKED_UP"
        assert events[0].payload["previous_courier_id"] == str(courier.id)
        assert _events(db, UUID(order_id), "order.cancelled") == []
    finally:
        db.close()


def test_repeating_a_courier_cancel_writes_nothing_else(client, directory, session_factory):
    _requester_token, courier_token, _courier, order_id = _open_and_accept(
        client, session_factory, directory
    )
    first = client.post(f"/orders/{order_id}/cancel", headers=_auth(courier_token))
    assert first.status_code == 200, first.text

    second = client.post(f"/orders/{order_id}/cancel", headers=_auth(courier_token))

    assert second.status_code == 200, second.text
    assert second.json()["status"] == "OPEN"
    db = session_factory()
    try:
        assert len(_events(db, UUID(order_id), "order.reopened")) == 1
        reasons = [row.reason for row in _history(db, UUID(order_id))]
        assert reasons.count("courier_cancelled") == 1
    finally:
        db.close()


def test_other_people_cannot_cancel_for_the_courier(client, directory, session_factory):
    requester_token, courier_token, _courier, order_id = _open_and_accept(
        client, session_factory, directory
    )
    stranger_token, _stranger = directory.add()
    missing = client.post(f"/orders/{order_id}/cancel", headers=_auth(stranger_token))
    assert missing.status_code == 404

    picked = client.post(f"/orders/{order_id}/pickup", headers=_auth(courier_token))
    assert picked.status_code == 200, picked.text
    requester = client.post(f"/orders/{order_id}/cancel", headers=_auth(requester_token))
    assert requester.status_code == 403
    assert requester.json()["detail"] == "An order can only be cancelled before it is picked up"


def test_requester_cancel_still_cancels(client, directory, session_factory):
    requester_token, _courier_token, _courier, order_id = _open_and_accept(
        client, session_factory, directory
    )

    cancelled = client.post(f"/orders/{order_id}/cancel", headers=_auth(requester_token))

    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["status"] == "CANCELLED"
    db = session_factory()
    try:
        assert len(_events(db, UUID(order_id), "order.cancelled")) == 1
        assert _events(db, UUID(order_id), "order.reopened") == []
        assert _history(db, UUID(order_id))[-1].reason == "cancelled"
    finally:
        db.close()


def test_admin_cancel_after_pickup_still_cancels(client, directory, session_factory):
    _requester_token, courier_token, courier, order_id = _open_and_accept(
        client, session_factory, directory
    )
    assert client.post(f"/orders/{order_id}/pickup", headers=_auth(courier_token)).status_code == 200
    admin_token, admin = directory.add(role="admin")

    cancelled = client.post(f"/orders/{order_id}/cancel", headers=_auth(admin_token))

    assert cancelled.status_code == 200, cancelled.text
    body = cancelled.json()
    assert body["status"] == "CANCELLED"
    assert body["cancelled_by"] == str(admin.id)
    assert body["courier_id"] == str(courier.id)
    db = session_factory()
    try:
        events = _events(db, UUID(order_id), "order.cancelled")
        assert len(events) == 1
        assert events[0].payload["previous_status"] == "PICKED_UP"
        assert _events(db, UUID(order_id), "order.reopened") == []
    finally:
        db.close()


def test_another_courier_can_accept_a_reopened_order(client, directory, session_factory):
    _requester_token, courier_token, first, order_id = _open_and_accept(
        client, session_factory, directory
    )
    assert client.post(f"/orders/{order_id}/pickup", headers=_auth(courier_token)).status_code == 200
    assert client.post(f"/orders/{order_id}/cancel", headers=_auth(courier_token)).status_code == 200
    second_token, second = directory.add()

    accepted = client.post(f"/orders/{order_id}/accept", headers=_auth(second_token))

    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["status"] == "ACCEPTED"
    assert accepted.json()["courier_id"] == str(second.id)
    assert accepted.json()["courier_id"] != str(first.id)


def test_history_follows_the_lifecycle_and_is_visible_to_participants(
    client, directory, session_factory
):
    requester_token, requester = directory.add()
    courier_token, courier = directory.add()
    created = _create(client, requester_token)
    order_id = created["id"]
    _reserve(session_factory, order_id)
    assert client.post(f"/orders/{order_id}/accept", headers=_auth(courier_token)).status_code == 200
    assert client.post(f"/orders/{order_id}/pickup", headers=_auth(courier_token)).status_code == 200
    assert client.post(f"/orders/{order_id}/cancel", headers=_auth(courier_token)).status_code == 200
    second_token, second = directory.add()
    assert client.post(f"/orders/{order_id}/accept", headers=_auth(second_token)).status_code == 200
    assert client.post(f"/orders/{order_id}/pickup", headers=_auth(second_token)).status_code == 200
    completed = client.post(f"/orders/{order_id}/complete", headers=_auth(requester_token))
    assert completed.status_code == 200, completed.text

    visible = client.get(f"/orders/{order_id}/history", headers=_auth(requester_token))
    assert visible.status_code == 200, visible.text
    rows = visible.json()
    assert [(row["from_status"], row["to_status"], row["reason"]) for row in rows] == [
        (None, "PENDING_CREDIT", "created"),
        ("PENDING_CREDIT", "OPEN", "credit_reserved"),
        ("OPEN", "ACCEPTED", "accepted"),
        ("ACCEPTED", "PICKED_UP", "picked_up"),
        ("PICKED_UP", "OPEN", "courier_cancelled"),
        ("OPEN", "ACCEPTED", "accepted"),
        ("ACCEPTED", "PICKED_UP", "picked_up"),
        ("PICKED_UP", "COMPLETED", "completed"),
    ]
    assert rows[0]["actor_id"] == str(requester.id)
    assert rows[1]["actor_id"] is None
    assert rows[2]["actor_id"] == str(courier.id)
    assert rows[4]["actor_id"] == str(courier.id)
    assert rows[5]["actor_id"] == str(second.id)
    assert rows[7]["actor_id"] == str(requester.id)

    assert client.get(f"/orders/{order_id}/history", headers=_auth(second_token)).status_code == 200
    admin_token, _admin = directory.add(role="admin")
    assert client.get(f"/orders/{order_id}/history", headers=_auth(admin_token)).status_code == 200
    stranger_token, _stranger = directory.add()
    assert client.get(f"/orders/{order_id}/history", headers=_auth(stranger_token)).status_code == 404
    former = client.get(f"/orders/{order_id}/history", headers=_auth(courier_token))
    assert former.status_code == 404


def test_expiry_and_rejection_record_history_without_an_actor(
    client, directory, session_factory
):
    token, requester = directory.add()
    created = _create(client, token)
    order_id = UUID(created["id"])
    _reserve(session_factory, str(order_id))
    db = session_factory()
    try:
        order = db.get(Order, order_id)
        assert order is not None
        order.expires_at = datetime.now(timezone.utc) - timedelta(seconds=5)
        db.commit()
        assert expire_overdue_orders(db) == 1
        rows = _history(db, order_id)
    finally:
        db.close()

    assert [(row.to_status, row.actor_id, row.reason) for row in rows] == [
        ("PENDING_CREDIT", requester.id, "created"),
        ("OPEN", None, "credit_reserved"),
        ("EXPIRED", None, "expired"),
    ]

    rejected = _create(client, token, key="reject-me")
    rejected_id = UUID(rejected["id"])
    _reject(session_factory, str(rejected_id))
    db = session_factory()
    try:
        rows = _history(db, rejected_id)
        stored = db.get(Order, rejected_id)
    finally:
        db.close()
    assert stored is not None
    assert stored.status == "REJECTED"
    assert [(row.to_status, row.actor_id, row.reason) for row in rows] == [
        ("PENDING_CREDIT", requester.id, "created"),
        ("REJECTED", None, "credit_reservation_failed"),
    ]
