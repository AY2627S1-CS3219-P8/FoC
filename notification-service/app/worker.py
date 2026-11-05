# AI Assistance Disclosure:
# Tool: Claude Code (model: claude-opus-5-5), date: 2026-11-03
# Scope: Writing implementation code — write a worker that validates configuration, logs startup, idles until SIGTERM/SIGINT, and exits non-zero on invalid configuration.
# Author review: Keith confirmed review of all affected changes.
# Details: notification-service/ai/usage-log.md; ai-20261103-001
# Tool: Claude Code (model: claude-opus-5-5), date: 2026-11-04
# Scope: Writing implementation code — replace the idle loop with the order.events consumer: store events in one transaction with NOTIFY, then commit the offset synchronously; stop on malformed records and on any exception (ai-20261104-003).
# Author review: Keith confirmed verification, with 551 tests passed on the Pytest suite (ai-20261104-003).
# Details: notification-service/ai/usage-log.md; ai-20261104-003

"""Consume ``order.events`` and write notifications.

Each record is stored in one database transaction, and its offset is committed
only after that transaction has committed. A crash in between redelivers the
record, and the ``processed_events`` primary key then identifies it as a
duplicate, so delivery is at-least-once but the stored effect happens once.

Failures stop the worker without committing the offset. Failure logs give the
exception type and stack frames, never its message: driver errors can quote
statement parameters and JSON from the record.
"""

import logging
import signal
import sys
import threading
import traceback
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Protocol

from confluent_kafka import Consumer, KafkaException, Message
from psycopg.errors import UniqueViolation
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import WorkerSettings, configure_logging
from app.db import make_engine, make_session_factory
from app.events import BeforeCutoff, Event, Ignore, Malformed, process_record
from app.models import Notification, ProcessedEvent

logger = logging.getLogger(__name__)

ORDER_TOPIC = "order.events"
CONSUMER_GROUP = "notification-service-order"
POLL_TIMEOUT_SECONDS = 1.0
NOTIFY_CHANNEL = "notifications"
# PostgreSQL's default name for the primary key in the initial migration.
PROCESSED_EVENTS_PKEY = "processed_events_pkey"


class WorkerAbort(Exception):
    """The worker must stop. The cause has already been logged."""


class CommittingConsumer(Protocol):
    def poll(self, timeout: float) -> Message | None: ...

    def commit(self, *, message: Message, asynchronous: bool) -> object: ...

    def close(self) -> None: ...


def _is_duplicate_event(error: IntegrityError) -> bool:
    return (
        isinstance(error.orig, UniqueViolation)
        and error.orig.diag.constraint_name == PROCESSED_EVENTS_PKEY
    )


def store_event(
    session_factory: Callable[[], Session], result: BeforeCutoff | Event
) -> bool:
    """Write one event in one transaction. Return False if already processed."""

    drafts = result.drafts if isinstance(result, Event) else []
    try:
        with session_factory() as db, db.begin():
            # Flushed alone so that a duplicate fails before anything else runs.
            # A concurrent delivery blocks here until the other transaction ends.
            db.add(
                ProcessedEvent(
                    event_id=result.event_id,
                    event_type=result.event_type,
                    processed_at=datetime.now(timezone.utc),
                )
            )
            db.flush()
            db.add_all(
                Notification(
                    recipient_id=draft.recipient_id,
                    recipient_role=draft.recipient_role,
                    event_id=result.event_id,
                    order_id=result.order_id,
                    type=draft.type,
                    params=draft.params,
                    title=draft.title,
                    body=draft.body,
                    occurred_at=result.occurred_at,
                )
                for draft in drafts
            )
            db.flush()
            for recipient_id in dict.fromkeys(draft.recipient_id for draft in drafts):
                # NOTIFY takes no bind parameters. recipient_id is a parsed UUID,
                # so its text form cannot break out of the literal.
                db.execute(text(f"NOTIFY {NOTIFY_CHANNEL}, '{recipient_id}'"))
    except IntegrityError as error:
        if _is_duplicate_event(error):
            return False
        raise
    return True


def _log_outcome(
    outcome: str,
    result: BeforeCutoff | Ignore | Event,
    message: Message,
    *,
    notifications: int = 0,
) -> None:
    # %r because event_type comes from the record and may hold control characters.
    logger.info(
        "notification_event_%s event_id=%s event_type=%r order_id=%s "
        "notifications=%s topic=%s partition=%s offset=%s",
        outcome,
        result.event_id,
        result.event_type,
        result.order_id,
        notifications,
        message.topic(),
        message.partition(),
        message.offset(),
    )


def _log_failure(
    error: Exception, result: BeforeCutoff | Ignore | Event | None, message: Message
) -> None:
    logger.error(
        "notification_event_failed exception_type=%s sqlstate=%s event_id=%s "
        "event_type=%r order_id=%s topic=%s partition=%s offset=%s\n%s",
        type(error).__name__,
        getattr(getattr(error, "orig", None), "sqlstate", None),
        getattr(result, "event_id", None),
        getattr(result, "event_type", None),
        getattr(result, "order_id", None),
        message.topic(),
        message.partition(),
        message.offset(),
        "".join(traceback.format_tb(error.__traceback__)),
    )


def _apply(
    session_factory: Callable[[], Session],
    result: BeforeCutoff | Ignore | Event,
    message: Message,
) -> None:
    """Perform and log the database work for one valid record."""

    if isinstance(result, Ignore):
        _log_outcome("ignored", result, message)
    elif not store_event(session_factory, result):
        _log_outcome("duplicate", result, message)
    elif isinstance(result, BeforeCutoff):
        _log_outcome("before_cutoff", result, message)
    else:
        _log_outcome("stored", result, message, notifications=len(result.drafts))


def handle_message(
    session_factory: Callable[[], Session],
    consumer: CommittingConsumer,
    message: Message,
    *,
    start_at: datetime,
    stop: threading.Event,
) -> None:
    """Process one polled message, then synchronously commit its offset."""

    error = message.error()
    if error is not None:
        if error.fatal():
            logger.error("kafka_fatal_error reason=%s", error)
            raise WorkerAbort
        logger.error("kafka_poll_error reason=%s", error)
        return

    # A record polled while stopping is left for the next run.
    if stop.is_set():
        return

    result = None
    try:
        result = process_record(
            message.key(), message.value(), message.headers(), start_at=start_at
        )
        if isinstance(result, Malformed):
            logger.error(
                "notification_event_malformed reason=%s topic=%s partition=%s offset=%s",
                result.reason,
                message.topic(),
                message.partition(),
                message.offset(),
            )
            raise WorkerAbort

        _apply(session_factory, result, message)

        if stop.is_set():
            # The next run sees a duplicate, or reprocesses an ignored record.
            logger.info(
                "notification_offset_not_committed event_id=%s topic=%s "
                "partition=%s offset=%s",
                result.event_id,
                message.topic(),
                message.partition(),
                message.offset(),
            )
            return
        consumer.commit(message=message, asynchronous=False)
    except WorkerAbort:
        raise
    except Exception as failure:
        _log_failure(failure, result, message)
        raise WorkerAbort from None


def make_consumer(settings: WorkerSettings) -> Consumer:
    consumer = Consumer(
        {
            "bootstrap.servers": settings.kafka_bootstrap_servers,
            "group.id": CONSUMER_GROUP,
            "enable.auto.commit": False,
            "enable.auto.offset.store": False,
            "auto.offset.reset": "earliest",
        }
    )
    consumer.subscribe([ORDER_TOPIC])
    return consumer


def run(
    settings: WorkerSettings,
    stop: threading.Event,
    consumer: CommittingConsumer | None = None,
) -> None:
    """Consume until ``stop`` is set. Raise WorkerAbort on any failure."""

    engine = make_engine(settings.database_url)
    session_factory = make_session_factory(engine)
    consumer = consumer or make_consumer(settings)
    logger.info(
        "notification_worker_started topic=%s consumer_group=%s",
        ORDER_TOPIC,
        CONSUMER_GROUP,
    )
    try:
        while not stop.is_set():
            try:
                message = consumer.poll(POLL_TIMEOUT_SECONDS)
            except KafkaException as error:
                logger.error("kafka_fatal_error reason=%s", error)
                raise WorkerAbort from None
            if message is not None:
                handle_message(
                    session_factory,
                    consumer,
                    message,
                    start_at=settings.notifications_start_at,
                    stop=stop,
                )
    finally:
        consumer.close()
        engine.dispose()
    logger.info("notification_worker_stopped")


def main() -> None:
    settings = WorkerSettings.from_env()
    configure_logging(settings.log_level)
    stop = threading.Event()

    def request_stop(signum: int, _frame) -> None:
        logger.info("notification_worker_stopping signal=%s", signum)
        stop.set()

    signal.signal(signal.SIGTERM, request_stop)
    signal.signal(signal.SIGINT, request_stop)
    try:
        run(settings, stop)
    except WorkerAbort:
        logger.error("notification_worker_aborted")
        sys.exit(1)


if __name__ == "__main__":
    main()
