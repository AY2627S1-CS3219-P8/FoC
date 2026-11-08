<!--
AI Assistance Disclosure:
Tool: Claude Code (model: claude-opus-5-5), date: 2026-11-04
Scope: Refactoring and documentation improvements — write the "Running tests" section covering setup, runs with and without TEST_DATABASE_URL, a throwaway PostgreSQL example, and a warning that the schema tests run alembic downgrade base (ai-20261104-001). The AI Use Summary section is a disclosure record.
Author review: Keith confirmed that all tests and manual verification were completed and approved, and confirmed rerunning the tests himself, with commands and results unspecified (ai-20261104-001).
Details: notification-service/ai/usage-log.md; ai-20261104-001
Tool: Claude Code (model: claude-opus-5-5), date: 2026-11-04
Scope: Refactoring and documentation improvements — write the "Worker" section covering required settings and failure behaviour, and update the "Running tests" skip description (ai-20261104-003).
Author review: Keith confirmed verification, with 551 tests passed on the Pytest suite (ai-20261104-003).
Details: notification-service/ai/usage-log.md; ai-20261104-003
Tool: Claude Code (model: claude-opus-5-5), date: 2026-11-05
Scope: Refactoring and documentation improvements — update the "Worker" section for retries and the dead-letter queue (ai-20261105-001).
Author review: Keith confirmed on 2026-11-08: full pytest suite with PostgreSQL 16 and Kafka 4.1.2, 645 passed; code manually read and verified; manual checks in an isolated Compose run (ai-20261105-001).
Details: notification-service/ai/usage-log.md; ai-20261105-001
Tool: Claude Code (model: claude-opus-5-5), date: 2026-11-06
Scope: Refactoring and documentation improvements — document the DLQ size limit and the real-broker tests (ai-20261106-001).
Author review: Keith confirmed on 2026-11-08: full pytest suite with PostgreSQL 16 and Kafka 4.1.2, 645 passed; code manually read and verified; manual checks in an isolated Compose run (ai-20261106-001).
Details: notification-service/ai/usage-log.md; ai-20261106-001
Tool: Claude Code (model: claude-opus-5-5), date: 2026-11-06
Scope: Refactoring and documentation improvements — document the worker's database timeouts and their known limitations (ai-20261106-002).
Author review: Keith confirmed on 2026-11-08: full pytest suite with PostgreSQL 16 and Kafka 4.1.2, 645 passed; code manually read and verified; manual checks in an isolated Compose run (ai-20261106-002).
Details: notification-service/ai/usage-log.md; ai-20261106-002
Tool: Claude Code (model: claude-opus-5-5), date: 2026-11-08
Scope: Refactoring and documentation improvements — write the "API" section and update the "Running tests" skip description (ai-20261108-001).
Author review: Keith confirmed on 2026-11-08: full pytest suite with PostgreSQL 16, 790 passed and 5 real-broker tests skipped; code read and verified; manual checks against the full Compose stack with the real User Service (ai-20261108-001).
Details: notification-service/ai/usage-log.md; ai-20261108-001
-->

# Notification Service

## Running tests

Install the development dependencies, then run pytest from this directory:

```sh
cd notification-service
python -m venv .venv
.venv/bin/pip install -r requirements-dev.txt
.venv/bin/python -m pytest
```

**Without a database.** If `TEST_DATABASE_URL` is unset, the API, configuration,
event, API authentication and validation, and Kafka-double worker tests run.
The PostgreSQL tests in `tests/test_schema.py`, `tests/test_worker_postgres.py`,
and `tests/test_notifications_postgres.py` are skipped. Run `pytest -rs` to list
the skips.

**With a database.** Set `TEST_DATABASE_URL` to an empty, disposable
PostgreSQL 16 database using the `postgresql+psycopg://` scheme. For example,
start a throwaway container:

```sh
docker run -d --rm --name notification-test-db \
  -e POSTGRES_PASSWORD=test -e POSTGRES_DB=notification_test \
  -p 127.0.0.1:55432:5432 postgres:16-alpine

TEST_DATABASE_URL=postgresql+psycopg://postgres:test@127.0.0.1:55432/notification_test \
  .venv/bin/python -m pytest

docker stop notification-test-db
```

> **Warning:** the schema tests run `alembic downgrade base` and
> `alembic upgrade head` against `TEST_DATABASE_URL`. They also delete every
> row in `notifications` and `processed_events`, and briefly change the
> database's default `timezone` setting. Never point `TEST_DATABASE_URL` at
> `notification-db` or any database whose data you need. As a safeguard, the
> tests refuse to start if the database contains tables other than
> `notifications`, `processed_events`, and `alembic_version`.

**With a broker.** The tests in `tests/test_worker_kafka.py` are skipped unless
`TEST_KAFKA_BOOTSTRAP_SERVERS` is set. The Compose broker publishes no port, so
start a throwaway broker that advertises a host address, then run
`event-broker/create-topics.sh` against it. These commands run from the repo root:

```sh
docker run -d --rm --name notification-test-kafka \
  -e KAFKA_NODE_ID=1 -e KAFKA_PROCESS_ROLES=broker,controller \
  -e KAFKA_LISTENERS=PLAINTEXT://:59092,CONTROLLER://:9093 \
  -e KAFKA_ADVERTISED_LISTENERS=PLAINTEXT://127.0.0.1:59092 \
  -e KAFKA_CONTROLLER_LISTENER_NAMES=CONTROLLER \
  -e KAFKA_LISTENER_SECURITY_PROTOCOL_MAP=CONTROLLER:PLAINTEXT,PLAINTEXT:PLAINTEXT \
  -e KAFKA_CONTROLLER_QUORUM_VOTERS=1@localhost:9093 \
  -e KAFKA_OFFSETS_TOPIC_REPLICATION_FACTOR=1 \
  -e KAFKA_TRANSACTION_STATE_LOG_REPLICATION_FACTOR=1 \
  -e KAFKA_TRANSACTION_STATE_LOG_MIN_ISR=1 \
  -e KAFKA_GROUP_INITIAL_REBALANCE_DELAY_MS=0 \
  -e KAFKA_AUTO_CREATE_TOPICS_ENABLE=false \
  -p 127.0.0.1:59092:59092 apache/kafka:4.1.2

# Repeat until the broker is up and this succeeds.
docker exec -i -e KAFKA_BOOTSTRAP_SERVERS=127.0.0.1:59092 \
  notification-test-kafka bash < event-broker/create-topics.sh

cd notification-service
TEST_KAFKA_BOOTSTRAP_SERVERS=127.0.0.1:59092 \
  .venv/bin/python -m pytest tests/test_worker_kafka.py

docker stop notification-test-kafka
```

Each test creates its own source topic and consumer group, and writes to the DLQ
topic. Use a disposable broker.

## API

The API needs these settings on top of `DATABASE_URL`. The worker doesn't use them.

| Variable | Purpose |
| --- | --- |
| `USER_SERVICE_URL` | HTTPS base URL of User Service. Compose sets `https://user-service:8080`. |
| `USER_SERVICE_CA_FILE` | CA file that verifies User Service's certificate. Compose mounts `${INTERNAL_CA_CERT_FILE:-./certs/ca.crt}` at `/run/tls/ca.crt`. |

Every `/notifications` endpoint needs `Authorization: Bearer <token>`, and the
scheme name is case-insensitive. The token is resolved through User Service
`GET /users/me`, as in Credit Service. A missing, malformed, or rejected token,
or an inactive user, returns 401 with `WWW-Authenticate: Bearer`. A timeout, an
unreachable User Service, or an unusable answer returns 503. Each endpoint only
sees the caller's own notifications, and no endpoint accepts a user ID.

| Endpoint | Result |
| --- | --- |
| `GET /notifications?cursor=&limit=` | `{"items": [...], "next_cursor": int \| null}`, newest first. `cursor` returns ids below it. `limit` is 1–100, default 20. |
| `GET /notifications/unread-count` | `{"count": int}` |
| `POST /notifications/{id}/read` | Sets `read_at` if it is null and returns the notification. Repeating keeps the first `read_at`. 404 if the notification isn't the caller's. |
| `POST /notifications/read-all` | `{"updated": int}`, the number of notifications it marked read. |

Each item has `id`, `type`, `recipient_role`, `params`, `title`, `body`,
`order_id`, `occurred_at`, `created_at`, and `read_at` (null while unread), with
timestamps in UTC. `/docs` shows one schema per `type` with its `params`. A
cursor above the newest id returns the newest page, and 0 or below returns an
empty page. A non-integer cursor, limit, or id, or a limit outside 1–100, returns
422. An id outside the `bigint` range returns 404 without a query.

Two requests that mark the same notification read both get 200 and the same
`read_at`. The update keeps an existing `read_at` with `COALESCE`, and the second
request waits for the first one's row lock.

## Worker

`python -m app.worker` consumes `order.events` as the consumer group
`notification-service-order`. It needs these settings on top of `DATABASE_URL`:

| Variable | Purpose |
| --- | --- |
| `KAFKA_BOOTSTRAP_SERVERS` | Kafka brokers. Compose sets `kafka:9092`. |
| `NOTIFICATIONS_START_AT` | Required ISO-8601 time with a timezone. Compose reads it from `.env`. Events before it are recorded in `processed_events` and create no notifications. |
| `NOTIFICATION_RETRY_BACKOFF_SECONDS` | Optional comma-separated positive delays, default `0.5,1,2,4`. A transient failure gets one retry after each delay. Empty means a single attempt. An invalid value stops the worker at startup. |

A failed record is retried or copied to `notification-service.order-events.dlq`,
so later records in its partition can continue. The exception is a DLQ write
that keeps failing, described below:

| Failure | Handling | `x-notification-failure-code` |
| --- | --- | --- |
| The record fails validation | No retry | `MALFORMED_MESSAGE` |
| Transient database error (`OperationalError`, `InterfaceError`, `DisconnectionError`, SQLAlchemy `TimeoutError`, or a `DBAPIError` with `connection_invalidated`) | Roll back and retry after each delay | `TRANSIENT_RETRIES_EXHAUSTED` once the delays run out |
| Anything else, such as text PostgreSQL can't store in `params` | Roll back, no retry | `UNEXPECTED_PROCESSING_ERROR` |

A duplicate `event_id` is not a failure: the event counts as already processed
and its offset is committed.

The DLQ record has the source key, value, and headers, plus
`x-notification-failure-code`, `x-notification-failed-at`,
`x-notification-failed-attempts`, `x-notification-source-topic`,
`x-notification-source-partition`, and `x-notification-source-offset`. The source
offset is committed only after Kafka confirms the DLQ write.

The worker stops with exit code 1 and leaves the offset uncommitted if the DLQ
write or the offset commit fails, or on a fatal Kafka error. The record is then
processed again after a restart, so a failed offset commit can put a second copy
in the DLQ. On SIGTERM the worker exits with code 0, also without committing a
record it has not finished, including during a backoff sleep.

The DLQ producer's `message.max.bytes` and the DLQ topic's `max.message.bytes` are
both 1,100,000 bytes, above the broker's default limit, so any uncompressed record
`order.events` accepts fits with the diagnostic headers. A record compressed at
source can still be too large, because the broker only checked its compressed
size. The DLQ write then fails, the worker logs
`notification_dlq_publish_failed kafka_error=MSG_SIZE_TOO_LARGE`, and it restarts
in a cycle with later records waiting until someone removes the record or moves
the group's offset past it. No service here produces such a record.

The worker's database connections turn a database that stops responding into a
normal error, which then follows the retry and DLQ path above. TCP keepalives and
`tcp_user_timeout` (10 seconds) detect a lost network, and `lock_timeout` (5
seconds) and `statement_timeout` (10 seconds) limit lock waits and slow queries.
The API's connections do not have these settings.

Known limitations:

- **A long lock wait or database stall can send a record to the DLQ.** It can use
  up the retries and send the record to the DLQ as `TRANSIENT_RETRIES_EXHAUSTED`,
  where it needs a manual replay.
- **A frozen database server can still hang the worker**, for example under
  `docker pause`. The OS still answers TCP and the server can't enforce its own
  timeouts. No data is lost, because the offset stays uncommitted and the record is
  redelivered after a restart. Under Compose, Docker kills a worker that ignores
  SIGTERM once its stop timeout runs out.
- **An `event_type` that doesn't fit `processed_events` goes to the DLQ if it is
  before the cutoff.** A type over 64 characters can't be stored, so the record goes
  to the DLQ as `UNEXPECTED_PROCESSING_ERROR`. No notification is lost, because a
  record before the cutoff never creates one. At or after the cutoff, an unknown type
  is skipped.

Keep the total retry time well under Kafka's `max.poll.interval.ms` (5 minutes by
default). Past that, the broker reassigns the partition and the offset commit
fails.

## AI Use Summary (Notification Service)

Claude Code (model: claude-opus-5-5) provided **Boilerplate generation**,
**Writing implementation code**, and **Debugging assistance** for the service
skeleton: the FastAPI app (`app/main.py`, `app/config.py`, `app/db.py`),
the idle worker (`app/worker.py`), Alembic layout, Dockerfile and dependency
files, tests under `tests/`, and Notification-related changes to root
`compose.yaml` and `.env.example`. Work followed the user's specification, with
credit-service used as the conventions-only reference. A readiness hang against
a frozen database was found during live testing and fixed with a
deadline-bounded probe; the original version was not retained.

Observed verification (agent only): 19 tests passed; `docker compose config`
succeeded with existing services unchanged; the live stack met the startup,
`/health`, `/ready` (reachable, stopped, paused, recovered), and
configuration-failure checks. Keith confirmed review of all affected changes; no human
test rerun is claimed.

See the [usage record](ai/usage-log.md#ai-20261103-001). Original per-message
timestamps are unavailable; no redactions. Header exception:
`alembic/versions/.gitkeep` (zero-byte directory placeholder).

### Database schema (ai-20261104-001)

Claude Code (model: claude-sonnet-5-5 for the first prompt, then
claude-opus-5-5 for two review follow-ups) provided **Writing implementation
code**, **Boilerplate generation**, **Debugging assistance**, and **Refactoring
and documentation improvements** for the database schema. The work
followed the user-specified schema: the Alembic revision
(`alembic/versions/20261104_0001_notification_schema.py`), the models
(`app/models.py`), the PostgreSQL schema tests (`tests/test_schema.py`), the
UTC session time zone in `app/db.py` and `alembic/env.py`, and this README's
"Running tests" section. All changes were retained. Keith's review raised six
issues, and all were adopted: split the varchar(64) tests and catch
`DataError`, build the CHECK from `RECIPIENT_ROLES`, document test runs, pin
the session time zone to UTC, catch role drift that autogenerate misses, and
apply the time zone to migrations. Two test bugs the agent found while running
the tests were fixed.

Observed verification (agent): the final run had 53 tests passing against a
disposable PostgreSQL 16 container, and 19 passing with 34 skipped without
`TEST_DATABASE_URL`. `alembic upgrade`, `downgrade base`, `upgrade`, and
`alembic check` succeeded. Mutation checks confirmed that the naive-datetime,
UTC-pin, and role-drift tests fail when their safeguard is removed. A
temporary probe showed migrations run in UTC. Author review: Keith confirmed that
all tests and manual verification were completed and approved, and confirmed
rerunning the tests himself, with commands and results unspecified.

See the [usage record](ai/usage-log.md#ai-20261104-001). Original per-message
timestamps are unavailable; no redactions; no header exceptions.

### Event validation and translation (ai-20261104-002)

Claude Code (model: claude-opus-5-5) provided **Writing implementation code**,
**Debugging assistance**, and **Refactoring and documentation improvements**: 
pure functions in `app/events.py` that classify a raw Kafka record as
Malformed, Ignore, or Event with notification drafts, and unit tests in
`tests/test_events.py`. The work followed the user's specification. Three gaps
were put to the user first, and the recommended option was selected for each:
singular "1 credit is on hold" wording, a non-string `reason` being Malformed
with an explicit null treated as null, and comparing the `event_id` header as a
UUID. All changes were retained, including a later requested rename of
`parse_record` to `process_record`. A test helper bug the agent found on the
first run was fixed.

Observed verification (agent only): 416 tests passed in `tests/test_events.py`;
the full suite without `TEST_DATABASE_URL` had 435 passed, 34 skipped, and 1
warning, before and after the rename. The tests caught all 21 mutations applied
before the rename. Author review: Keith confirmed review and confirmed
running `.venv/bin/python -m pytest tests/test_events.py`, with 416 passed.

See the [usage record](ai/usage-log.md#ai-20261104-002). Original per-message
timestamps are unavailable; no redactions; no header exceptions.

### Kafka consumer, happy path (ai-20261104-003)

Claude Code (model: claude-opus-5-5) provided **Writing implementation code**,
**Boilerplate generation**, **Debugging assistance**, and **Refactoring and
documentation improvements**: the `start_at` cutoff in `app/events.py`,
worker settings in `app/config.py`, the consumer in `app/worker.py`, the
confluent-kafka pin, Notification-related settings in root `compose.yaml` and
`.env.example`, tests under `tests/`, and the Worker section of this README. The
work followed the user's specification, with `credit-service/app/worker.py` as
the conventions reference. All changes were retained. A test was strengthened
after a mutation survived.

Observed verification (agent only): with PostgreSQL 16 the full suite had 551
passed and 1 warning; without `TEST_DATABASE_URL` it had 494 passed, 57 skipped,
and 1 warning. Of 21 mutations, the tests caught 20, and caught the last after
the test was strengthened. A live run of an isolated Compose project covered the
order walkthrough, both cancellations, offset reset, cutoff, SIGTERM, malformed
stop, and lag, using a verification-only workaround for Order Service TLS trust.
Author review: Keith confirmed verification, with 551 tests passed on the Pytest
suite; the command and environment were not stated. No wider code review is
recorded.

See the [usage record](ai/usage-log.md#ai-20261104-003). Original per-message
timestamps are unavailable; no redactions; no header exceptions.

### Consumer retries and dead-letter queue (ai-20261105-001)

Claude Code (model: claude-opus-5-5) provided **Writing implementation code**,
**Boilerplate generation**, and **Refactoring and documentation improvements**:
`correlation_id` in `app/events.py`, the backoff setting in `app/config.py`,
failure handling in `app/worker.py`, Notification-related settings in root
`compose.yaml` and `.env.example`, tests under `tests/`, and the Worker section of
this README. The work followed the user's specification, with
`credit-service/app/worker.py` as the conventions reference.

Observed verification (agent only): with PostgreSQL 16 the full suite had 625
passed and 1 warning; without `TEST_DATABASE_URL` it had 550 passed, 75 skipped,
and 1 warning. The tests caught all 26 mutations applied. A live run of an isolated
Compose project covered malformed records, unstorable text, retries running out,
recovery, SIGTERM during backoff, and a failed DLQ write.

Author review (confirmed by Keith on 2026-11-08, covering ai-20261105-001 to
ai-20261107-001 as one increment): Keith ran `.venv/bin/python -m pytest -rs` with
throwaway PostgreSQL 16 and Kafka 4.1.2 (topics from `event-broker/create-topics.sh`)
and 645 passed; manually read and verified the code; and ran manual checks in an
isolated Compose project. The specific Compose checks were not stated.

See the [usage record](ai/usage-log.md#ai-20261105-001). Original per-message
timestamps are unavailable; no redactions; no header exceptions.

### Oversized records and the DLQ (ai-20261106-001)

Claude Code (model: claude-opus-5-5) provided **Writing implementation code**,
**Boilerplate generation**, **Debugging assistance**, and **Refactoring and
documentation improvements**: the DLQ producer limit and Kafka error code logging in
`app/worker.py`, the topic limit in `event-broker/create-topics.sh`, tests under
`tests/`, and notes in this README and `event-broker/README.md`. The user reported the
issue, and chose the limit, the handling of compressed records, the test approach,
and the upgrade path for existing topics.

Observed verification (agent only): with PostgreSQL 16 and Kafka 4.1.2 the full suite
had 634 passed and 1 warning; with neither it had 554 passed, 80 skipped, and 1
warning. The tests caught all 7 mutations applied. A live run of an isolated Compose
project reproduced the restart cycle before the change, and showed the same records
reaching the DLQ with no restarts after it.

Author review (confirmed by Keith on 2026-11-08, covering ai-20261105-001 to
ai-20261107-001 as one increment): Keith ran `.venv/bin/python -m pytest -rs` with
throwaway PostgreSQL 16 and Kafka 4.1.2 (topics from `event-broker/create-topics.sh`)
and 645 passed; manually read and verified the code; and ran manual checks in an
isolated Compose project. The specific Compose checks were not stated.

See the [usage record](ai/usage-log.md#ai-20261106-001). Original per-message
timestamps are unavailable; no redactions; no header exceptions (a correction: the
`event-broker/` files now have headers).

### Database hang timeouts (ai-20261106-002)

Claude Code (model: claude-opus-5-5) provided **Writing implementation code**,
**Debugging assistance**, and **Refactoring and documentation improvements**: a
worker-only `make_engine` option in `app/db.py` with the user's specified keepalive,
`tcp_user_timeout`, `lock_timeout`, and `statement_timeout` values, its use in
`app/worker.py`, tests under `tests/`, and the Worker section of this README.

Observed verification (agent only): with PostgreSQL 16 and Kafka 4.1.2 the full suite
had 642 passed and 1 warning; with neither it had 557 passed, 85 skipped, and 1
warning. The tests caught all 8 mutations applied. A live run
of an isolated Compose project reproduced the hang before the change, and covered a
network cut, recovery, a held lock, a stopped database, and `docker pause` after it.

Author review (confirmed by Keith on 2026-11-08, covering ai-20261105-001 to
ai-20261107-001 as one increment): Keith ran `.venv/bin/python -m pytest -rs` with
throwaway PostgreSQL 16 and Kafka 4.1.2 (topics from `event-broker/create-topics.sh`)
and 645 passed; manually read and verified the code; and ran manual checks in an
isolated Compose project. The specific Compose checks were not stated.

See the [usage record](ai/usage-log.md#ai-20261106-002). Original per-message
timestamps are unavailable; no redactions; no header exceptions.

### Failure code on offset commit failures (ai-20261107-001)

Claude Code (model: claude-opus-5-5) provided **Debugging assistance** and **Writing
implementation code**: verified and applied the fix the user identified, so that
`notification_offset_commit_failed` logs the record's failure code, with tests in
`tests/test_worker.py`.

Observed verification (agent only): with PostgreSQL 16 and Kafka 4.1.2 the full suite
had 645 passed and 1 warning; with neither it had 560 passed, 85 skipped, and 1
warning. With the defect restored on a scratch copy, the new assertions failed.

Author review (confirmed by Keith on 2026-11-08, covering ai-20261105-001 to
ai-20261107-001 as one increment): Keith ran `.venv/bin/python -m pytest -rs` with
throwaway PostgreSQL 16 and Kafka 4.1.2 (topics from `event-broker/create-topics.sh`)
and 645 passed; manually read and verified the code; and ran manual checks in an
isolated Compose project. The specific Compose checks were not stated.

See the [usage record](ai/usage-log.md#ai-20261107-001). Original per-message
timestamps are unavailable; no redactions; no header exceptions.

### History and read-status API (ai-20261108-001)

Claude Code (model: claude-opus-5-5) provided **Writing implementation code**,
**Boilerplate generation**, and **Refactoring and documentation improvements**:
the User Service client and bearer-token dependency (`app/clients.py`,
`app/auth.py`, following Credit Service), API-only settings in `app/config.py`,
the DTO and per-type `params` schemas (`app/schemas.py`), the endpoints
(`app/routes/notifications.py`) and their wiring in `app/main.py`, the httpx pin,
the notification-service settings in root `compose.yaml`, tests under `tests/`,
and the API section of this README. The work followed the user's specification.

Observed verification (agent only): with PostgreSQL 16 the full suite had 790
passed and 5 skipped (the real-broker tests, with no Kafka); without a database it
had 668 passed and 127 skipped. EXPLAIN on a 20,300-row dataset showed the list
queries using `ix_notifications_recipient_id_desc`, the count and read-all using
`ix_notifications_recipient_unread`, and no sequential scan. The tests caught all 8
mutations applied. `docker compose config` succeeded. No live Compose run against
User Service was done by the agent.

Author review (confirmed by Keith on 2026-11-08): Keith ran
`.venv/bin/python -m pytest -rs` with a throwaway PostgreSQL 16 and 790 passed, with
the 5 real-broker worker tests skipped; read and verified the code; and ran manual
checks against the full Compose stack with the real User Service. The specific
Compose checks were not stated.

See the [usage record](ai/usage-log.md#ai-20261108-001). Original per-message
timestamps are unavailable; no redactions; no header exceptions.
