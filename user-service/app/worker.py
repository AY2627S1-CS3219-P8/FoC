"""Publish committed User Service outbox events to RabbitMQ."""

import logging
import os
import time
from typing import Protocol

import pika
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db import SessionLocal
from app.events import dump_event
from app.messaging import (
    EXCHANGE,
    RABBITMQ_PORT,
    RELAY_BATCH_SIZE,
    RELAY_POLL_SECONDS,
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


class PikaPublisher:
    def __init__(self, channel: pika.adapters.blocking_connection.BlockingChannel):
        self._channel = channel

    def publish(self, event: UserOutboxEvent) -> None:
        self._channel.basic_publish(
            exchange=EXCHANGE,
            routing_key=event.event_type,
            body=dump_event(event),
            properties=pika.BasicProperties(
                content_type="application/json",
                delivery_mode=2,
                message_id=str(event.event_id),
                headers={"user_id": str(event.user_id)},
            ),
            mandatory=True,
        )


def declare_topology(channel: pika.adapters.blocking_connection.BlockingChannel) -> None:
    """Declare the producer-owned exchange; consumers own their queues."""

    channel.exchange_declare(exchange=EXCHANGE, exchange_type="topic", durable=True)


def relay_once(db: Session, publisher: Publisher) -> int:
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


def connection() -> pika.BlockingConnection:
    return pika.BlockingConnection(
        pika.ConnectionParameters(
            host=required_env("RABBITMQ_HOST"),
            port=RABBITMQ_PORT,
            credentials=pika.PlainCredentials(
                required_env("RABBITMQ_USER"), required_env("RABBITMQ_PASSWORD")
            ),
            heartbeat=60,
            socket_timeout=10,
        )
    )


def main() -> None:
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    broker = connection()
    channel = broker.channel()
    channel.confirm_delivery()
    declare_topology(channel)
    publisher = PikaPublisher(channel)
    logger.info("user_outbox_worker_started")

    while True:
        with SessionLocal() as db:
            try:
                relay_once(db, publisher)
            except Exception:
                db.rollback()
                logger.exception("user_outbox_relay_failed")
                if not broker.is_open:
                    raise
        broker.process_data_events(time_limit=RELAY_POLL_SECONDS)
        time.sleep(RELAY_POLL_SECONDS)


if __name__ == "__main__":
    main()
