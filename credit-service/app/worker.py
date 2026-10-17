"""Relay credit outbox rows and consume Order Service lifecycle events."""

import logging
import os
import time
from collections.abc import Callable
from typing import Protocol

import pika
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import Settings, required_env
from app.db import make_engine, make_session_factory
from app.events import MalformedMessage, dump_event, parse_incoming_event
from app.messaging import (
    EVENT_STREAM_QUEUES,
    EXCHANGE,
    ORDER_EVENTS_DLQ,
    ORDER_EVENTS_QUEUE,
    QUEUE_MAX_LENGTH,
    RABBITMQ_PORT,
    RELAY_BATCH_SIZE,
    RELAY_POLL_SECONDS,
    USER_EVENTS_DLQ,
    USER_EVENTS_QUEUE,
)
from app.models import OutboxEvent, utc_now
from app.services.event_handlers import apply_incoming_event

logger = logging.getLogger(__name__)


class Publisher(Protocol):
    def publish(self, event: OutboxEvent) -> None: ...


class PikaPublisher:
    def __init__(self, channel: pika.adapters.blocking_connection.BlockingChannel):
        self._channel = channel

    def publish(self, event: OutboxEvent) -> None:
        self._channel.basic_publish(
            exchange=EXCHANGE,
            routing_key=event.event_type,
            body=dump_event(event),
            properties=pika.BasicProperties(
                content_type="application/json",
                delivery_mode=2,
                message_id=str(event.event_id),
                headers={"order_id": str(event.order_id)} if event.order_id else {},
            ),
            mandatory=True,
        )


def declare_topology(channel: pika.adapters.blocking_connection.BlockingChannel) -> None:
    """Declare only the queues owned and consumed by Credit Service."""

    channel.exchange_declare(exchange=EXCHANGE, exchange_type="topic", durable=True)
    limit = {"x-max-length": QUEUE_MAX_LENGTH, "x-overflow": "reject-publish"}

    for queue, dlq in (
        (ORDER_EVENTS_QUEUE, ORDER_EVENTS_DLQ),
        (USER_EVENTS_QUEUE, USER_EVENTS_DLQ),
    ):
        channel.queue_declare(queue=dlq, durable=True)
        channel.queue_declare(queue=queue, durable=True, arguments=limit)

    for event_type in (
        "order.created",
        "order.completed",
        "order.cancelled",
        "order.expired",
    ):
        channel.queue_bind(ORDER_EVENTS_QUEUE, EXCHANGE, routing_key=event_type)
    for event_type in ("user.created",):
        channel.queue_bind(USER_EVENTS_QUEUE, EXCHANGE, routing_key=event_type)


def relay_once(db: Session, publisher: Publisher) -> int:
    statement = (
        select(OutboxEvent)
        .where(OutboxEvent.published_at.is_(None))
        .order_by(OutboxEvent.id)
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


def process_delivery(
    session_factory: Callable[[], Session],
    body: bytes,
    *,
    initial_allocation: int,
    retry_backoff_seconds: tuple[float, ...],
    sleep: Callable[[float], None] = time.sleep,
) -> str:
    """Return ack or dead-letter after configurable transient retries."""

    for attempt in range(len(retry_backoff_seconds) + 1):
        db = session_factory()
        try:
            event = parse_incoming_event(body)
            apply_incoming_event(
                db, event, initial_allocation=initial_allocation
            )
            db.commit()
        except MalformedMessage:
            db.rollback()
            logger.exception("credit_event_malformed")
            return "invalid"
        except Exception:
            db.rollback()
            if attempt == len(retry_backoff_seconds):
                logger.exception("credit_event_dead_lettered")
                return "dead-letter"
            delay = retry_backoff_seconds[attempt]
            logger.warning(
                "credit_event_processing_failed",
                extra={"attempt": attempt + 1, "retry_delay_seconds": delay},
            )
            sleep(delay)
        else:
            return "ack"
        finally:
            db.close()
    return "dead-letter"


def selected_queue() -> tuple[str, str]:
    """Resolve the one event stream assigned to this worker process."""

    stream = os.getenv("CREDIT_EVENT_STREAM", "order").strip().lower()
    try:
        return stream, EVENT_STREAM_QUEUES[stream]
    except KeyError as exc:
        allowed = ", ".join(sorted(EVENT_STREAM_QUEUES))
        raise RuntimeError(
            f"CREDIT_EVENT_STREAM must be one of: {allowed}"
        ) from exc


def _connection() -> pika.BlockingConnection:
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
    settings = Settings.from_env()
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    engine = make_engine(settings.database_url)
    session_factory = make_session_factory(engine)
    connection = _connection()
    channel = connection.channel()
    channel.confirm_delivery()
    declare_topology(channel)
    channel.basic_qos(prefetch_count=1)
    publisher = PikaPublisher(channel)
    stream, queue = selected_queue()
    logger.info("credit_worker_started", extra={"event_stream": stream})

    while True:
        # Order-event mutations create credit.* outbox rows. Keep relay
        # responsibility in one process so scaling the User consumer cannot
        # create avoidable duplicate publishes.
        if stream == "order":
            db = session_factory()
            try:
                relay_once(db, publisher)
            except Exception:
                db.rollback()
                logger.exception("credit_outbox_relay_failed")
            finally:
                db.close()

        method, properties, body = channel.basic_get(
            queue=queue, auto_ack=False
        )
        if method is not None:
            outcome = process_delivery(
                session_factory,
                body,
                initial_allocation=settings.initial_credit_allocation,
                retry_backoff_seconds=settings.retry_backoff_seconds,
            )
            if outcome == "ack":
                channel.basic_ack(method.delivery_tag)
            else:
                dlq = (
                    ORDER_EVENTS_DLQ
                    if queue == ORDER_EVENTS_QUEUE
                    else USER_EVENTS_DLQ
                )
                headers = dict(properties.headers or {})
                headers["x-credit-failed-attempts"] = (
                    1
                    if outcome == "invalid"
                    else len(settings.retry_backoff_seconds) + 1
                )
                # Publisher confirms are enabled. A failed DLQ publish raises,
                # leaving the source delivery unacknowledged for broker recovery.
                channel.basic_publish(
                    exchange="",
                    routing_key=dlq,
                    body=body,
                    properties=pika.BasicProperties(
                        content_type=properties.content_type or "application/json",
                        delivery_mode=2,
                        message_id=properties.message_id,
                        correlation_id=properties.correlation_id,
                        headers=headers,
                    ),
                    mandatory=True,
                )
                channel.basic_ack(method.delivery_tag)
        connection.process_data_events(time_limit=RELAY_POLL_SECONDS)


if __name__ == "__main__":
    main()
