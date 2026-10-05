"""Who can see which orders."""

from uuid import UUID, uuid4

from app.events import IncomingEvent
from app.services.orders import apply_incoming
from tests.helpers import (
    COURIER_ID,
    OTHER_ID,
    REQUESTER_ID,
    auth_headers,
    insert_order,
    order_headers,
    valid_payload,
)


def test_open_feed_hides_the_callers_own_orders_and_closed_ones(api):
    own = insert_order(api["session_factory"], status="OPEN", requester_id=REQUESTER_ID)
    visible = insert_order(api["session_factory"], status="OPEN", requester_id=OTHER_ID)
    insert_order(api["session_factory"], status="ACCEPTED", requester_id=OTHER_ID, courier_id=COURIER_ID)
    insert_order(api["session_factory"], status="PENDING_CREDIT", requester_id=OTHER_ID)

    response = api["client"].get("/orders/open", headers=auth_headers(REQUESTER_ID))

    assert response.status_code == 200
    body = response.json()
    assert body["total"] == 1
    assert [item["id"] for item in body["items"]] == [str(visible)]
    assert str(own) not in [item["id"] for item in body["items"]]


def test_my_orders_are_split_by_role_and_paginated(api):
    first = insert_order(api["session_factory"], status="OPEN", requester_id=REQUESTER_ID)
    second = insert_order(api["session_factory"], status="CANCELLED", requester_id=REQUESTER_ID)
    insert_order(
        api["session_factory"],
        status="ACCEPTED",
        requester_id=OTHER_ID,
        courier_id=REQUESTER_ID,
    )

    requested = api["client"].get(
        "/orders",
        params={"role": "requester", "limit": 1, "offset": 0},
        headers=auth_headers(REQUESTER_ID),
    )
    delivered = api["client"].get(
        "/orders",
        params={"role": "courier"},
        headers=auth_headers(REQUESTER_ID),
    )

    assert requested.status_code == 200
    assert requested.json()["total"] == 2
    assert len(requested.json()["items"]) == 1
    assert {str(first), str(second)} >= {requested.json()["items"][0]["id"]}
    assert delivered.json()["total"] == 1
    assert delivered.json()["items"][0]["status"] == "ACCEPTED"


def test_credit_confirmation_makes_the_order_visible(api):
    created = api["client"].post("/orders", json=valid_payload(), headers=order_headers())
    order_id = UUID(created.json()["id"])
    event = IncomingEvent(
        event_id=uuid4(),
        event_type="credit.reserved",
        correlation_id=uuid4(),
        order_id=order_id,
        reason=None,
    )
    with api["session_factory"]() as db:
        apply_incoming(db, event)
        db.commit()

    feed = api["client"].get("/orders/open", headers=auth_headers(COURIER_ID))

    assert feed.json()["total"] == 1
    assert feed.json()["items"][0]["status"] == "OPEN"
