"""User Service Kafka outbox relay tests."""

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.db import Base
from app.messaging import USER_TOPIC
from app.models import UserOutboxEvent
from app.worker import KafkaPublisher, relay_once


class FakeProducer:
    def __init__(self, *, acknowledge: bool = True, remaining: int = 0):
        self.acknowledge = acknowledge
        self.remaining = remaining
        self.records = []

    def produce(self, **record):
        self.records.append(record)
        if self.acknowledge:
            record["on_delivery"](None, object())

    def flush(self, _timeout):
        return self.remaining


def outbox_event() -> UserOutboxEvent:
    user_id = uuid4()
    return UserOutboxEvent(
        event_id=uuid4(),
        event_type="user.created",
        schema_version=1,
        occurred_at=datetime.now(timezone.utc),
        correlation_id=uuid4(),
        user_id=user_id,
        payload={
            "user_id": str(user_id),
            "nus_student_number": "A0123456X",
        },
    )


def test_user_event_uses_user_key_headers_and_delivery_confirmation() -> None:
    producer = FakeProducer()
    publisher = KafkaPublisher(producer)
    event = outbox_event()

    publisher.publish(event)

    record = producer.records[0]
    assert record["topic"] == USER_TOPIC
    assert record["key"] == str(event.user_id).encode()
    assert dict(record["headers"]) == {
        "event_type": b"user.created",
        "event_id": str(event.event_id).encode(),
    }


def test_unconfirmed_publish_does_not_mark_outbox_published() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    event = outbox_event()
    with Session(engine) as db:
        db.add(event)
        db.commit()
        event_id = event.event_id

    with Session(engine) as db:
        with pytest.raises(RuntimeError, match="did not acknowledge"):
            relay_once(
                db,
                KafkaPublisher(FakeProducer(acknowledge=False, remaining=1)),
            )
        db.rollback()

    with Session(engine) as db:
        stored = db.scalar(
            select(UserOutboxEvent).where(UserOutboxEvent.event_id == event_id)
        )
        assert stored.published_at is None
    engine.dispose()


def test_confirmed_publish_marks_outbox_published() -> None:
    engine = create_engine("sqlite+pysqlite:///:memory:")
    Base.metadata.create_all(engine)
    event = outbox_event()
    with Session(engine) as db:
        db.add(event)
        db.commit()
        event_id = event.event_id

    producer = FakeProducer()
    with Session(engine) as db:
        assert relay_once(db, KafkaPublisher(producer)) == 1

    with Session(engine) as db:
        stored = db.scalar(
            select(UserOutboxEvent).where(UserOutboxEvent.event_id == event_id)
        )
        assert stored.published_at is not None
    assert len(producer.records) == 1
    engine.dispose()
