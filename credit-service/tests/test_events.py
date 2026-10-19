import json
from uuid import uuid4

import pytest

from app.events import (
    MalformedMessage,
    UserCreatedEvent,
    parse_incoming_event,
    parse_order_event,
)
from app.messaging import OUTGOING_EVENT_TYPES


def event_body(event_type: str = "order.created", **payload_overrides) -> bytes:
    payload = {
        "order_id": str(uuid4()),
        "requester_id": str(uuid4()),
        "credit_amount": 8,
        **payload_overrides,
    }
    return json.dumps(
        {
            "event_id": str(uuid4()),
            "event_type": event_type,
            "schema_version": 1,
            "occurred_at": "2026-10-16T04:00:00Z",
            "correlation_id": str(uuid4()),
            "payload": payload,
        }
    ).encode()


def user_event_body(student_number: str) -> bytes:
    return json.dumps(
        {
            "event_id": str(uuid4()),
            "event_type": "user.created",
            "schema_version": 1,
            "occurred_at": "2026-10-17T04:00:00Z",
            "correlation_id": str(uuid4()),
            "payload": {
                "user_id": str(uuid4()),
                "nus_student_number": student_number,
            },
        }
    ).encode()


def test_parses_created_order_contract() -> None:
    event = parse_order_event(event_body())
    assert event.event_type == "order.created"
    assert event.credit_amount == 8
    assert event.courier_id is None


def test_outgoing_contract_contains_only_reservation_results() -> None:
    assert OUTGOING_EVENT_TYPES == frozenset(
        {"credit.reserved", "credit.reservation_failed"}
    )


def test_completed_order_requires_courier() -> None:
    with pytest.raises(MalformedMessage):
        parse_order_event(event_body("order.completed"))


def test_completed_order_accepts_courier() -> None:
    courier_id = uuid4()
    event = parse_order_event(
        event_body("order.completed", courier_id=str(courier_id))
    )
    assert event.courier_id == courier_id


def test_picked_up_cancellation_requires_courier() -> None:
    with pytest.raises(MalformedMessage):
        parse_order_event(
            event_body("order.cancelled", previous_status="picked_up")
        )


def test_picked_up_cancellation_accepts_courier() -> None:
    courier_id = uuid4()
    event = parse_order_event(
        event_body(
            "order.cancelled",
            previous_status="picked_up",
            courier_id=str(courier_id),
        )
    )
    assert event.courier_id == courier_id


def test_parses_user_created_for_initial_allocation() -> None:
    user_id = uuid4()
    body = json.dumps(
        {
            "event_id": str(uuid4()),
            "event_type": "user.created",
            "schema_version": 1,
            "occurred_at": "2026-10-17T04:00:00Z",
            "correlation_id": str(uuid4()),
            "payload": {
                "user_id": str(user_id),
                "nus_student_number": "A0123456X",
            },
        }
    ).encode()

    event = parse_incoming_event(body)

    assert isinstance(event, UserCreatedEvent)
    assert event.user_id == user_id
    assert event.nus_student_number == "A0123456X"


@pytest.mark.parametrize(
    "student_number",
    [
        "A123",
        "B0123456X",
        "A01234ABC",
        "A１２３４５６７X",
        "A01234567",
    ],
)
def test_rejects_invalid_user_created_student_number(student_number: str) -> None:
    with pytest.raises(MalformedMessage):
        parse_incoming_event(user_event_body(student_number))


def test_normalizes_valid_user_created_student_number() -> None:
    event = parse_incoming_event(user_event_body(" a0123456x "))

    assert isinstance(event, UserCreatedEvent)
    assert event.nus_student_number == "A0123456X"


@pytest.mark.parametrize(
    "mutator",
    [
        lambda body: body.update(schema_version=2),
        lambda body: body.update(event_type="order.accepted"),
        lambda body: body["payload"].update(credit_amount=0),
        lambda body: body["payload"].pop("requester_id"),
    ],
)
def test_rejects_incompatible_contract(mutator) -> None:
    body = json.loads(event_body())
    mutator(body)
    with pytest.raises(MalformedMessage):
        parse_order_event(json.dumps(body).encode())
