"""Tests for errand request creation."""

from sqlalchemy import func, select

from app.models import Order, OutboxEvent
from tests.helpers import (
    OTHER_ID,
    REQUESTER_ID,
    SUPPLIER_ID,
    auth_headers,
    order_headers,
    valid_payload,
)


def _count(session_factory, model):
    with session_factory() as db:
        return db.scalar(select(func.count()).select_from(model))


def test_create_order_persists_pending_credit_order(api):
    response = api["client"].post("/orders", json=valid_payload(), headers=order_headers())

    assert response.status_code == 201
    body = response.json()
    assert body["requester_id"] == str(REQUESTER_ID)
    assert body["pickup_supplier_id"] == str(SUPPLIER_ID)
    assert body["status"] == "PENDING_CREDIT"
    assert body["credit_amount"] == 5
    assert body["courier_id"] is None
    assert _count(api["session_factory"], Order) == 1
    with api["session_factory"]() as db:
        event = db.scalars(select(OutboxEvent)).one()
        assert event.event_type == "order.created"
        assert event.published_at is None
        assert event.payload["order_id"] == body["id"]
        assert event.payload["credit_amount"] == 5
        assert "expires_at" in event.payload
        assert "courier_id" not in event.payload


def test_create_order_rejects_missing_required_fields(api):
    response = api["client"].post(
        "/orders",
        json={"pickup_supplier_id": str(SUPPLIER_ID), "credit_amount": 5},
        headers=order_headers(),
    )

    assert response.status_code == 422
    assert _count(api["session_factory"], Order) == 0


def test_create_order_rejects_blank_item_description(api):
    response = api["client"].post(
        "/orders",
        json=valid_payload(item_description="   "),
        headers=order_headers(),
    )

    assert response.status_code == 422
    assert _count(api["session_factory"], Order) == 0


def test_create_order_rejects_unknown_supplier(api):
    api["supplier"].known = set()

    response = api["client"].post("/orders", json=valid_payload(), headers=order_headers())

    assert response.status_code == 422
    assert response.json()["detail"] == "Pickup location is not supported"
    assert _count(api["session_factory"], Order) == 0


def test_create_order_reports_supplier_outage_without_saving(api):
    api["supplier"].unavailable = True

    response = api["client"].post("/orders", json=valid_payload(), headers=order_headers())

    assert response.status_code == 503
    assert response.json()["detail"] == "Pickup locations are temporarily unavailable"
    assert _count(api["session_factory"], Order) == 0


def test_create_order_rejects_delivery_outside_campus(api):
    payload = valid_payload(
        delivery={
            "label": "Marina Bay",
            "latitude": 1.280,
            "longitude": 103.860,
            "details": "Outside campus",
        }
    )

    response = api["client"].post("/orders", json=payload, headers=order_headers())

    assert response.status_code == 422
    assert response.json()["detail"] == "Delivery location is not supported"
    assert _count(api["session_factory"], Order) == 0


def test_create_order_accepts_utown_and_engineering_coordinates(api):
    for latitude, longitude in ((1.306, 103.773), (1.299, 103.753)):
        payload = valid_payload(
            delivery={
                "label": "Campus",
                "latitude": latitude,
                "longitude": longitude,
                "details": "On campus",
            }
        )
        response = api["client"].post(
            "/orders",
            json=payload,
            headers=order_headers(idempotency_key=f"{latitude}-{longitude}"),
        )
        assert response.status_code == 201


def test_create_order_replays_same_idempotency_key(api):
    first = api["client"].post("/orders", json=valid_payload(), headers=order_headers())
    second = api["client"].post("/orders", json=valid_payload(), headers=order_headers())

    assert first.status_code == 201
    assert second.status_code == 200
    assert first.json()["id"] == second.json()["id"]
    assert _count(api["session_factory"], Order) == 1
    assert _count(api["session_factory"], OutboxEvent) == 1


def test_create_order_rejects_idempotency_key_with_different_body(api):
    first = api["client"].post("/orders", json=valid_payload(), headers=order_headers())
    second = api["client"].post(
        "/orders",
        json=valid_payload(credit_amount=10),
        headers=order_headers(),
    )

    assert first.status_code == 201
    assert second.status_code == 409
    assert _count(api["session_factory"], Order) == 1


def test_create_order_requires_bearer_token(api):
    response = api["client"].post(
        "/orders",
        json=valid_payload(),
        headers={"Idempotency-Key": "create-order-1"},
    )

    assert response.status_code == 401
    assert _count(api["session_factory"], Order) == 0


def test_create_order_rejects_invalid_bearer_token(api):
    response = api["client"].post(
        "/orders",
        json=valid_payload(),
        headers=order_headers() | {"Authorization": "Bearer not-a-session"},
    )

    assert response.status_code == 401


def test_create_order_requires_idempotency_key(api):
    response = api["client"].post(
        "/orders",
        json=valid_payload(),
        headers=auth_headers(),
    )

    assert response.status_code == 422


def test_create_order_rejects_a_non_uuid_correlation_id(api):
    response = api["client"].post(
        "/orders",
        json=valid_payload(),
        headers=order_headers(**{"X-Correlation-ID": "not-a-uuid"}),
    )

    assert response.status_code == 422
    assert _count(api["session_factory"], Order) == 0


def test_create_order_allows_different_requesters_with_same_idempotency_key(api):
    first = api["client"].post("/orders", json=valid_payload(), headers=order_headers())
    second = api["client"].post(
        "/orders",
        json=valid_payload(),
        headers=order_headers(user_id=OTHER_ID),
    )

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] != second.json()["id"]
    assert _count(api["session_factory"], Order) == 2


def test_pending_order_is_hidden_from_the_open_feed(api):
    created = api["client"].post("/orders", json=valid_payload(), headers=order_headers())
    assert created.status_code == 201

    feed = api["client"].get("/orders/open", headers=auth_headers(OTHER_ID))

    assert feed.status_code == 200
    assert feed.json()["total"] == 0
