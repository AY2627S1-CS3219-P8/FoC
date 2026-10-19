"""Publish committed User Service outbox events to Kafka."""

import logging
import os
import time
from typing import Protocol

from confluent_kafka import KafkaException, Producer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.events import dump_event
from app.messaging import (
    PUBLISH_TIMEOUT_SECONDS,
    RELAY_BATCH_SIZE,
    RELAY_POLL_SECONDS,
    USER_TOPIC,
)
from app.models import UserOutboxEvent, utc_now

logger = logging.getLogger(__name__)


def required_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} must be set")
    return value


class Publisher(Protocol):
    def publish(self, event: UserOutboxEvent) -> None: ...


class _Delivery:
    """Delivery callback state for one Kafka produce call."""

    def __init__(self) -> None:
        self.error = None
        self.done = False

    def __call__(self, error, _message) -> None:
        self.error = error
        self.done = True


class KafkaPublisher:
    def __init__(self, producer: Producer) -> None:
        self._producer = producer

    def publish(self, event: UserOutboxEvent) -> None:
        delivery = _Delivery()
        self._producer.produce(
            topic=USER_TOPIC,
            key=str(event.user_id).encode("utf-8"),
            value=dump_event(event),
            headers=[
                ("event_type", event.event_type.encode("utf-8")),
                ("event_id", str(event.event_id).encode("utf-8")),
            ],
            on_delivery=delivery,
        )
        remaining = self._producer.flush(PUBLISH_TIMEOUT_SECONDS)
        if delivery.error is not None:
            raise KafkaException(delivery.error)
        if remaining or not delivery.done:
            raise RuntimeError("Kafka did not acknowledge the record")


def relay_once(db: Session, publisher: Publisher) -> int:
    """Publish outbox rows in order and mark each only after confirmation."""

    statement = (
        select(UserOutboxEvent)
        .where(UserOutboxEvent.published_at.is_(None))
        .order_by(UserOutboxEvent.id)
        .limit(RELAY_BATCH_SIZE)
    )
    if db.get_bind().dialect.name == "postgresql":
        statement = statement.with_for_update(skip_locked=True)
    pending = list(db.scalars(statement))
    for event in pending:
        publisher.publish(event)
        event.published_at = utc_now()
        db.commit()
    return len(pending)


def main() -> None:
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    producer = Producer(
        {
            "bootstrap.servers": required_env("KAFKA_BOOTSTRAP_SERVERS"),
            "enable.idempotence": True,
            "acks": "all",
            "message.timeout.ms": PUBLISH_TIMEOUT_SECONDS * 1000,
        }
    )
    publisher = KafkaPublisher(producer)
    logger.info("user_outbox_worker_started topic=%s", USER_TOPIC)

    try:
        while True:
            with SessionLocal() as db:
                try:
                    relay_once(db, publisher)
                except Exception:
                    db.rollback()
                    logger.exception("user_outbox_relay_failed")
            time.sleep(RELAY_POLL_SECONDS)
    finally:
        producer.flush(PUBLISH_TIMEOUT_SECONDS)


if __name__ == "__main__":
    main()
