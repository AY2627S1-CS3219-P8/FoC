"""Relay the outbox and consume credit and expiry messages.

The API process does not connect to RabbitMQ. A broker outage cannot fail a request.
"""

import logging
import os
import threading
import time
from collections.abc import Callable
from typing import Protocol

import pika
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import required_env
from app.db import database_url, make_engine, make_session_factory
from app.events import created_expiration_ms, dump_event
from app.messaging import (
    CREDIT_DLQ,
    CREDIT_QUEUE,
    CREDIT_SERVICE_QUEUE,
    EXCHANGE,
    EXPIRY_DELAY_QUEUE,
    EXPIRY_DUE_DLQ,
    EXPIRY_DUE_QUEUE,
    EXPIRY_TTL_MS,
    MAX_ATTEMPTS,
    NOTIFICATION_QUEUE,
    QUEUE_MAX_LENGTH,
    RABBITMQ_PORT,
    RELAY_BATCH_SIZE,
    RELAY_POLL_SECONDS,
    RETRY_BACKOFF_SECONDS,
)
from app.models import OutboxEvent, utc_now
from app.services.orders import handle_delivery

logger = logging.getLogger(__name__)


class Publisher(Protocol):
    """Something that accepts one outbox row. Tests substitute a fake."""

    def publish(self, event: OutboxEvent) -> None:
        """Publish one event or raise if the broker rejects it."""


class PikaPublisher:
    def __init__(self, channel: pika.adapters.blocking_connection.BlockingChannel) -> None:
        self._channel = channel

    def publish(self, event: OutboxEvent) -> None:
        expiration = created_expiration_ms(event)
        properties = pika.BasicProperties(
            content_type="application/json",
            delivery_mode=2,
            message_id=str(event.event_id),
            headers={"order_id": str(event.order_id)},
            expiration=expiration,
        )
        self._channel.basic_publish(
            exchange=EXCHANGE,
            routing_key=event.event_type,
            body=dump_event(event),
            properties=properties,
        )


def declare_topology(channel: pika.adapters.blocking_connection.BlockingChannel) -> None:
    """Declare the exchange, the expiry TTL queue, and the queues this service owns.

    Downstream services consume credit-service.order-events and
    notification-service.order-events. Declaring them here keeps events that
    are published before those services start.
    """

    channel.exchange_declare(exchange=EXCHANGE, exchange_type="topic", durable=True)
    limit = {"x-max-length": QUEUE_MAX_LENGTH, "x-overflow": "reject-publish"}

    channel.queue_declare(queue=CREDIT_DLQ, durable=True)
    channel.queue_declare(
        queue=CREDIT_QUEUE,
        durable=True,
        arguments={
            **limit,
            "x-dead-letter-exchange": "",
            "x-dead-letter-routing-key": CREDIT_DLQ,
        },
    )
    channel.queue_bind(CREDIT_QUEUE, EXCHANGE, routing_key="credit.reserved")
    channel.queue_bind(CREDIT_QUEUE, EXCHANGE, routing_key="credit.reservation_failed")

    channel.queue_declare(queue=EXPIRY_DUE_DLQ, durable=True)
    channel.queue_declare(
        queue=EXPIRY_DUE_QUEUE,
        durable=True,
        arguments={
            **limit,
            "x-dead-letter-exchange": "",
            "x-dead-letter-routing-key": EXPIRY_DUE_DLQ,
        },
    )
    channel.queue_declare(
        queue=EXPIRY_DELAY_QUEUE,
        durable=True,
        arguments={
            **limit,
            "x-message-ttl": EXPIRY_TTL_MS,
            "x-dead-letter-exchange": "",
            "x-dead-letter-routing-key": EXPIRY_DUE_QUEUE,
        },
    )
    channel.queue_bind(EXPIRY_DELAY_QUEUE, EXCHANGE, routing_key="order.created")

    for queue in (CREDIT_SERVICE_QUEUE, NOTIFICATION_QUEUE):
        channel.queue_declare(queue=queue, durable=True, arguments=limit)
        channel.queue_bind(queue, EXCHANGE, routing_key="order.#")


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


def _connection() -> pika.BlockingConnection:
    credentials = pika.PlainCredentials(
        required_env("RABBITMQ_USER"), required_env("RABBITMQ_PASSWORD")
    )
    return pika.BlockingConnection(
        pika.ConnectionParameters(
            host=required_env("RABBITMQ_HOST"),
            port=RABBITMQ_PORT,
            credentials=credentials,
            heartbeat=60,
            socket_timeout=10,
        )
    )


def _relay_loop(session_factory: Callable[[], Session], stop: threading.Event) -> None:
    try:
        connection = _connection()
        channel = connection.channel()
        channel.confirm_delivery()
        publisher = PikaPublisher(channel)
        try:
            while not stop.is_set():
                db = session_factory()
                try:
                    relay_once(db, publisher)
                except Exception:
                    db.rollback()
                    logger.exception("outbox_relay_failed")
                    if not connection.is_open:
                        raise
                finally:
                    db.close()
                # pika only sends heartbeats during a pika call. Waiting on the
                # event would let the broker drop this connection after a quiet spell.
                connection.process_data_events(time_limit=RELAY_POLL_SECONDS)
        finally:
            connection.close()
    except Exception:
        logger.exception("outbox_relay_stopped")
        # The consumer cannot publish without this thread. Exit so the container restarts.
        os._exit(1)


def _on_message(session_factory, channel, method, _properties, body: bytes) -> None:
    outcome = process_delivery(session_factory, body)
    if outcome == "ack":
        channel.basic_ack(method.delivery_tag)
    else:
        channel.basic_nack(method.delivery_tag, requeue=False)


def main() -> None:
    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO"),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    engine = make_engine(database_url())
    session_factory = make_session_factory(engine)
    connection = _connection()
    channel = connection.channel()
    declare_topology(channel)
    channel.basic_qos(prefetch_count=1)
    for queue in (CREDIT_QUEUE, EXPIRY_DUE_QUEUE):
        channel.basic_consume(
            queue=queue,
            on_message_callback=lambda ch, method, properties, body: _on_message(
                session_factory, ch, method, properties, body
            ),
        )
    stop = threading.Event()
    relay = threading.Thread(
        target=_relay_loop, args=(session_factory, stop), name="outbox-relay", daemon=True
    )
    logger.info("worker_started")
    relay.start()
    try:
        channel.start_consuming()
    finally:
        stop.set()
        engine.dispose()


if __name__ == "__main__":
    main()
