# AI Assistance Disclosure:
# Tool: Claude Code (model: claude-opus-5-5), date: 2026-11-03
# Scope: Writing implementation code — write a test that the worker idles until its stop event is set.
# Author review: Keith confirmed review of all affected changes.
# Details: notification-service/ai/usage-log.md; ai-20261103-001
# Tool: Claude Code (model: claude-opus-5-5), date: 2026-11-04
# Scope: Writing implementation code; Debugging assistance — replace the idle test with consumer tests that need no database: configuration, poll errors, malformed records, ignored records, and SIGTERM; strengthen the stop test after a mutation survived (ai-20261104-003).
# Author review: Keith confirmed verification, with 551 tests passed on the Pytest suite (ai-20261104-003).
# Details: notification-service/ai/usage-log.md; ai-20261104-003

"""Worker tests that need neither Kafka nor a database."""

import logging
import os
import selectors
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path
from uuid import uuid4

import pytest
from confluent_kafka import KafkaException

from app import worker
from app.worker import WorkerAbort, handle_message, make_consumer, run
from tests.worker_support import (
    FakeConsumer,
    FakeError,
    FakeMessage,
    START_AT,
    make_settings,
    order_record,
)

SERVICE_ROOT = Path(__file__).resolve().parents[1]
# Parsed lazily, and nothing here should reach it.
UNREACHABLE_DB = "postgresql+psycopg://nobody@127.0.0.1:1/none"


def no_database():
    raise AssertionError("the database must not be used")


def handle(consumer, message, stop=None) -> None:
    handle_message(
        no_database, consumer, message, start_at=START_AT, stop=stop or threading.Event()
    )


def test_consumer_configuration(monkeypatch) -> None:
    created = {}

    class Recorder:
        def __init__(self, config) -> None:
            created["config"] = config

        def subscribe(self, topics) -> None:
            created["topics"] = topics

    monkeypatch.setattr(worker, "Consumer", Recorder)

    make_consumer(make_settings(UNREACHABLE_DB))

    assert created["topics"] == ["order.events"]
    assert created["config"] == {
        "bootstrap.servers": "unused:9092",
        "group.id": "notification-service-order",
        "enable.auto.commit": False,
        "enable.auto.offset.store": False,
        "auto.offset.reset": "earliest",
    }


def test_non_fatal_poll_error_is_logged_and_the_loop_continues(caplog) -> None:
    stop = threading.Event()
    bad = FakeMessage(None, None, None, error=FakeError(fatal=False))
    ignored = order_record("order.created", offset=7)
    consumer = FakeConsumer([bad, ignored], stop)

    with caplog.at_level(logging.ERROR):
        run(make_settings(UNREACHABLE_DB), stop, consumer)

    assert consumer.committed == [7]
    assert consumer.closed
    assert "kafka_poll_error reason=broker trouble" in caplog.text


def test_fatal_poll_error_stops_the_worker(caplog) -> None:
    stop = threading.Event()
    fatal = FakeMessage(None, None, None, error=FakeError(fatal=True))
    never_reached = order_record("order.created", offset=7)
    consumer = FakeConsumer([fatal, never_reached], stop)

    with caplog.at_level(logging.ERROR), pytest.raises(WorkerAbort):
        run(make_settings(UNREACHABLE_DB), stop, consumer)

    assert consumer.committed == []
    assert consumer.closed
    assert "kafka_fatal_error" in caplog.text


def test_exception_from_poll_stops_the_worker() -> None:
    stop = threading.Event()
    consumer = FakeConsumer([], stop)

    def failing_poll(timeout):
        raise KafkaException("poll failed")

    consumer.poll = failing_poll

    with pytest.raises(WorkerAbort):
        run(make_settings(UNREACHABLE_DB), stop, consumer)
    assert consumer.closed


def test_ignore_commits_and_logs_identifiers(caplog) -> None:
    consumer = FakeConsumer([], threading.Event())
    order_id, event_id = str(uuid4()), str(uuid4())
    message = order_record("order.created", order_id=order_id, event_id=event_id, offset=3)

    with caplog.at_level(logging.INFO):
        handle(consumer, message)

    assert consumer.committed == [3]
    assert consumer.commit_modes == [False]
    line = caplog.text
    for expected in (
        "notification_event_ignored",
        f"event_id={event_id}",
        "event_type='order.created'",
        f"order_id={order_id}",
        "topic=order.events",
        "partition=0",
        "offset=3",
    ):
        assert expected in line


def test_malformed_stops_without_committing_and_logs_no_contents(caplog) -> None:
    stop = threading.Event()
    secret = b'{"event_type": "SECRET-CONTENTS"}'
    message = FakeMessage(b"SECRET-KEY", secret, [("h", b"SECRET-HEADER")], offset=9)
    consumer = FakeConsumer([message], stop)

    with caplog.at_level(logging.DEBUG), pytest.raises(WorkerAbort):
        run(make_settings(UNREACHABLE_DB), stop, consumer)

    assert consumer.committed == []
    assert consumer.closed
    text = caplog.text
    assert (
        "notification_event_malformed reason=envelope.event_id: missing "
        "topic=order.events partition=0 offset=9"
    ) in text
    assert "SECRET" not in text


def test_control_characters_in_event_type_cannot_forge_log_lines(caplog) -> None:
    consumer = FakeConsumer([], threading.Event())
    message = order_record("order.x\nFORGED", offset=1)

    with caplog.at_level(logging.INFO):
        handle(consumer, message)

    assert consumer.committed == [1]
    assert "\nFORGED" not in caplog.text


def test_record_polled_while_stopping_is_left_uncommitted() -> None:
    stop = threading.Event()
    stop.set()
    consumer = FakeConsumer([], stop)

    # A handled type: no_database fails the test if the record is processed.
    handle(consumer, order_record("order.expired"), stop)

    assert consumer.commit_modes == []


def test_stop_set_during_processing_leaves_the_offset_uncommitted(monkeypatch) -> None:
    stop = threading.Event()
    consumer = FakeConsumer([], stop)
    real_log = worker._log_outcome

    def stop_while_processing(*args, **kwargs):
        stop.set()
        real_log(*args, **kwargs)

    monkeypatch.setattr(worker, "_log_outcome", stop_while_processing)

    handle(consumer, order_record("order.created"), stop)

    assert consumer.commit_modes == []


def test_sigterm_closes_the_consumer_and_exits_cleanly() -> None:
    """Run the real process against an unreachable broker."""

    environment = {
        **os.environ,
        "DATABASE_URL": UNREACHABLE_DB,
        "KAFKA_BOOTSTRAP_SERVERS": "127.0.0.1:1",
        "NOTIFICATIONS_START_AT": "2026-11-04T00:00:00+00:00",
        "LOG_LEVEL": "INFO",
        "PYTHONUNBUFFERED": "1",
    }
    process = subprocess.Popen(
        [sys.executable, "-m", "app.worker"],
        cwd=SERVICE_ROOT,
        env=environment,
        stderr=subprocess.PIPE,
        text=True,
    )
    try:
        with selectors.DefaultSelector() as selector:
            selector.register(process.stderr, selectors.EVENT_READ)
            deadline = time.monotonic() + 30
            started = ""
            while "notification_worker_started" not in started:
                assert time.monotonic() < deadline and selector.select(timeout=30)
                started = process.stderr.readline()
        process.send_signal(signal.SIGTERM)
        _, stderr = process.communicate(timeout=30)
    finally:
        process.kill()
        process.wait()

    assert process.returncode == 0
    assert "notification_worker_stopped" in stderr
