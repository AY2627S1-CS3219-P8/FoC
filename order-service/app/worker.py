"""Relay the outbox, consume credit events, and expire orders that are past due.

The API process does not connect to Kafka. A broker outage cannot fail a request.
"""

import logging
import os
import time
from collections.abc import Callable
from typing import Protocol

from confluent_kafka import Consumer, KafkaException, Message, Producer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import required_env
from app.db import database_url, make_engine, make_session_factory
from app.events import dump_event
from app.messaging import (
    CONSUMER_GROUP,
    CREDIT_DLQ_TOPIC,
    CREDIT_TOPIC,
    EXPIRY_SWEEP_SECONDS,
    MAX_ATTEMPTS,
    ORDER_TOPIC,
    RELAY_BATCH_SIZE,
    RELAY_POLL_SECONDS,
    RETRY_BACKOFF_SECONDS,
)
from app.models import OutboxEvent, utc_now
from app.services.orders import expire_overdue_orders, handle_delivery

logger = logging.getLogger(__name__)

PUBLISH_TIMEOUT_SECONDS = 10


class Publisher(Protocol):
    """Something that accepts one outbox row. Tests substitute a fake."""

    def publish(self, event: OutboxEvent) -> None:
        """Publish one event or raise if the broker rejects it."""


class _Delivery:
    """Result of one produce call. A later call cannot observe this one."""

    def __init__(self) -> None:
        self.error = None
        self.done = False

    def __call__(self, err, _message) -> None:
        self.error = err
        self.done = True


class KafkaPublisher:
    def __init__(self, producer: Producer) -> None:
        self._producer = producer

    def publish(self, event: OutboxEvent) -> None:
        delivery = _Delivery()
        self._producer.produce(
            topic=ORDER_TOPIC,
            key=str(event.order_id).encode("utf-8"),
            value=dump_event(event),
            headers=[
                ("event_type", event.event_type.encode("utf-8")),
                ("event_id", str(event.event_id).encode("utf-8")),
            ],
            on_delivery=delivery,
        )
        self._require_delivery(delivery)

    def dead_letter(self, message: Message) -> None:
        """Copy a credit message that could not be applied onto the dead-letter topic."""

        delivery = _Delivery()
        self._producer.produce(
            topic=CREDIT_DLQ_TOPIC,
            key=message.key(),
            value=message.value(),
            headers=message.headers(),
            on_delivery=delivery,
        )
        self._require_delivery(delivery)

    def _require_delivery(self, delivery: _Delivery) -> None:
        self._producer.flush(PUBLISH_TIMEOUT_SECONDS)
        if delivery.error is not None:
            raise KafkaException(delivery.error)
        if not delivery.done:
            raise RuntimeError("Kafka did not acknowledge the record")


def relay_once(db: Session, publisher: Publisher) -> int:
    """Publish unpublished outbox rows in id order. Stop at the first broker failure."""

    statement = (
        select(OutboxEvent)
        .where(OutboxEvent.published_at.is_(None))
        .order_by(OutboxEvent.id)
        .limit(RELAY_BATCH_SIZE)
    )
    if db.get_bind().dialect.name == "postgresql":
        statement = statement.with_for_update(skip_locked=True)
    pending = list(db.scalars(statement))
    published = 0
    for event in pending:
        publisher.publish(event)
        event.published_at = utc_now()
        db.commit()
        published += 1
    return published


def process_delivery(
    session_factory: Callable[[], Session],
    body: bytes,
    *,
    sleep: Callable[[float], None] = time.sleep,
) -> str:
    """Apply one message. Returns 'ack' or 'nack' after bounded backoff."""

    for attempt in range(MAX_ATTEMPTS):
        db = session_factory()
        try:
            handle_delivery(db, body)
        except Exception:
            db.rollback()
            if attempt >= MAX_ATTEMPTS - 1:
                logger.exception("message_dead_lettered")
                return "nack"
            logger.warning(
                "message_processing_failed", extra={"attempt": attempt + 1}
            )
            sleep(RETRY_BACKOFF_SECONDS[attempt])
        else:
            return "ack"
        finally:
            db.close()
    return "nack"


def _client_config() -> dict:
    return {"bootstrap.servers": required_env("KAFKA_BOOTSTRAP_SERVERS")}


def _handle_message(
    session_factory: Callable[[], Session],
    publisher: KafkaPublisher,
    consumer: Consumer,
    message: Message,
) -> None:
    error = message.error()
    if error is not None:
        if error.fatal():
            raise KafkaException(error)
        logger.error("kafka_poll_error", extra={"reason": str(error)})
        return
    if process_delivery(session_factory, message.value() or b"") == "nack":
        publisher.dead_letter(message)
    consumer.commit(message=message, asynchronous=False)


def _relay(session_factory: Callable[[], Session], publisher: Publisher) -> None:
    db = session_factory()
    try:
        relay_once(db, publisher)
    except Exception:
        db.rollback()
        logger.exception("outbox_relay_failed")
    finally:
        db.close()


def _sweep(session_factory: Callable[[], Session], next_sweep: float) -> float:
    now = time.monotonic()
    if now < next_sweep:
        return next_sweep
    db = session_factory()
    try:
        expire_overdue_orders(db)
    except Exception:
        db.rollback()
        logger.exception("expiry_sweep_failed")
    finally:
        db.close()
    return now + EXPIRY_SWEEP_SECONDS


def main() -> None:
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    engine = make_engine(database_url())
    session_factory = make_session_factory(engine)
    producer = Producer(
        {
            **_client_config(),
            "enable.idempotence": True,
            "acks": "all",
            "message.timeout.ms": PUBLISH_TIMEOUT_SECONDS * 1000,
        }
    )
    publisher = KafkaPublisher(producer)
    consumer = Consumer(
        {
            **_client_config(),
            "group.id": CONSUMER_GROUP,
            "enable.auto.commit": False,
            "auto.offset.reset": "earliest",
        }
    )
    consumer.subscribe([CREDIT_TOPIC])
    next_sweep = time.monotonic()
    logger.info("worker_started")
    try:
        while True:
            message = consumer.poll(RELAY_POLL_SECONDS)
            if message is not None:
                _handle_message(session_factory, publisher, consumer, message)
            _relay(session_factory, publisher)
            next_sweep = _sweep(session_factory, next_sweep)
    finally:
        consumer.close()
        producer.flush(PUBLISH_TIMEOUT_SECONDS)
        engine.dispose()


if __name__ == "__main__":
    main()
