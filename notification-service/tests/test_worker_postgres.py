# AI Assistance Disclosure:
# Tool: Claude Code (model: claude-opus-5-5), date: 2026-11-04
# Scope: Writing implementation code — write worker integration tests against real PostgreSQL with a Kafka test double, covering the acceptance criteria, commit ordering, redelivery, concurrency, LISTEN/NOTIFY, and failures (ai-20261104-003).
# Author review: Keith confirmed verification, with 551 tests passed on the Pytest suite (ai-20261104-003).
# Details: notification-service/ai/usage-log.md; ai-20261104-003

"""Worker integration tests: real PostgreSQL, with a Kafka test double.

Set TEST_DATABASE_URL (postgresql+psycopg://...) to a disposable database, as
for tests/test_schema.py. These tests migrate it and delete every row in
``notifications`` and ``processed_events``.
"""

import logging
import os
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID, uuid4

import psycopg
import pytest
from sqlalchemy import event, text

from app import worker
from app.db import make_engine, make_session_factory
from app.events import Event, NotificationDraft
from app.worker import WorkerAbort, handle_message, run, store_event
from tests.worker_support import (
    ADMIN,
    ALICE,
    BEFORE,
    BOB,
    START_AT,
    FakeConsumer,
    FakeMessage,
    make_settings,
    order_record,
)

SERVICE_ROOT = Path(__file__).resolve().parents[1]
TEST_DATABASE_URL = os.getenv("TEST_DATABASE_URL")

pytestmark = pytest.mark.skipif(
    not TEST_DATABASE_URL,
    reason="Set TEST_DATABASE_URL to run worker integration tests",
)


@pytest.fixture(scope="module")
def engine():
    assert TEST_DATABASE_URL is not None
    engine = make_engine(TEST_DATABASE_URL)
    with engine.connect() as connection:
        tables = set(
            connection.execute(
                text("SELECT tablename FROM pg_tables WHERE schemaname = 'public'")
            ).scalars()
        )
    unexpected = tables - {"alembic_version", "notifications", "processed_events"}
    if unexpected:
        engine.dispose()
        pytest.fail(
            f"TEST_DATABASE_URL is not a disposable database; found {sorted(unexpected)}"
        )
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=SERVICE_ROOT,
        env={**os.environ, "DATABASE_URL": TEST_DATABASE_URL},
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    yield engine
    engine.dispose()


@pytest.fixture(autouse=True)
def clean(engine):
    yield
    with engine.begin() as connection:
        connection.execute(text("DELETE FROM notifications"))
        connection.execute(text("DELETE FROM processed_events"))


@pytest.fixture
def session_factory(engine):
    return make_session_factory(engine)


@pytest.fixture
def listener():
    url = TEST_DATABASE_URL.replace("postgresql+psycopg://", "postgresql://", 1)
    with psycopg.connect(url, autocommit=True) as connection:
        connection.execute("LISTEN notifications")
        yield connection


def drain(listener) -> list[str]:
    return [item.payload for item in listener.notifies(timeout=0.5, stop_after=None)]


def counts(engine) -> tuple[int, int]:
    with engine.connect() as connection:
        return (
            connection.scalar(text("SELECT count(*) FROM processed_events")),
            connection.scalar(text("SELECT count(*) FROM notifications")),
        )


def notification_rows(engine) -> set[tuple[str, str, str]]:
    with engine.connect() as connection:
        rows = connection.execute(
            text("SELECT recipient_id, recipient_role, type FROM notifications")
        ).all()
    return {(str(recipient), role, type_) for recipient, role, type_ in rows}


def run_worker(messages, **consumer_kwargs) -> FakeConsumer:
    stop = threading.Event()
    consumer = FakeConsumer(messages, stop, **consumer_kwargs)
    run(make_settings(TEST_DATABASE_URL), stop, consumer)
    return consumer


def order_lifecycle(order_id: str | None = None) -> list[FakeMessage]:
    """Alice creates an order; Bob accepts and picks it up; Alice completes it."""

    order_id = order_id or str(uuid4())
    records = [
        ("order.created", {"credit_amount": 8}),
        ("order.opened", {"credit_amount": 8}),
        ("order.accepted", {"courier_id": BOB}),
        ("order.picked_up", {"courier_id": BOB}),
        ("order.completed", {"courier_id": BOB, "credit_amount": 8}),
    ]
    return [
        order_record(event_type, order_id=order_id, offset=offset, **fields)
        for offset, (event_type, fields) in enumerate(records)
    ]


def cancelled(cancelled_by: str, previous_status: str, **fields) -> FakeMessage:
    return order_record(
        "order.cancelled",
        cancelled_by=cancelled_by,
        previous_status=previous_status,
        **fields,
    )


# --- Acceptance: outcomes ---


def test_full_order_lifecycle_notifies_the_counterparty(engine) -> None:
    consumer = run_worker(order_lifecycle())

    assert notification_rows(engine) == {
        (ALICE, "requester", "order.opened"),
        (ALICE, "requester", "order.accepted"),
        (ALICE, "requester", "order.picked_up"),
        (BOB, "courier", "order.completed"),
    }
    assert counts(engine) == (4, 4)  # order.created is ignored
    assert consumer.committed == [0, 1, 2, 3, 4]
    assert consumer.commit_modes == [False] * 5
    assert consumer.closed


def test_columns_are_copied_from_the_event_and_draft(engine) -> None:
    order_id, event_id = str(uuid4()), str(uuid4())
    run_worker(
        [
            order_record(
                "order.completed",
                order_id=order_id,
                event_id=event_id,
                courier_id=BOB,
                credit_amount=1,
            )
        ]
    )

    with engine.connect() as connection:
        row = connection.execute(text("SELECT * FROM notifications")).mappings().one()
        processed = connection.execute(text("SELECT * FROM processed_events")).mappings().one()
    assert row["event_id"] == UUID(event_id)
    assert row["order_id"] == UUID(order_id)
    assert row["recipient_id"] == UUID(BOB)
    assert row["recipient_role"] == "courier"
    assert row["type"] == "order.completed"
    assert row["params"] == {"credit_amount": 1}
    assert row["title"] == "Order completed"
    assert row["body"] == "Order completed. 1 credit will be added to your balance."
    assert row["occurred_at"].isoformat() == "2026-11-04T00:30:00+00:00"
    assert processed["event_id"] == UUID(event_id)
    assert processed["event_type"] == "order.completed"
    assert processed["processed_at"] is not None


def test_cancelling_open_order_as_requester_writes_only_processed_event(
    engine, listener
) -> None:
    consumer = run_worker([cancelled(ALICE, "OPEN", offset=5)])

    assert counts(engine) == (1, 0)
    assert consumer.committed == [5]
    assert drain(listener) == []


def test_cancelling_accepted_order_as_requester_notifies_the_courier(engine) -> None:
    run_worker([cancelled(ALICE, "ACCEPTED", courier_id=BOB)])

    assert notification_rows(engine) == {(BOB, "courier", "order.cancelled")}
    with engine.connect() as connection:
        params = connection.scalar(text("SELECT params FROM notifications"))
    assert params == {"cancelled_by_role": "requester", "previous_status": "ACCEPTED"}


def test_admin_cancellation_with_courier_writes_two_rows_and_notifies_each(
    engine, listener
) -> None:
    run_worker([cancelled(ADMIN, "ACCEPTED", courier_id=BOB)])

    assert notification_rows(engine) == {
        (ALICE, "requester", "order.cancelled"),
        (BOB, "courier", "order.cancelled"),
    }
    assert drain(listener) == [ALICE, BOB]


# --- Acceptance: the cutoff ---


@pytest.mark.parametrize(
    ("event_type", "fields"),
    [
        pytest.param("order.created", {}, id="created"),
        pytest.param("order.opened", {"credit_amount": 8}, id="opened"),
        pytest.param("order.completed", {"credit_amount": 8}, id="completed-no-courier"),
        pytest.param("order.opened", {"credit_amount": "bad"}, id="invalid-amount"),
    ],
)
def test_events_before_the_cutoff_write_only_processed_events(
    engine, listener, caplog, event_type, fields
) -> None:
    event_id, order_id = str(uuid4()), str(uuid4())
    message = order_record(
        event_type, occurred_at=BEFORE, event_id=event_id, order_id=order_id, offset=4, **fields
    )

    with caplog.at_level(logging.INFO):
        consumer = run_worker([message])

    assert counts(engine) == (1, 0)
    assert consumer.committed == [4]
    assert drain(listener) == []
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT event_type FROM processed_events")) == event_type
    for expected in (
        "notification_event_before_cutoff",
        f"event_id={event_id}",
        f"event_type='{event_type}'",
        f"order_id={order_id}",
        "topic=order.events",
        "partition=0",
        "offset=4",
    ):
        assert expected in caplog.text


def test_duplicate_before_the_cutoff_commits_the_offset(engine) -> None:
    event_id = str(uuid4())
    first = order_record("order.created", occurred_at=BEFORE, event_id=event_id, offset=1)
    again = order_record("order.created", occurred_at=BEFORE, event_id=event_id, offset=2)

    consumer = run_worker([first, again])

    assert counts(engine) == (1, 0)
    assert consumer.committed == [1, 2]


def test_malformed_before_the_cutoff_stops_the_worker(engine) -> None:
    good = order_record("order.created", occurred_at=BEFORE)
    malformed = FakeMessage(None, good.value(), good.headers(), offset=6)
    stop = threading.Event()
    consumer = FakeConsumer([malformed], stop)

    with pytest.raises(WorkerAbort):
        run(make_settings(TEST_DATABASE_URL), stop, consumer)

    assert counts(engine) == (0, 0)
    assert consumer.committed == []


def test_record_at_the_cutoff_is_translated(engine) -> None:
    run_worker(
        [order_record("order.expired", occurred_at=START_AT.isoformat())]
    )

    assert notification_rows(engine) == {(ALICE, "requester", "order.expired")}


# --- Acceptance: redelivery and ordering ---


def test_replay_from_earliest_leaves_row_counts_unchanged(engine, listener) -> None:
    messages = order_lifecycle()
    run_worker(messages)
    before = counts(engine)
    assert sorted(drain(listener)) == sorted([ALICE, ALICE, ALICE, BOB])

    replay = run_worker(messages)

    assert counts(engine) == before
    assert replay.committed == [0, 1, 2, 3, 4]
    assert drain(listener) == []


def test_offset_is_committed_synchronously_only_after_the_transaction(
    engine,
) -> None:
    """Prove commit order from a separate connection, inside the Kafka commit."""

    seen = []

    def on_commit(message):
        seen.append((message.offset(), counts(engine)))

    messages = [
        order_record("order.opened", credit_amount=8, offset=0),
        order_record("order.accepted", courier_id=BOB, offset=1),
        order_record("order.created", offset=2),
        order_record("order.created", occurred_at=BEFORE, offset=3),
    ]
    consumer = run_worker(messages, on_commit=on_commit)

    assert seen == [(0, (1, 1)), (1, (2, 2)), (2, (2, 2)), (3, (3, 2))]
    assert consumer.commit_modes == [False] * 4


def test_crash_between_database_commit_and_offset_commit_is_a_duplicate_on_restart(
    engine, caplog
) -> None:
    message = order_record("order.expired", offset=2)
    stop = threading.Event()
    crashing = FakeConsumer([message], stop, commit_error=RuntimeError("broker gone"))

    with pytest.raises(WorkerAbort):
        run(make_settings(TEST_DATABASE_URL), stop, crashing)

    assert crashing.closed
    assert crashing.committed == []
    assert counts(engine) == (1, 1)

    with caplog.at_level(logging.INFO):
        restarted = run_worker([message])

    assert counts(engine) == (1, 1)
    assert restarted.committed == [2]
    assert "notification_event_duplicate" in caplog.text


def test_concurrent_deliveries_create_one_set_of_rows(engine, session_factory) -> None:
    message = cancelled(ADMIN, "ACCEPTED", courier_id=BOB, offset=3)
    barrier = threading.Barrier(8)
    consumers = [FakeConsumer([], threading.Event()) for _ in range(8)]
    failures = []

    def deliver(consumer):
        barrier.wait()
        try:
            handle_message(
                session_factory,
                consumer,
                message,
                start_at=START_AT,
                stop=threading.Event(),
            )
        except BaseException as error:  # noqa: BLE001 - reported on the main thread
            failures.append(error)

    threads = [threading.Thread(target=deliver, args=(c,)) for c in consumers]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=30)

    assert failures == []
    assert counts(engine) == (1, 2)
    assert [consumer.committed for consumer in consumers] == [[3]] * 8


def test_delivery_blocked_by_a_concurrent_transaction_becomes_a_duplicate(
    engine, session_factory
) -> None:
    result_event_id = uuid4()
    message = order_record("order.expired", event_id=str(result_event_id), offset=8)
    consumer = FakeConsumer([], threading.Event())
    holder = engine.connect()
    holder_transaction = holder.begin()
    holder.execute(
        text(
            "INSERT INTO processed_events (event_id, event_type, processed_at) "
            "VALUES (:event_id, 'order.expired', now())"
        ),
        {"event_id": result_event_id},
    )

    thread = threading.Thread(
        target=handle_message,
        args=(session_factory, consumer, message),
        kwargs={"start_at": START_AT, "stop": threading.Event()},
    )
    thread.start()
    try:
        deadline = time.monotonic() + 10
        blocked = 0
        while not blocked and time.monotonic() < deadline:
            with engine.connect() as connection:
                blocked = connection.scalar(
                    text(
                        "SELECT count(*) FROM pg_stat_activity "
                        "WHERE wait_event_type = 'Lock' AND datname = current_database()"
                    )
                )
        assert blocked == 1
        assert consumer.committed == []
    finally:
        holder_transaction.commit()
        holder.close()
        thread.join(timeout=10)

    assert consumer.committed == [8]
    assert counts(engine) == (1, 0)


# --- Acceptance: NOTIFY ---


def test_listener_gets_one_notification_per_recipient_only_after_commit(
    engine, session_factory, listener
) -> None:
    before_commit = []

    def check_before_commit(_session):
        before_commit.append(drain(listener))
        before_commit.append(counts(engine))

    event.listen(session_factory, "before_commit", check_before_commit)
    message = cancelled(ADMIN, "ACCEPTED", courier_id=BOB)
    consumer = FakeConsumer([], threading.Event())

    handle_message(
        session_factory, consumer, message, start_at=START_AT, stop=threading.Event()
    )

    assert before_commit == [[], (0, 0)]
    assert drain(listener) == [ALICE, BOB]


# --- Failures and stopping ---


def test_nul_in_reason_rolls_back_and_stops_without_committing(
    engine, listener, caplog
) -> None:
    message = order_record("order.rejected", reason="SECRET\u0000REASON", offset=11)
    stop = threading.Event()
    consumer = FakeConsumer([message], stop)

    with caplog.at_level(logging.DEBUG), pytest.raises(WorkerAbort):
        run(make_settings(TEST_DATABASE_URL), stop, consumer)

    assert counts(engine) == (0, 0)
    assert consumer.commit_modes == []
    assert consumer.closed
    assert drain(listener) == []
    assert "notification_event_failed exception_type=DataError" in caplog.text
    assert "offset=11" in caplog.text
    assert "SECRET" not in caplog.text


def test_failure_after_processed_event_insert_leaves_no_partial_rows(
    engine, monkeypatch, listener
) -> None:
    def failing_text(_statement):
        raise RuntimeError("boom")

    monkeypatch.setattr(worker, "text", failing_text)
    message = order_record("order.expired", offset=1)
    stop = threading.Event()
    consumer = FakeConsumer([message], stop)

    with pytest.raises(WorkerAbort):
        run(make_settings(TEST_DATABASE_URL), stop, consumer)

    monkeypatch.undo()
    assert counts(engine) == (0, 0)
    assert consumer.commit_modes == []
    assert drain(listener) == []


def test_other_unique_violation_is_not_treated_as_a_duplicate(
    engine, session_factory
) -> None:
    """Only the processed_events key means already processed."""

    draft = NotificationDraft(UUID(ALICE), "requester", "order.expired", {}, "t", "b")
    result = Event(
        event_id=uuid4(),
        event_type="order.expired",
        occurred_at=datetime.now(timezone.utc),
        order_id=uuid4(),
        drafts=[draft, draft],
    )

    with pytest.raises(Exception, match="uq_notifications_event_recipient"):
        store_event(session_factory, result)
    assert counts(engine) == (0, 0)


def test_sigterm_mid_record_keeps_the_transaction_but_not_the_offset(
    engine, monkeypatch, session_factory
) -> None:
    stop = threading.Event()
    consumer = FakeConsumer([], stop)
    real_store = worker.store_event

    def store_then_signal(*args):
        stored = real_store(*args)
        stop.set()
        return stored

    monkeypatch.setattr(worker, "store_event", store_then_signal)
    message = order_record("order.expired", offset=4)

    handle_message(session_factory, consumer, message, start_at=START_AT, stop=stop)

    assert counts(engine) == (1, 1)
    assert consumer.commit_modes == []


def test_outcome_log_includes_every_identifier(engine, caplog) -> None:
    event_id, order_id = str(uuid4()), str(uuid4())
    message = order_record("order.expired", event_id=event_id, order_id=order_id, offset=12)

    with caplog.at_level(logging.INFO):
        run_worker([message])

    for expected in (
        "notification_event_stored",
        f"event_id={event_id}",
        "event_type='order.expired'",
        f"order_id={order_id}",
        "notifications=1",
        "topic=order.events",
        "partition=0",
        "offset=12",
    ):
        assert expected in caplog.text
