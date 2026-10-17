"""Credit worker queue topology tests."""

import json
from uuid import uuid4

from app.messaging import (
    EXCHANGE,
    ORDER_EVENT_TYPES,
    ORDER_EVENTS_DLQ,
    ORDER_EVENTS_QUEUE,
    USER_EVENTS_DLQ,
    USER_EVENTS_QUEUE,
)
from app.worker import declare_topology, process_delivery, selected_queue


class FakeChannel:
    def __init__(self):
        self.bindings = []
        self.queues = []

    def exchange_declare(self, **_kwargs):
        pass

    def queue_declare(self, **kwargs):
        self.queues.append(kwargs)

    def queue_bind(self, queue, exchange, routing_key):
        self.bindings.append((queue, exchange, routing_key))


def test_credit_consumes_only_requested_order_events() -> None:
    channel = FakeChannel()

    declare_topology(channel)

    order_keys = {
        routing_key
        for queue, exchange, routing_key in channel.bindings
        if queue == ORDER_EVENTS_QUEUE and exchange == EXCHANGE
    }
    assert order_keys == ORDER_EVENT_TYPES
    assert "order.#" not in order_keys


def test_credit_consumes_user_created_without_declaring_order_service_queue() -> None:
    channel = FakeChannel()

    declare_topology(channel)

    user_keys = {
        routing_key
        for queue, exchange, routing_key in channel.bindings
        if queue == USER_EVENTS_QUEUE and exchange == EXCHANGE
    }
    assert user_keys == {"user.created"}
    assert {item["queue"] for item in channel.queues} == {
        ORDER_EVENTS_QUEUE,
        ORDER_EVENTS_DLQ,
        USER_EVENTS_QUEUE,
        USER_EVENTS_DLQ,
    }
    assert all(not queue.startswith("order-service.") for queue, _, _ in channel.bindings)


def test_worker_selects_one_configured_event_stream(monkeypatch) -> None:
    monkeypatch.setenv("CREDIT_EVENT_STREAM", "user")
    assert selected_queue() == ("user", USER_EVENTS_QUEUE)


class FakeSession:
    def __init__(self):
        self.rollback_count = 0
        self.closed = False

    def rollback(self):
        self.rollback_count += 1

    def close(self):
        self.closed = True

    def commit(self):
        pass


def test_malformed_event_is_dead_lettered_without_retry() -> None:
    session = FakeSession()
    sleeps = []

    outcome = process_delivery(
        lambda: session,
        b"not-json",
        initial_allocation=100,
        retry_backoff_seconds=(0.5, 1.0, 2.0),
        sleep=sleeps.append,
    )

    assert outcome == "invalid"
    assert sleeps == []
    assert session.rollback_count == 1
    assert session.closed is True


def test_transient_failure_uses_configured_retry_schedule(monkeypatch) -> None:
    body = json.dumps(
        {
            "event_id": str(uuid4()),
            "event_type": "user.created",
            "schema_version": 1,
            "occurred_at": "2026-10-17T04:00:00Z",
            "correlation_id": str(uuid4()),
            "payload": {
                "user_id": str(uuid4()),
                "nus_student_number": "A0123456X",
            },
        }
    ).encode()
    sessions = []
    sleeps = []

    def session_factory():
        session = FakeSession()
        sessions.append(session)
        return session

    def fail_processing(*_args, **_kwargs):
        raise RuntimeError("temporary database failure")

    monkeypatch.setattr("app.worker.apply_incoming_event", fail_processing)

    outcome = process_delivery(
        session_factory,
        body,
        initial_allocation=100,
        retry_backoff_seconds=(0.25, 0.75),
        sleep=sleeps.append,
    )

    assert outcome == "dead-letter"
    assert sleeps == [0.25, 0.75]
    assert len(sessions) == 3
    assert all(session.rollback_count == 1 for session in sessions)
    assert all(session.closed for session in sessions)
