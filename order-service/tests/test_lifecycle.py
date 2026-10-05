"""Lifecycle transitions, repeats, and delivery changes."""

import pytest
from sqlalchemy import func, select

from app.models import Order, OutboxEvent
from tests.helpers import (
    ADMIN_ID,
    COURIER_ID,
    REQUESTER_ID,
    ACTORS,
    auth_headers,
    insert_order,
    valid_payload,
)


# status, action, actor, expected HTTP status, expected order status, event type or None
CASES = [
    ("OPEN", "accept", "other", 200, "ACCEPTED", "order.accepted"),
    ("OPEN", "accept", "requester", 403, "OPEN", None),
    ("ACCEPTED", "accept", "courier", 200, "ACCEPTED", None),
    ("ACCEPTED", "accept", "other", 409, "ACCEPTED", None),
    ("ACCEPTED", "pickup", "courier", 200, "PICKED_UP", "order.picked_up"),
    ("ACCEPTED", "pickup", "requester", 403, "ACCEPTED", None),
    ("ACCEPTED", "pickup", "other", 404, "ACCEPTED", None),
    ("PICKED_UP", "pickup", "courier", 200, "PICKED_UP", None),
    ("PICKED_UP", "complete", "requester", 200, "COMPLETED", "order.completed"),
    ("PICKED_UP", "complete", "courier", 403, "PICKED_UP", None),
    ("COMPLETED", "complete", "requester", 200, "COMPLETED", None),
    ("PICKED_UP", "cancel", "requester", 403, "PICKED_UP", None),
    ("PICKED_UP", "cancel", "admin", 200, "CANCELLED", "order.cancelled"),
    ("OPEN", "cancel", "requester", 200, "CANCELLED", "order.cancelled"),
    ("OPEN", "cancel", "other", 404, "OPEN", None),
    ("ACCEPTED", "cancel", "requester", 200, "CANCELLED", "order.cancelled"),
    ("COMPLETED", "cancel", "requester", 409, "COMPLETED", None),
    ("EXPIRED", "cancel", "requester", 409, "EXPIRED", None),
    ("CANCELLED", "cancel", "requester", 409, "CANCELLED", None),
    ("REJECTED", "cancel", "requester", 409, "REJECTED", None),
    ("PENDING_CREDIT", "cancel", "requester", 200, "CANCELLED", "order.cancelled"),
    ("PENDING_CREDIT", "accept", "other", 404, "PENDING_CREDIT", None),
    ("OPEN", "complete", "requester", 409, "OPEN", None),
    ("ACCEPTED", "complete", "requester", 409, "ACCEPTED", None),
    ("COMPLETED", "accept", "other", 404, "COMPLETED", None),
    ("EXPIRED", "accept", "other", 404, "EXPIRED", None),
    ("PICKED_UP", "accept", "courier", 409, "PICKED_UP", None),
]


def _seed(api, status):
    courier_id = COURIER_ID if status in {"ACCEPTED", "PICKED_UP", "COMPLETED"} else None
    cancelled_by = ADMIN_ID if status == "CANCELLED" else None
    return insert_order(
        api["session_factory"],
        status=status,
        courier_id=courier_id,
        cancelled_by=cancelled_by,
    )


@pytest.mark.parametrize(
    ("start", "action", "actor", "http_status", "end_status", "event_type"),
    CASES,
)
def test_order_action(api, start, action, actor, http_status, end_status, event_type):
    order_id = _seed(api, start)
    user_id, role = ACTORS[actor]

    response = api["client"].post(
        f"/orders/{order_id}/{action}",
        headers=auth_headers(user_id, role=role),
    )

    assert response.status_code == http_status
    with api["session_factory"]() as db:
        order = db.get(Order, order_id)
        events = db.scalars(select(OutboxEvent).order_by(OutboxEvent.id)).all()
        assert order.status == end_status
        if event_type is None:
            assert events == []
        else:
            assert [event.event_type for event in events] == [event_type]
            assert events[0].payload["requester_id"] == str(REQUESTER_ID)
            assert events[0].payload["credit_amount"] == 5


def test_completion_keeps_requester_courier_and_amount(api):
    order_id = _seed(api, "PICKED_UP")

    response = api["client"].post(
        f"/orders/{order_id}/complete", headers=auth_headers(REQUESTER_ID)
    )

    assert response.status_code == 200
    body = response.json()
    assert body["requester_id"] == str(REQUESTER_ID)
    assert body["courier_id"] == str(COURIER_ID)
    assert body["credit_amount"] == 5
    with api["session_factory"]() as db:
        event = db.scalars(select(OutboxEvent)).one()
        assert event.event_type == "order.completed"
        assert event.payload["courier_id"] == str(COURIER_ID)
        assert event.payload["requester_id"] == str(REQUESTER_ID)
        assert event.payload["credit_amount"] == 5


def test_admin_cancel_after_pickup_records_compensation_context(api):
    order_id = _seed(api, "PICKED_UP")

    response = api["client"].post(
        f"/orders/{order_id}/cancel",
        headers=auth_headers(ADMIN_ID, role="admin"),
    )

    assert response.status_code == 200
    with api["session_factory"]() as db:
        event = db.scalars(select(OutboxEvent)).one()
        assert event.payload["previous_status"] == "PICKED_UP"
        assert event.payload["cancelled_by"] == str(ADMIN_ID)
        assert event.payload["courier_id"] == str(COURIER_ID)


def test_repeating_cancel_does_not_write_another_event(api):
    order_id = _seed(api, "OPEN")
    headers = auth_headers(REQUESTER_ID)

    first = api["client"].post(f"/orders/{order_id}/cancel", headers=headers)
    second = api["client"].post(f"/orders/{order_id}/cancel", headers=headers)

    assert first.status_code == 200
    assert second.status_code == 200
    with api["session_factory"]() as db:
        assert db.scalar(select(func.count()).select_from(OutboxEvent)) == 1


def test_stranger_cannot_read_an_order(api):
    order_id = _seed(api, "OPEN")

    response = api["client"].get(
        f"/orders/{order_id}", headers=auth_headers(ACTORS["other"][0])
    )

    assert response.status_code == 404


def test_requester_can_change_destination_until_pickup(api):
    order_id = _seed(api, "ACCEPTED")
    delivery = valid_payload()["delivery"] | {
        "label": "Cinnamon College",
        "latitude": 1.306,
        "longitude": 103.773,
    }

    response = api["client"].patch(
        f"/orders/{order_id}/delivery",
        json=delivery,
        headers=auth_headers(REQUESTER_ID),
    )

    assert response.status_code == 200
    assert response.json()["delivery_label"] == "Cinnamon College"
    with api["session_factory"]() as db:
        assert db.scalar(select(func.count()).select_from(OutboxEvent)) == 0


def test_destination_change_is_rejected_after_pickup(api):
    order_id = _seed(api, "PICKED_UP")

    response = api["client"].patch(
        f"/orders/{order_id}/delivery",
        json=valid_payload()["delivery"],
        headers=auth_headers(REQUESTER_ID),
    )

    assert response.status_code == 409
    with api["session_factory"]() as db:
        order = db.get(Order, order_id)
        assert order.status == "PICKED_UP"
        assert order.delivery_label == "PGP Tower"
