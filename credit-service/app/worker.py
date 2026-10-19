"""Relay credit outbox rows and consume keyed Kafka domain-event streams."""

import json
import logging
import os
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Protocol
from uuid import UUID

from confluent_kafka import Consumer, KafkaException, Message, Producer
from sqlalchemy import select
from sqlalchemy.exc import (
    DBAPIError,
    DisconnectionError,
    InterfaceError,
    OperationalError,
    TimeoutError as SQLAlchemyTimeoutError,
)
from sqlalchemy.orm import Session

from app.config import Settings, required_env
from app.db import make_engine, make_session_factory
from app.events import MalformedMessage, dump_event, parse_incoming_event
from app.messaging import (
    CREDIT_TOPIC,
    EVENT_STREAMS,
    PUBLISH_TIMEOUT_SECONDS,
    RELAY_BATCH_SIZE,
    RELAY_POLL_SECONDS,
    EventStream,
)
from app.models import OutboxEvent, utc_now
from app.services.credits import CreditDomainError
from app.services.event_handlers import apply_incoming_event

logger = logging.getLogger(__name__)

FailureCode = Literal[
    "MALFORMED_MESSAGE",
    "BUSINESS_RULE_VIOLATION",
    "TRANSIENT_RETRIES_EXHAUSTED",
    "UNEXPECTED_PROCESSING_ERROR",
]


@dataclass(frozen=True)
class DeliveryResult:
    """Decision and diagnostics produced by one source-record delivery."""

    disposition: Literal["ACK", "QUARANTINE"]
    attempts: int
    failure_code: FailureCode | None = None
    exception_type: str | None = None
    event_type: str | None = None
    event_id: UUID | None = None
    correlation_id: UUID | None = None
    order_id: UUID | None = None
    user_id: UUID | None = None


@dataclass(frozen=True)
class TransportDecision:
    """Routing decision made before invoking the strict domain parser."""

    action: Literal["PROCESS", "IGNORE", "QUARANTINE"]
    result: DeliveryResult | None = None


class Publisher(Protocol):
    def publish(self, event: OutboxEvent) -> None: ...


class _Delivery:
    """Delivery callback state for one Kafka produce call."""

    def __init__(self) -> None:
        self.error = None
        self.done = False

    def __call__(self, error, _message) -> None:
        self.error = error
        self.done = True


class KafkaPublisher:
    """Publish Credit events and quarantine records with broker confirmation."""

    def __init__(self, producer: Producer) -> None:
        self._producer = producer

    def publish(self, event: OutboxEvent) -> None:
        if event.order_id is None:
            raise ValueError("Credit events require an order_id Kafka key")
        self._produce_confirmed(
            topic=CREDIT_TOPIC,
            key=str(event.order_id).encode("utf-8"),
            value=dump_event(event),
            headers=[
                ("event_type", event.event_type.encode("utf-8")),
                ("event_id", str(event.event_id).encode("utf-8")),
            ],
        )

    def dead_letter(
        self,
        message: Message,
        *,
        dlq_topic: str,
        result: DeliveryResult,
    ) -> None:
        """Copy the exact failed record and append Credit diagnostics."""

        if result.disposition != "QUARANTINE" or result.failure_code is None:
            raise ValueError("Only failed deliveries can be quarantined")
        headers = list(message.headers() or [])
        headers.extend(
            [
                ("x-credit-failure-code", result.failure_code.encode("utf-8")),
                (
                    "x-credit-failed-at",
                    utc_now().isoformat().replace("+00:00", "Z").encode("utf-8"),
                ),
                ("x-credit-failed-attempts", str(result.attempts).encode("utf-8")),
                ("x-credit-source-topic", message.topic().encode("utf-8")),
                (
                    "x-credit-source-partition",
                    str(message.partition()).encode("utf-8"),
                ),
                ("x-credit-source-offset", str(message.offset()).encode("utf-8")),
            ]
        )
        self._produce_confirmed(
            topic=dlq_topic,
            key=message.key(),
            value=message.value(),
            headers=headers,
        )

    def _produce_confirmed(self, **record) -> None:
        delivery = _Delivery()
        self._producer.produce(**record, on_delivery=delivery)
        remaining = self._producer.flush(PUBLISH_TIMEOUT_SECONDS)
        if delivery.error is not None:
            raise KafkaException(delivery.error)
        if remaining or not delivery.done:
            raise RuntimeError("Kafka did not acknowledge the record")


def relay_once(db: Session, publisher: Publisher) -> int:
    """Publish outbox rows in order and mark each only after confirmation."""

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


def _delivery_result(
    *,
    disposition: Literal["ACK", "QUARANTINE"],
    attempts: int,
    event: object | None = None,
    body: bytes | None = None,
    failure_code: FailureCode | None = None,
    error: Exception | None = None,
) -> DeliveryResult:
    raw_event_type = None
    raw_event_id = None
    raw_correlation_id = None
    raw_order_id = None
    raw_user_id = None
    if event is None and body is not None:
        try:
            envelope = json.loads(body)
            payload = envelope.get("payload", {})
            if not isinstance(payload, dict):
                payload = {}
            candidate_type = envelope.get("event_type")
            if (
                isinstance(candidate_type, str)
                and len(candidate_type) <= 64
                and candidate_type.isprintable()
            ):
                raw_event_type = candidate_type
            raw_event_id = _safe_uuid(envelope.get("event_id"))
            raw_correlation_id = _safe_uuid(envelope.get("correlation_id"))
            raw_order_id = _safe_uuid(payload.get("order_id"))
            raw_user_id = _safe_uuid(payload.get("user_id"))
        except (AttributeError, TypeError, ValueError, json.JSONDecodeError):
            pass
    return DeliveryResult(
        disposition=disposition,
        attempts=attempts,
        failure_code=failure_code,
        exception_type=type(error).__name__ if error is not None else None,
        event_type=getattr(event, "event_type", raw_event_type),
        event_id=getattr(event, "event_id", raw_event_id),
        correlation_id=getattr(event, "correlation_id", raw_correlation_id),
        order_id=getattr(event, "order_id", raw_order_id),
        user_id=getattr(event, "user_id", raw_user_id),
    )


def _safe_uuid(value: object) -> UUID | None:
    try:
        return UUID(str(value))
    except (TypeError, ValueError, AttributeError):
        return None


def _rollback(db: Session | None) -> None:
    """Rollback without masking the failure that caused the rollback."""

    if db is None:
        return
    try:
        db.rollback()
    except Exception:
        logger.exception("credit_event_rollback_failed")


def _is_transient_infrastructure_failure(error: Exception) -> bool:
    if isinstance(
        error,
        (
            OperationalError,
            InterfaceError,
            DisconnectionError,
            SQLAlchemyTimeoutError,
        ),
    ):
        return True
    return isinstance(error, DBAPIError) and error.connection_invalidated


def _log_failure(result: DeliveryResult, error: Exception) -> None:
    logger.error(
        "credit_event_quarantined failure_code=%s attempts=%s "
        "exception_type=%s event_type=%s event_id=%s correlation_id=%s "
        "order_id=%s user_id=%s",
        result.failure_code,
        result.attempts,
        result.exception_type,
        result.event_type,
        result.event_id,
        result.correlation_id,
        result.order_id,
        result.user_id,
        exc_info=(type(error), error, error.__traceback__),
    )


def process_delivery(
    session_factory: Callable[[], Session],
    body: bytes,
    *,
    initial_allocation: int,
    retry_backoff_seconds: tuple[float, ...],
    sleep: Callable[[float], None] = time.sleep,
) -> DeliveryResult:
    """Process once, retry only infrastructure failures, or quarantine safely."""

    for attempt in range(len(retry_backoff_seconds) + 1):
        attempts = attempt + 1
        db = None
        event = None
        stage = "session"
        try:
            db = session_factory()
            stage = "parse"
            event = parse_incoming_event(body)
            stage = "domain"
            apply_incoming_event(db, event, initial_allocation=initial_allocation)
            stage = "commit"
            db.commit()
        except Exception as error:
            _rollback(db)
            transient = _is_transient_infrastructure_failure(error)
            if transient and attempt < len(retry_backoff_seconds):
                delay = retry_backoff_seconds[attempt]
                logger.warning(
                    "credit_event_transient_retry attempt=%s "
                    "retry_delay_seconds=%s exception_type=%s event_type=%s "
                    "event_id=%s correlation_id=%s",
                    attempts,
                    delay,
                    type(error).__name__,
                    getattr(event, "event_type", None),
                    getattr(event, "event_id", None),
                    getattr(event, "correlation_id", None),
                    exc_info=(type(error), error, error.__traceback__),
                )
                sleep(delay)
                continue

            if isinstance(error, MalformedMessage):
                failure_code: FailureCode = "MALFORMED_MESSAGE"
            elif isinstance(error, CreditDomainError) or (
                isinstance(error, ValueError) and stage == "domain"
            ):
                failure_code = "BUSINESS_RULE_VIOLATION"
            elif transient:
                failure_code = "TRANSIENT_RETRIES_EXHAUSTED"
            else:
                failure_code = "UNEXPECTED_PROCESSING_ERROR"
            result = _delivery_result(
                disposition="QUARANTINE",
                attempts=attempts,
                event=event,
                body=body,
                failure_code=failure_code,
                error=error,
            )
            _log_failure(result, error)
            return result
        else:
            return _delivery_result(
                disposition="ACK", attempts=attempts, event=event, body=body
            )
        finally:
            if db is not None:
                db.close()
    raise AssertionError("Retry loop exited without a delivery result")


def _decoded_headers(message: Message) -> dict[str, str]:
    decoded: dict[str, str] = {}
    for name, raw_value in message.headers() or []:
        if raw_value is None:
            raise MalformedMessage(f"Kafka header {name} has no value")
        try:
            decoded[name] = (
                raw_value.decode("utf-8")
                if isinstance(raw_value, bytes)
                else str(raw_value)
            )
        except UnicodeDecodeError as exc:
            raise MalformedMessage(f"Kafka header {name} is not UTF-8") from exc
    return decoded


def inspect_transport_record(
    stream: EventStream, message: Message
) -> TransportDecision:
    """Validate the common envelope/headers, then filter unrelated events."""

    body = message.value() or b""
    try:
        data = json.loads(body)
        if not isinstance(data, dict):
            raise MalformedMessage("Event envelope must be an object")
        required = {
            "event_id",
            "event_type",
            "schema_version",
            "occurred_at",
            "correlation_id",
            "payload",
        }
        if not required.issubset(data):
            raise MalformedMessage("Event envelope is incomplete")
        if type(data["schema_version"]) is not int or data["schema_version"] != 1:
            raise MalformedMessage("Unsupported event schema version")
        event_type = data["event_type"]
        if not isinstance(event_type, str) or not event_type.startswith(
            stream.event_prefix
        ):
            raise MalformedMessage("Event type does not belong on this topic")
        event_id = UUID(str(data["event_id"]))
        UUID(str(data["correlation_id"]))
        occurred_at = datetime.fromisoformat(
            str(data["occurred_at"]).replace("Z", "+00:00")
        )
        if occurred_at.tzinfo is None:
            raise MalformedMessage("occurred_at must include a timezone")
        payload = data["payload"]
        if not isinstance(payload, dict):
            raise MalformedMessage("Event payload must be an object")

        headers = _decoded_headers(message)
        if headers.get("event_type") != event_type:
            raise MalformedMessage("event_type header does not match the envelope")
        header_event_id = headers.get("event_id")
        if header_event_id is None or UUID(header_event_id) != event_id:
            raise MalformedMessage("event_id header does not match the envelope")

        key_value = payload.get(stream.key_field)
        if key_value is None or message.key() is None:
            raise MalformedMessage(f"Kafka record requires a {stream.key_field} key")
        expected_key = str(UUID(str(key_value))).encode("utf-8")
        if message.key() != expected_key:
            raise MalformedMessage("Kafka key does not match the event payload")
    except MalformedMessage as error:
        return TransportDecision(
            action="QUARANTINE",
            result=_delivery_result(
                disposition="QUARANTINE",
                attempts=1,
                body=body,
                failure_code="MALFORMED_MESSAGE",
                error=error,
            ),
        )
    except (TypeError, ValueError, json.JSONDecodeError) as error:
        malformed = MalformedMessage("Invalid common event envelope")
        malformed.__cause__ = error
        return TransportDecision(
            action="QUARANTINE",
            result=_delivery_result(
                disposition="QUARANTINE",
                attempts=1,
                body=body,
                failure_code="MALFORMED_MESSAGE",
                error=malformed,
            ),
        )

    if event_type not in stream.event_types:
        return TransportDecision(action="IGNORE")
    return TransportDecision(action="PROCESS")


def selected_stream() -> tuple[str, EventStream]:
    """Resolve the one Kafka stream assigned to this worker process."""

    name = os.getenv("CREDIT_EVENT_STREAM", "order").strip().lower()
    try:
        return name, EVENT_STREAMS[name]
    except KeyError as exc:
        allowed = ", ".join(sorted(EVENT_STREAMS))
        raise RuntimeError(f"CREDIT_EVENT_STREAM must be one of: {allowed}") from exc


def _handle_message(
    session_factory: Callable[[], Session],
    publisher: KafkaPublisher,
    consumer: Consumer,
    message: Message,
    *,
    stream: EventStream,
    initial_allocation: int,
    retry_backoff_seconds: tuple[float, ...],
) -> None:
    """Apply/skip/quarantine one record, then synchronously commit its offset."""

    error = message.error()
    if error is not None:
        if error.fatal():
            raise KafkaException(error)
        logger.error("kafka_poll_error", extra={"reason": str(error)})
        return

    decision = inspect_transport_record(stream, message)
    if decision.action == "IGNORE":
        logger.debug(
            "credit_event_ignored",
            extra={
                "topic": message.topic(),
                "partition": message.partition(),
                "offset": message.offset(),
            },
        )
        consumer.commit(message=message, asynchronous=False)
        return

    if decision.action == "QUARANTINE":
        outcome = decision.result
        assert outcome is not None
    else:
        outcome = process_delivery(
            session_factory,
            message.value() or b"",
            initial_allocation=initial_allocation,
            retry_backoff_seconds=retry_backoff_seconds,
        )

    if outcome.disposition == "QUARANTINE":
        logger.error(
            "credit_event_sent_to_dlq failure_code=%s attempts=%s "
            "topic=%s partition=%s offset=%s",
            outcome.failure_code,
            outcome.attempts,
            message.topic(),
            message.partition(),
            message.offset(),
        )
        publisher.dead_letter(
            message, dlq_topic=stream.dlq_topic, result=outcome
        )
    # Failed DLQ publication or database work raises before this point.
    consumer.commit(message=message, asynchronous=False)


def _relay(session_factory: Callable[[], Session], publisher: Publisher) -> None:
    db = session_factory()
    try:
        relay_once(db, publisher)
    except Exception:
        db.rollback()
        logger.exception("credit_outbox_relay_failed")
    finally:
        db.close()


def _client_config() -> dict[str, object]:
    return {"bootstrap.servers": required_env("KAFKA_BOOTSTRAP_SERVERS")}


def main() -> None:
    settings = Settings.from_env()
    logging.basicConfig(
        level=settings.log_level,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    stream_name, stream = selected_stream()
    engine = make_engine(settings.database_url)
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
            "group.id": stream.group_id,
            "enable.auto.commit": False,
            "enable.auto.offset.store": False,
            "auto.offset.reset": "earliest",
        }
    )
    consumer.subscribe([stream.topic])
    logger.info(
        "credit_worker_started event_stream=%s topic=%s consumer_group=%s",
        stream_name,
        stream.topic,
        stream.group_id,
    )
    try:
        while True:
            message = consumer.poll(RELAY_POLL_SECONDS)
            if message is not None:
                _handle_message(
                    session_factory,
                    publisher,
                    consumer,
                    message,
                    stream=stream,
                    initial_allocation=settings.initial_credit_allocation,
                    retry_backoff_seconds=settings.retry_backoff_seconds,
                )
            # Only the order worker relays credit.* results. This prevents
            # avoidable duplicate publication when User workers are scaled.
            if stream_name == "order":
                _relay(session_factory, publisher)
    finally:
        consumer.close()
        producer.flush(PUBLISH_TIMEOUT_SECONDS)
        engine.dispose()


if __name__ == "__main__":
    main()
