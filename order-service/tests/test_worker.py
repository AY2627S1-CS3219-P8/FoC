"""Outbox relay and consumer retries, without a broker."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.events import created_expiration_ms
from app.messaging import RETRY_BACKOFF_SECONDS
from app.models import OutboxEvent
from app.worker import PikaPublisher, process_delivery, relay_once
from tests.helpers import order_headers, valid_payload


class RecordingPublisher:
    def __init__(self, fail_at=None):
        self.types = []
        self.fail_at = fail_at

    def publish(self, event):
        if self.fail_at is not None and len(self.types) + 1 == self.fail_at:
            raise RuntimeError("broker unavailable")
        self.types.append(event.event_type)


def test_relay_publishes_in_order_and_stops_when_the_broker_rejects(api):
    for key in ("one", "two"):
        response = api["client"].post(
            "/orders", json=valid_payload(), headers=order_headers(idempotency_key=key)
        )
        assert response.status_code == 201
    publisher = RecordingPublisher(fail_at=2)

    with api["session_factory"]() as db:
        with pytest.raises(RuntimeError):
            relay_once(db, publisher)

    assert publisher.types == ["order.created"]
    with api["session_factory"]() as db:
        events = list(db.scalars(select(OutboxEvent).order_by(OutboxEvent.id)))
        assert events[0].published_at is not None
        assert events[1].published_at is None


def test_retries_use_backoff_then_acknowledge(api, monkeypatch):
    attempts = {"count": 0}

    def flaky(_db, _body):
        attempts["count"] += 1
        if attempts["count"] < 3:
            raise RuntimeError("transient")

    monkeypatch.setattr("app.worker.handle_delivery", flaky)
    delays = []

    outcome = process_delivery(
        api["session_factory"], b"{}", sleep=lambda delay: delays.append(delay)
    )

    assert outcome == "ack"
    assert delays == list(RETRY_BACKOFF_SECONDS[:2])


def test_exhausted_retries_nack(api):
    outcome = process_delivery(
        api["session_factory"], b"not-json", sleep=lambda _delay: None
    )

    assert outcome == "nack"


def test_created_event_expiration_is_the_remaining_ttl():
    now = datetime(2026, 10, 5, tzinfo=timezone.utc)
    event_id = uuid4()
    event = OutboxEvent(
        event_id=event_id,
        event_type="order.created",
        schema_version=1,
        occurred_at=now,
        correlation_id=event_id,
        order_id=event_id,
        payload={"expires_at": (now + timedelta(minutes=30)).isoformat().replace("+00:00", "Z")},
    )

    assert created_expiration_ms(event, now=now) == str(30 * 60 * 1000)
    assert created_expiration_ms(event, now=now + timedelta(hours=2)) == "0"


class _FakeChannel:
    def __init__(self):
        self.calls = []

    def basic_publish(self, **kwargs):
        self.calls.append(kwargs)


def test_pika_publisher_sends_a_persistent_message_with_the_remaining_ttl():
    event_id = uuid4()
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=30)
    event = OutboxEvent(
        event_id=event_id,
        event_type="order.created",
        schema_version=1,
        occurred_at=expires_at,
        correlation_id=event_id,
        order_id=event_id,
        payload={"expires_at": expires_at.isoformat().replace("+00:00", "Z")},
    )
    channel = _FakeChannel()

    PikaPublisher(channel).publish(event)

    call = channel.calls[0]
    assert call["exchange"] == "foc.events"
    assert call["routing_key"] == "order.created"
    assert call["properties"].delivery_mode == 2
    assert call["properties"].message_id == str(event_id)
    assert call["properties"].headers == {"order_id": str(event_id)}
    remaining = int(call["properties"].expiration)
    assert 29 * 60 * 1000 <= remaining <= 30 * 60 * 1000
