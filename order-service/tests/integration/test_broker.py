"""Postgres and RabbitMQ tests. Skipped unless both services are configured."""

import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from uuid import UUID, uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi import HTTPException
from fastapi.testclient import TestClient
from pika import BasicProperties, BlockingConnection, ConnectionParameters, PlainCredentials
from sqlalchemy import delete, insert, select
from sqlalchemy.orm import Session

from app.clients import Identity
from app.db import make_engine, make_session_factory
from app.events import dump_event
from app.main import app
from app.messaging import (
    CREDIT_DLQ,
    CREDIT_QUEUE,
    EXCHANGE,
    EXPIRY_DELAY_QUEUE,
    EXPIRY_DUE_QUEUE,
    PURGEABLE_QUEUES,
    RABBITMQ_PORT,
)
from app.models import Order, OutboxEvent, ProcessedEvent
from app.services.orders import accept_order
from app.worker import declare_topology, process_delivery, relay_once
from tests.helpers import (
    COURIER_ID,
    REQUESTER_ID,
    SUPPLIER_ID,
    FakeSupplierClient,
    FakeUserClient,
    auth_headers,
    insert_order,
    order_headers,
    valid_payload,
)

_READY = all(
    os.getenv(name)
    for name in (
        "TEST_DATABASE_URL",
        "RABBITMQ_HOST",
        "RABBITMQ_USER",
        "RABBITMQ_PASSWORD",
    )
)

pytestmark = pytest.mark.skipif(
    not _READY,
    reason="Set TEST_DATABASE_URL, RABBITMQ_HOST, RABBITMQ_USER, and RABBITMQ_PASSWORD",
)


@pytest.fixture(scope="session")
def postgres_engine():
    url = os.environ["TEST_DATABASE_URL"]
    database_name = url.rsplit("/", 1)[-1]
    if not url.startswith("postgresql+psycopg") or not database_name.endswith("_test"):
        pytest.fail("TEST_DATABASE_URL must be a postgresql+psycopg database whose name ends in _test")
    os.environ["DATABASE_URL"] = url
    command.upgrade(Config("alembic.ini"), "head")
    engine = make_engine(url)
    yield engine
    engine.dispose()


@pytest.fixture(scope="session")
def broker():
    connection = BlockingConnection(
        ConnectionParameters(
            host=os.environ["RABBITMQ_HOST"],
            port=RABBITMQ_PORT,
            credentials=PlainCredentials(
                os.environ["RABBITMQ_USER"], os.environ["RABBITMQ_PASSWORD"]
            ),
            socket_timeout=10,
        )
    )
    channel = connection.channel()
    declare_topology(channel)
    yield channel
    connection.close()


def _wipe(engine):
    with engine.begin() as connection:
        connection.execute(delete(OutboxEvent))
        connection.execute(delete(ProcessedEvent))
        connection.execute(delete(Order))


@pytest.fixture(autouse=True)
def clean(postgres_engine, broker):
    _wipe(postgres_engine)
    for queue in PURGEABLE_QUEUES:
        broker.queue_purge(queue)
    yield
    _wipe(postgres_engine)


@pytest.fixture()
def client(postgres_engine):
    del postgres_engine
    with TestClient(app) as test_client:
        app.state.user_client = FakeUserClient()
        app.state.supplier_client = FakeSupplierClient({SUPPLIER_ID})
        yield test_client


def test_models_match_the_migration():
    command.check(Config("alembic.ini"))


def test_ten_couriers_accepting_at_once_produce_one_winner(postgres_engine):
    order_id = insert_order(
        make_session_factory(postgres_engine), status="OPEN", requester_id=REQUESTER_ID
    )
    actors = [uuid4() for _index in range(10)]
    barrier = threading.Barrier(10)

    def attempt(actor_id):
        barrier.wait(timeout=10)
        with Session(postgres_engine) as db:
            try:
                accept_order(db, order_id, Identity(id=actor_id, role="user", status="active"))
            except HTTPException as exc:
                return exc.status_code
            return 200

    with ThreadPoolExecutor(max_workers=10) as pool:
        codes = list(pool.map(attempt, actors))

    assert sorted(codes) == [200, *([409] * 9)]
    with Session(postgres_engine) as db:
        order = db.get(Order, order_id)
        events = list(db.scalars(select(OutboxEvent)))
        assert order.status == "ACCEPTED"
        assert order.courier_id in actors
        assert [event.event_type for event in events] == ["order.accepted"]


def test_round_trip_publishes_one_ordered_workflow(client, postgres_engine, broker):
    correlation_id = uuid4()
    created = client.post(
        "/orders",
        json=valid_payload(),
        headers=order_headers(**{"X-Correlation-ID": str(correlation_id)}),
    )
    assert created.status_code == 201
    order_id = UUID(created.json()["id"])
    factory = make_session_factory(postgres_engine)
    reserved = _message(order_id, correlation_id, "credit.reserved")
    broker.basic_publish(
        exchange=EXCHANGE,
        routing_key="credit.reserved",
        body=reserved,
        properties=BasicProperties(delivery_mode=2),
    )
    broker.basic_publish(
        exchange=EXCHANGE,
        routing_key="credit.reserved",
        body=reserved,
        properties=BasicProperties(delivery_mode=2),
    )
    again = _message(order_id, correlation_id, "credit.reserved")
    broker.basic_publish(
        exchange=EXCHANGE,
        routing_key="credit.reserved",
        body=again,
        properties=BasicProperties(delivery_mode=2),
    )
    for _index in range(3):
        outcome, _body = _consume(broker, CREDIT_QUEUE, factory)
        assert outcome == "ack"

    accepted = client.post(f"/orders/{order_id}/accept", headers=auth_headers(COURIER_ID))
    picked_up = client.post(f"/orders/{order_id}/pickup", headers=auth_headers(COURIER_ID))
    completed = client.post(f"/orders/{order_id}/complete", headers=auth_headers(REQUESTER_ID))
    assert (accepted.status_code, picked_up.status_code, completed.status_code) == (200, 200, 200)

    capture = f"test-capture-{uuid4().hex}"
    broker.queue_declare(queue=capture, exclusive=True, auto_delete=True)
    broker.queue_bind(capture, EXCHANGE, routing_key="order.#")
    with Session(postgres_engine) as db:
        relay_once(db, _ChannelPublisher(broker))
    events = _drain(broker, capture)

    assert [event["event_type"] for event in events] == [
        "order.created",
        "order.opened",
        "order.accepted",
        "order.picked_up",
        "order.completed",
    ]
    assert {event["correlation_id"] for event in events} == {str(correlation_id)}
    opened = [event for event in events if event["event_type"] == "order.opened"]
    assert len(opened) == 1
    assert events[-1]["payload"]["courier_id"] == str(COURIER_ID)
    assert events[-1]["payload"]["credit_amount"] == 5


def test_expiry_uses_the_ttl_queue_and_ignores_redelivery(postgres_engine, broker):
    order_id = insert_order(make_session_factory(postgres_engine), status="OPEN")
    body = _message(order_id, uuid4(), "order.created")
    broker.basic_publish(
        exchange="",
        routing_key=EXPIRY_DELAY_QUEUE,
        body=body,
        properties=BasicProperties(expiration="100", delivery_mode=2),
    )
    method, _properties, received = _wait(broker, EXPIRY_DUE_QUEUE)
    factory = make_session_factory(postgres_engine)
    assert process_delivery(factory, received, sleep=lambda _delay: None) == "ack"
    broker.basic_nack(method.delivery_tag, requeue=True)
    method, _properties, redelivered = _wait(broker, EXPIRY_DUE_QUEUE)
    assert process_delivery(factory, redelivered, sleep=lambda _delay: None) == "ack"
    broker.basic_ack(method.delivery_tag)

    with Session(postgres_engine) as db:
        order = db.get(Order, order_id)
        events = list(db.scalars(select(OutboxEvent)))
        assert order.status == "EXPIRED"
        assert [event.event_type for event in events] == ["order.expired"]


def test_malformed_credit_message_is_dead_lettered(postgres_engine, broker):
    broker.basic_publish(
        exchange="",
        routing_key=CREDIT_QUEUE,
        body=b"not-json",
        properties=BasicProperties(delivery_mode=2),
    )
    outcome, body = _consume(broker, CREDIT_QUEUE, make_session_factory(postgres_engine))
    assert outcome == "nack"
    assert body == b"not-json"
    method, _properties, dead = _wait(broker, CREDIT_DLQ)
    broker.basic_ack(method.delivery_tag)
    assert dead == b"not-json"


def test_feed_and_transition_stay_inside_the_latency_budget(client, postgres_engine):
    requester_id = uuid4()
    now = datetime.now(timezone.utc)
    rows = [
        {
            "id": uuid4(),
            "requester_id": requester_id,
            "pickup_supplier_id": SUPPLIER_ID,
            "delivery_label": "PGP Tower",
            "delivery_latitude": 1.291,
            "delivery_longitude": 103.777,
            "delivery_details": "Lobby",
            "item_description": "Noodles",
            "credit_amount": 5,
            "status": "OPEN",
            "idempotency_key": f"seed-{index}",
            "request_hash": "seed",
            "courier_id": None,
            "accepted_at": None,
            "picked_up_at": None,
            "completed_at": None,
            "cancelled_at": None,
            "cancelled_by": None,
            "expired_at": None,
            "expires_at": now,
            "correlation_id": uuid4(),
            "rejection_reason": None,
            "created_at": now,
            "updated_at": now,
        }
        for index in range(22_500)
    ]
    with Session(postgres_engine) as db:
        for start in range(0, len(rows), 1000):
            db.execute(insert(Order), rows[start : start + 1000])
        db.commit()

    caller = uuid4()
    started = time.perf_counter()
    feed = client.get("/orders/open", headers=auth_headers(caller), params={"limit": 20})
    feed_seconds = time.perf_counter() - started
    assert feed.status_code == 200
    assert feed.json()["total"] == 22_500
    assert feed_seconds < 0.5

    order_id = feed.json()["items"][0]["id"]
    started = time.perf_counter()
    accepted = client.post(f"/orders/{order_id}/accept", headers=auth_headers(caller))
    accept_seconds = time.perf_counter() - started
    assert accepted.status_code == 200
    assert accept_seconds < 0.5

    started = time.perf_counter()
    created = client.post(
        "/orders",
        json=valid_payload(),
        headers=order_headers(user_id=caller, idempotency_key="latency-create"),
    )
    create_seconds = time.perf_counter() - started
    assert created.status_code == 201
    assert create_seconds < 1


class _ChannelPublisher:
    def __init__(self, channel):
        self._channel = channel

    def publish(self, event):
        self._channel.basic_publish(
            exchange=EXCHANGE,
            routing_key=event.event_type,
            body=dump_event(event),
            properties=BasicProperties(
                content_type="application/json",
                delivery_mode=2,
                message_id=str(event.event_id),
                headers={"order_id": str(event.order_id)},
            ),
        )


def _message(order_id, correlation_id, event_type):
    body = {
        "event_id": str(uuid4()),
        "event_type": event_type,
        "schema_version": 1,
        "occurred_at": "2026-10-05T00:00:00Z",
        "correlation_id": str(correlation_id),
        "payload": {"order_id": str(order_id)},
    }
    return json.dumps(body).encode()


def _consume(channel, queue, session_factory):
    method, _properties, body = channel.basic_get(queue, auto_ack=False)
    assert method is not None
    outcome = process_delivery(session_factory, body, sleep=lambda _delay: None)
    if outcome == "ack":
        channel.basic_ack(method.delivery_tag)
    else:
        channel.basic_nack(method.delivery_tag, requeue=False)
    return outcome, body


def _wait(channel, queue, timeout=10):
    deadline = time.time() + timeout
    while time.time() < deadline:
        method, properties, body = channel.basic_get(queue, auto_ack=False)
        if method is not None:
            return method, properties, body
        time.sleep(0.05)
    raise AssertionError(f"timed out waiting for {queue}")


def _drain(channel, queue):
    messages = []
    deadline = time.time() + 2
    while time.time() < deadline:
        method, _properties, body = channel.basic_get(queue, auto_ack=True)
        if method is None:
            if messages:
                return messages
            time.sleep(0.05)
            continue
        messages.append(json.loads(body))
        deadline = time.time() + 0.2
    return messages
