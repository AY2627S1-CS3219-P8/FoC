# AI Usage Log — Notification Service

## ai-20261103-001

- Recorded at: 2026-11-03T23:22:59+08:00
- Exchange time: Original per-message timestamps unavailable; assistance occurred on 2026-11-03 (Asia/Singapore).
- Source: Claude Code (model: claude-opus-5-5); shell, file read/write/edit, Docker, and pytest tools in the local workspace.
- Mode and scenario: Agentic implementation of the Notification Service skeleton and Docker Compose wiring from the user's specified requirements, with credit-service supplied as the conventions-only reference architecture. 
- Outcome: Retained the new `notification-service/` package (FastAPI API, idle worker, configuration, database helpers, Alembic layout with no revisions, Dockerfile, tests), four Compose services, the `notification-private` network, the `notification-db-data` volume, and `.env.example` placeholders. The initial `/ready` implementation was revised after it hung against a paused database; the retained version bounds the probe with a deadline. The agent also appended `NOTIFICATION_DB_USER` and a randomly generated `NOTIFICATION_DB_PASSWORD` to the user's local, git-ignored `.env` so Compose commands would resolve; that file is not part of the repository. No changes were made to frontend-service, order-service, credit-service, or the event broker. Nothing was committed.
- Verification: Agent checks only. `pytest` in `notification-service/` (scratchpad virtual environment): 18 passed initially, then 19 passed after the readiness fix. `docker compose config` succeeded, and a JSON comparison with the `HEAD` version of `compose.yaml` showed all existing services unchanged. Live stack: `notification-db` healthy, `notification-migrate` exited 0, `/health` and `/ready` returned 200; with the database stopped `/ready` returned 503 in about 0.01 s; with the database paused the first implementation hung until the 20 s curl limit, and after the fix returned 503 in about 3.0 s then about 0.005 s on repeat probes; `/ready` recovered to 200 after restart/unpause. Images run with empty or `mysql://` `DATABASE_URL` exited 3 (API) and 1 (worker) with `ConfigError` naming `DATABASE_URL`. No human rerun is claimed.
- Author review: Keith confirmed review of all affected changes. No human test rerun is claimed.
- Review confirmation recorded at: 2026-11-03T23:34:21+08:00
- Missing evidence: Original per-message timestamps unavailable. Intermediate assistant progress messages are not reproduced; Key response 2 is a verbatim excerpt of the final response (file list and closing note omitted). No redactions.
- Header exceptions: `notification-service/alembic/versions/.gitkeep` is a zero-byte placeholder kept empty so it only tracks the directory. The local `.env` (git-ignored secrets file, not in the repository) was not given a header.

### Prompt 1

```text
You are implementing the service skeleton and Docker Compose wiring for the
Notification Service in the FoC repository. Use the following specification
as your single source of truth. Do not make assumptions about any requirement
not listed here. If something needed is unspecified, stop and ask.

Overview:
Create a new Python FastAPI service in notification-service/. Package it as one
Docker image, foc-notification-service:local, used by these Compose services:
- notification-db: postgres:16-alpine, with a pg_isready health check;
- notification-migrate: runs "alembic upgrade head" and exits; there are no
  migrations yet;
- notification-service: the HTTP API;
- notification-worker: runs "python -m app.worker", which for now only
  starts, logs, and idles. Kafka consumption will be added later.
Add a new internal network, notification-private. Follow the structure and
Compose patterns of credit-service (app/main.py, app/config.py, app/db.py,
app/worker.py, Alembic layout, db/migrate/worker services) for conventions
only. Configuration is read from environment variables and validated at
startup. The API exposes GET /health and GET /ready.

Acceptance criteria:
- "docker compose up notification-service notification-worker" starts
  successfully. notification-db becomes healthy, and notification-migrate exits
  with code 0 before notification-service and notification-worker start.
- GET /health returns 200 without touching the database.
- GET /ready returns 200 when the database is reachable, and 503 within a few
  seconds when it is not. It never hangs.
- When a required environment variable is missing or invalid (e.g.
  DATABASE_URL), the API and the worker exit with a non-zero code and an error
  that names the variable.
- notification-service is published only on 127.0.0.1:8084 (container port
  8080). notification-db is on notification-private only and is not published.
- notification-service and notification-worker join both the default network and
  notification-private. notification-worker has restart: unless-stopped and its
  health check disabled, matching credit-order-worker.
- Database credentials come from .env with the ${VAR:?message} pattern used in
  compose.yaml, and no secrets are committed.
- "docker compose config" succeeds, and the existing services are unchanged.
- Automated tests cover /health, /ready (both states), and configuration
  validation.

Out of scope:
- Database tables, Kafka consumption, authentication, and any endpoint other
  than /health and /ready.
- Changes to frontend-service, order-service, credit-service, or the event
  broker.

Edge cases:
- The API starts while the database is still initialising. Use depends_on with
  service_healthy and service_completed_successfully.
- The database becomes unreachable after startup: /ready returns 503, and the
  process keeps running.
- Environment variables that are set but empty count as missing.
```

### Key response 1

Verbatim excerpt of the final response:

The Notification Service skeleton is in place and working under Docker Compose. Every acceptance criterion passed on the live stack, and all 19 tests pass.

**Results from the running stack:**
- **Startup:** `docker compose up notification-service notification-worker` starts cleanly. The database becomes healthy, the migration job exits with code 0, and then the API and worker start.
- **`/health`:** returns 200 and never touches the database. It stayed at 200 during database outages.
- **`/ready`:** returns 200 when the database is up. With the database stopped it returned 503 in under 10 ms. With the database frozen (`docker compose pause`) it returned 503 after 3 s. Both times it went back to 200 once the database recovered, and the process kept running throughout.
- **Bad configuration:** with `DATABASE_URL` empty or using the wrong scheme, the API exits with code 3 and the worker with code 1. Both print an error that names `DATABASE_URL`.
- **Compose:** `docker compose config` succeeds, and a comparison against the previous `compose.yaml` shows the existing services are unchanged. The API is published only on `127.0.0.1:8084` and the database has no published port.

**One fix during testing:** my first version of `/ready` hung when the database was frozen. The connection timeout only covers new connections, so a reused connection waited forever for a reply. The database check now has a hard 3-second limit. If an earlier check is still stuck, `/ready` returns 503 straight away rather than piling up more waiting checks. There's a test for this case.

**Decisions for you:**
- **Your `.env`:** I added the two new variables to your local `.env` with a random password. Without them, every `docker compose` command fails because of the required-variable checks. `.env` is git-ignored, so nothing secret is committed.
- **Configuration:** the only required variable is `DATABASE_URL`, which must use the `postgresql+psycopg://` scheme. `LOG_LEVEL` is optional, defaults to `INFO`, and is checked against the standard level names. I added no other variables because the spec didn't list any.

### Scope

- `.env.example`: Boilerplate generation — add placeholder `NOTIFICATION_DB_USER` and `NOTIFICATION_DB_PASSWORD` values.
- `compose.yaml`: Boilerplate generation — add `notification-db`, `notification-migrate`, `notification-service`, and `notification-worker` on the shared `foc-notification-service:local` image; `${VAR:?message}` credentials; `service_healthy`/`service_completed_successfully` gating; loopback-only `127.0.0.1:8084:8080`; `restart: unless-stopped` and disabled health check for the worker; the internal `notification-private` network; and the `notification-db-data` volume.
- `notification-service/.dockerignore`: Boilerplate generation — exclude caches, virtual environments, secrets, Git metadata, and tests from the build context.
- `notification-service/Dockerfile`: Boilerplate generation — package the API, worker, and Alembic files in one non-root image with a `/ready` health check and uvicorn entrypoint.
- `notification-service/README.md`: Disclosure record only — created to hold the final AI Use Summary; no attribution header required.
- `notification-service/ai/usage-log.md`: Disclosure record only — created to hold this entry.
- `notification-service/alembic.ini`: Boilerplate generation — configure the Alembic script location, import path, and logging.
- `notification-service/alembic/env.py`: Boilerplate generation — scaffold online/offline migration execution reading `DATABASE_URL`, failing with a named error when it is missing.
- `notification-service/alembic/script.py.mako`: Boilerplate generation — provide the revision template following credit-service conventions.
- `notification-service/alembic/versions/.gitkeep`: Boilerplate generation — keep the empty revisions directory tracked (header exception).
- `notification-service/app/__init__.py`: Boilerplate generation — mark the application package.
- `notification-service/app/config.py`: Writing implementation code — write settings that treat empty variables as missing, validate the `DATABASE_URL` scheme and `LOG_LEVEL`, and raise errors naming the variable.
- `notification-service/app/db.py`: Writing implementation code; Debugging assistance — write engine/session construction with bounded PostgreSQL connect and pool timeouts.
- `notification-service/app/main.py`: Writing implementation code; Debugging assistance — write the FastAPI factory with startup configuration validation, database-independent `/health`, and `/ready`; after an observed hang against a frozen database, add a single-flight readiness probe with a hard 3-second deadline.
- `notification-service/app/worker.py`: Writing implementation code — write a worker that validates configuration, logs startup, idles until SIGTERM/SIGINT, and exits non-zero on invalid configuration.
- `notification-service/pytest.ini`: Boilerplate generation — configure the test path and quiet output.
- `notification-service/requirements-dev.txt`: Boilerplate generation — add pytest and httpx test dependencies.
- `notification-service/requirements.txt`: Boilerplate generation — pin FastAPI, uvicorn, SQLAlchemy, Alembic, and psycopg.
- `notification-service/tests/conftest.py`: Boilerplate generation — add the service root to the test import path.
- `notification-service/tests/test_api.py`: Writing implementation code; Debugging assistance — write tests for `/health` without database access, `/ready` success, 503 after the database becomes unreachable, fast 503 for refused PostgreSQL connections, and bounded 503 for a hanging database.
- `notification-service/tests/test_config.py`: Writing implementation code — write tests for valid, missing, empty, whitespace-only, and wrong-scheme `DATABASE_URL`, `LOG_LEVEL` validation, API startup failure, and non-zero worker exit.
- `notification-service/tests/test_worker.py`: Writing implementation code — write a test that the worker idles until stopped.
- `README.md`: Disclosure record only — add the Notification Service entry to the root AI Use Summary.

### Usage summary

Claude Code built the Notification Service skeleton to the user's specification, reusing credit-service conventions for package layout, configuration, Alembic, image, and Compose patterns. Configuration validation, health/readiness endpoints, the idle worker, and their tests were written by the agent. Live testing exposed a readiness hang against a frozen database, which was diagnosed as pooled connections not covered by connect timeouts and fixed with a deadline-bounded, single-flight probe plus a regression test.

## ai-20261104-001

- Recorded at: 2026-11-04T13:03:13+08:00
- Exchange time: Original per-message timestamps unavailable; assistance occurred on 2026-11-04 (Asia/Singapore).
- Source: Claude Code; model claude-sonnet-5-5 for Prompt 1, and claude-opus-5-5 for Prompts 2 and 3. Shell, file read/write/edit, Docker, and pytest tools in the local workspace.
- Mode and scenario: Agentic implementation of Notification Service database schema (Prompt 1), followed by two rounds of user code-review feedback (Prompts 2 and 3) that the agent implemented. credit-service was used for conventions only (migration layout, model style, `TEST_DATABASE_URL`-gated PostgreSQL tests).
- Outcome: Retained everything: a new Alembic revision `20261104_0001`, new SQLAlchemy models with a `TimestampTZ` type that rejects naive datetimes, new PostgreSQL schema tests, the `app.models` import and UTC `connect_args` in `alembic/env.py`, a shared UTC `SESSION_OPTIONS` in `app/db.py`, and a "Running tests" README section. The agent chose the constraint and index names because the specification did not name them: `uq_notifications_event_recipient`, `ck_notifications_recipient_role`, `ix_notifications_recipient_id_desc`, and `ix_notifications_recipient_unread`. The agent fixed two of its own test bugs while running the tests. A NOT NULL test wrapped `commit` instead of `execute`. The UTC test reused a pooled connection, which an `ALTER DATABASE ... SET` does not affect; it now uses `NullPool`. All six review points in Prompts 2 and 3 were adopted. The migration keeps a literal CHECK expression rather than reading `RECIPIENT_ROLES`, so that the revision stays a fixed record of the schema. Attribution headers were first omitted in Prompt 1 because author review had not been confirmed; they were added by this disclosure update. Nothing was committed.
- Verification: Agent checks below, against a disposable `postgres:16-alpine` container in a scratchpad virtual environment.
  - Prompt 1: `alembic upgrade head`, `\d` output, `alembic check` ("No new upgrade operations detected"), `downgrade base`, and `upgrade head` succeeded. The first test run had 1 failure, a test bug that was then fixed. After the fix, 48 tests passed with the database, and 19 passed with 29 skipped without it. Mutation checks: the drift test detected an altered type and server default, and disabling the naive-datetime guard failed the naive tests.
  - Prompt 2: the first UTC test failed because of a test bug, which was fixed. Then 52 tests passed with the database and 19 passed with 33 skipped without it. Removing the UTC pin failed the UTC test.
  - Prompt 3: 53 tests passed with the database, and 19 passed with 34 skipped without it. Adding `"admin"` to `RECIPIENT_ROLES` left `alembic check` passing but failed the new tests, and removing `"courier"` failed the CHECK comparison test. With the database default set to `Asia/Singapore`, a temporary `env.py` probe (since removed) reported `UTC` for migration sessions and `Asia/Singapore` without the pin.
- Author review: The user stated on 2026-11-04: "All tests and manual verification has been completed and approved by Keith". The user then added: "Yes i reran the tests myself" (recorded at 2026-11-04T13:09:52+08:00). Keith therefore confirmed a human test rerun, with commands and results unspecified. This replaces the earlier note in this entry that no independent rerun was claimed.
- Review confirmation recorded at: 2026-11-04T13:03:13+08:00; human test rerun confirmation recorded at 2026-11-04T13:09:52+08:00
- Missing evidence: Original per-message timestamps unavailable. Intermediate assistant progress messages are not reproduced. Key responses are verbatim excerpts of the final response to each prompt. No redactions.
- Header exceptions: None.

### Prompt 1

```text
You are implementing the database schema for the Notification Service in the
FoC repository. Use the following specification as your single source of
truth. Do not make assumptions about any requirement not listed here. If
something needed is unspecified, stop and ask.

Overview:
Write one Alembic migration in notification-service/ and the matching
SQLAlchemy 2 models for two tables.

processed_events (one row per consumed Kafka event):
- event_id      uuid, primary key
- event_type    varchar(64), not null
- processed_at  timestamptz, not null

notifications (one row per recipient per event):
- id             bigserial, primary key
- recipient_id   uuid, not null. This is a User Service user ID; there is no
                 foreign key, because users live in another service.
- recipient_role varchar(16), not null, CHECK IN ('requester', 'courier')
- event_id       uuid, not null
- order_id       uuid, not null
- type           varchar(64), not null (the source event_type)
- params         jsonb, not null, default '{}'
- title          text, not null
- body           text, not null
- occurred_at    timestamptz, not null
- created_at     timestamptz, not null, default now()
- read_at        timestamptz, null (null means unread)
Constraints and indexes:
- UNIQUE (event_id, recipient_id)
- index on (recipient_id, id DESC)
- partial index on (recipient_id) WHERE read_at IS NULL

Acceptance criteria:
- "alembic upgrade head" creates both tables with exactly the columns, types,
  nullability, defaults, constraints, and indexes above.
- Inserting two notifications with the same (event_id, recipient_id) fails with
  a unique violation. The same event_id with a different recipient_id succeeds.
- Inserting a duplicate processed_events.event_id fails with a unique violation.
- recipient_role values other than 'requester' or 'courier' are rejected.
- The partial index predicate is exactly read_at IS NULL.
- "alembic downgrade base" removes both tables, and a following
  "alembic upgrade head" succeeds.
- The models match the migration: Alembic autogenerate against the migrated
  database produces no changes.
- Automated tests cover the constraints above against a real PostgreSQL
  database.

Out of scope:
- Any code that reads or writes these tables (consumer, API).
- A retention or purge job, and any delivery or outbox table.
- Seed data.

Edge cases:
- Timestamps are stored and returned with a timezone. A naive datetime must
  not be stored silently as local time.
- params accepts an empty object and nested JSON.
- Very long title or body values are allowed (text has no length limit).
```

### Key response 1

Verbatim excerpts of the final response; omitted passages (the "What changed", "Acceptance criteria", and "Things to check" sections) are marked […]:

The Notification Service schema is done. The migration creates both tables as specified, and the models match it.

The suite has 48 tests and all pass against a throwaway `postgres:16-alpine`. I removed that container afterwards. Without `TEST_DATABASE_URL`, the 19 existing tests pass and the 29 new schema tests skip, as in credit-service. I haven't committed anything.

[…]

`timestamptz` alone doesn't stop this: Postgres would read a naive value in the session time zone. The models use a small `TimestampTZ` type that raises `ValueError` when it is given a naive datetime. I checked that the tests fail without it.

This guard only covers writes through the models. Raw SQL can still bypass it.

[…]

### Prompt 2

```text
Found some issues:
1. In test_schema.py, test_event_type_and_type_length_limits should be split into separate tests. Once a commit fails, the session has to be rolled back before you can insert again, so one test cannot cleanly check both columns. Then catch DataError instead of any Exception for the 65 char test.
2. In app/models.py, RECIPIENT_ROLES constant is never used and the CHECK constraint repeats the values as a literal. Could you build the model's constraint from it?
3. Running schema tests is not documentated. A "Running tests" section could be added to the notification service README to cover situations like running tests without a database, with a database and warn readers that the tests run alembic downgrade base.
4. The session time could be pinned to UTC, so naive values that bypasses TimestampTZ is read as UTC instead of the server local time.
```

### Key response 2

Verbatim excerpts of the final response; omitted passages are marked […]:

I've fixed all four issues. The suite now has 52 tests and all pass against a fresh `postgres:16-alpine`. Without `TEST_DATABASE_URL`, the 19 non-database tests pass and the 33 schema tests skip. I stopped the container afterwards, and nothing is committed.

[…] I left the literal in the migration on purpose: a migration should keep describing the schema as it was when written, even if the constant changes later. A new role would need a new migration either way.

[…]

- **A mistake I fixed:** my first version reused a pooled connection, and `ALTER DATABASE ... SET` only affects new sessions. The check that the unpinned connection sees `Asia/Singapore` caught this, and the plain engine now opens a new connection each time.

[…]

### Prompt 3

```text
I noticed that:
- test_allowed_recipient_roles hardcodes ["requester", "courier"] and that Alembic autogenerate doesn't compare CHECK constraints.Suppose someone adds a role to RECIPIENT_ROLES but writes no migration. alembic check would pass, every test would pass, and the database would still reject the new role. To catch this, either parametrize that test with RECIPIENT_ROLES, or compare pg_get_constraintdef for ck_notifications_recipient_role against the constant
- alembic/env.py doesn't pass the same options in connect_args, so migrations still run in the server's default time zone
```

### Key response 3

Verbatim excerpts of the final response; omitted passages are marked […]:

Both gaps are closed. The suite has 53 tests and all pass against a fresh Postgres. Without a database, 19 pass and 34 skip. Nothing is committed.

[…]

- I also added the constraint comparison you suggested. `test_recipient_role_check_matches_model_constant` reads the role list from `pg_get_constraintdef` and checks it matches the constant exactly. The parametrized test can't catch a role removed from the constant without a migration, because the database would still accept it. The comparison catches both directions.

[…]

- There's no automated test for this one. Alembic builds its engine inside `env.py`, and nothing a migration writes reveals the session time zone. The probe was a one-off manual check.

[…]

### Scope

- `notification-service/alembic/versions/20261104_0001_notification_schema.py`: Writing implementation code — write the revision creating `processed_events` and `notifications` to the user-specified columns, types, nullability, defaults, CHECK, unique constraint, `(recipient_id, id DESC)` index, and `read_at IS NULL` partial index, with a downgrade dropping both tables.
- `notification-service/app/models.py`: Writing implementation code; Refactoring and documentation improvements — write SQLAlchemy 2 models matching the migration and a `TimestampTZ` type that rejects naive datetimes; refactor the CHECK constraint to be built from `RECIPIENT_ROLES` (Prompt 2).
- `notification-service/tests/test_schema.py`: Writing implementation code; Debugging assistance — write PostgreSQL schema tests for structure, constraints, the partial index predicate, autogenerate drift, JSON, long text, time zones, naive-datetime rejection, and the downgrade/upgrade round trip; fix two test bugs found while running them; split the varchar(64) tests and catch `DataError` (Prompt 2); add the UTC session test (Prompt 2); parametrize allowed roles with `RECIPIENT_ROLES` and compare `pg_get_constraintdef` with the constant (Prompt 3).
- `notification-service/app/db.py`: Writing implementation code — pin the PostgreSQL session time zone to UTC with a shared `SESSION_OPTIONS` connect option (Prompts 2 and 3).
- `notification-service/alembic/env.py`: Boilerplate generation — import `app.models` so autogenerate sees the tables (Prompt 1), and pass `SESSION_OPTIONS` in `connect_args` so migrations run in UTC (Prompt 3).
- `notification-service/README.md`: Refactoring and documentation improvements — write the "Running tests" section (Prompt 2); disclosure record — add the schema subsection to the AI Use Summary.
- `notification-service/ai/usage-log.md`: Disclosure record only — this entry.
- `README.md`: Disclosure record only — update the root AI Use Summary.

### Usage summary

Claude Code implemented the Notification Service database schema to the user's specification: one Alembic revision, matching models, and PostgreSQL-backed tests covering every acceptance criterion and edge case. It verified the work with mutation checks and a live migration round trip. Keith's two rounds of review produced six changes, all adopted: split length tests with `DataError`, a CHECK derived from the role constant plus a drift test against the database definition, test-run documentation, and a UTC session time zone for both the app engine and Alembic.

## ai-20261104-002

- Recorded at: 2026-11-04T17:29:19+08:00
- Exchange time: Original per-message timestamps unavailable; assistance occurred on 2026-11-04 (Asia/Singapore).
- Source: Claude Code (model: claude-opus-5-5); shell, file read/write/edit, clarifying-question, and pytest tools in the local workspace.
- Mode and scenario: Agentic implementation of event validation and translation, with `contracts/asyncapi.yaml`, `order-service/app/events.py`, and `order-service/app/services/orders.py` read as context but not changed. The agent paused to ask about three behaviours the specification left open, then implemented the user's answers. A follow-up prompt renamed the public function.
- Outcome: Retained `notification-service/app/events.py` and `notification-service/tests/test_events.py`. The user selected the agent's recommended option for all three questions: "1 credit is on hold" for the singular wording; a non-string `reason` is Malformed and an explicit null is null; the `event_id` header is compared to the envelope as a UUID. The agent also chose, and reported, the return types (`UUID` and aware `datetime`), the accepted UUID spellings (uppercase, no hyphens, braces, `urn:uuid:`), a required `T` separator in `occurred_at`, Malformed results for over-nested JSON and over-long integers, and reason strings that omit record contents. `parse_record` was renamed to `process_record` on request, with `_parse`, `ParseResult`, and the `parse_event` test helper left unchanged. The first test version failed because of a helper bug, which was fixed before retention. Nothing was committed.
- Verification: Agent checks only. First `tests/test_events.py` run: 414 passed, 2 failed (the test helper bug). After the fix: 416 passed in `tests/test_events.py`; full suite without `TEST_DATABASE_URL`: 435 passed, 34 skipped, 1 warning; `git diff --check` clean. Mutation checks on a scratch copy: 21 mutations applied and all caught by the tests; a 22nd listed pattern was not found in the source and so was not applied, although the script's summary line read "22 mutants, 0 survived". After the rename, the full suite was rerun with the same result (435 passed, 34 skipped, 1 warning), and the mutation checks were not repeated. The PostgreSQL schema tests were not run against a database for this work, because the new code does not touch them.
- Author review: Keith confirmed review ("My review is confirmed"). The confirmation does not state what was reviewed in detail. Keith also confirmed rerunning the tests ("I have also rerun the tests"), and stated the command as `.venv/bin/python -m pytest tests/test_events.py` and the result as 416 passed.
- Review confirmation recorded at: 2026-11-04T19:29:32+08:00; human test rerun confirmation recorded at 2026-11-04T19:30:57+08:00
- Missing evidence: Original per-message timestamps unavailable. Prompt 2 is the clarifying-question answer record as the tool returned it, not free-form text typed by the user. Intermediate assistant progress messages are not reproduced, and key responses are verbatim excerpts with omissions marked […].
- Header exceptions: None.

### Prompt 1

```text
You are implementing event validation and translation for the Notification
Service in the FoC repository. Use the following specification as your single
source of truth. Do not make assumptions about any requirement not listed here.
If something needed is unspecified, stop and ask.

Feature: Event validation and translation

Overview:
Write pure functions (no Kafka, database, or network access) that take one raw
Kafka record (key bytes, value bytes, headers) and return exactly one of:
- Malformed(reason): the record breaks the contract;
- Ignore: a valid record that produces no notifications;
- Event(event_id, event_type, occurred_at, order_id, drafts): drafts is a
  list, which may be empty.
Each draft contains recipient_id, recipient_role, type, params, title, and body.

1. Transport validation. Any failure means Malformed.
   - The value is a UTF-8 JSON object containing event_id, event_type,
     schema_version, occurred_at, correlation_id, and payload.
   - schema_version is the integer 1. A bool or string does not count.
   - event_id and correlation_id are UUIDs.
   - occurred_at is ISO-8601 with a timezone.
   - payload is an object.
   - event_type starts with "order.".
   - The headers event_type and event_id are present, are UTF-8, and match the
     envelope.
   - The Kafka key equals the canonical string form of payload.order_id, which
     is a UUID.
2. Filter. These types are handled: order.opened, order.rejected,
   order.accepted, order.picked_up, order.completed, order.cancelled,
   order.expired. Return Ignore for order.created and any other "order.*" type.
   Unknown payload fields are ignored.
3. Required fields per handled type. A missing or invalid field means
   Malformed.
   - All types: requester_id (UUID).
   - order.opened, order.completed: credit_amount (an integer of at least 1;
     not a bool).
   - order.completed: courier_id (UUID).
   - order.cancelled: cancelled_by (UUID) and previous_status (non-empty
     string). courier_id is optional.
   - Any type: if courier_id is present it must be a UUID, and it must not equal
     requester_id.
4. Recipients, params, and fallback text. The rule is to notify the other
   party, never the actor. Use "credit" when the amount is 1 and "credits"
   otherwise.
   - order.opened -> requester; params {credit_amount}; "Order is live" /
     "Your order is live. N credits are on hold."
   - order.rejected -> requester; params {reason}, where reason is the payload
     string passed through unchanged, or null if absent; "Order not placed" /
     "Your order couldn't be placed." Never put the reason in the text.
   - order.accepted -> requester; params {}; "Order accepted" /
     "A courier accepted your order."
   - order.picked_up -> requester; params {}; "Order picked up" /
     "Your order has been picked up."
   - order.completed -> courier; params {credit_amount}; "Order completed" /
     "Order completed. N credits will be added to your balance." It must never
     say the credits have been paid.
   - order.expired -> requester; params {}; "Order expired" /
     "Your order expired without a courier."
   - order.cancelled where cancelled_by == requester_id -> the courier only if
     courier_id is present, otherwise no drafts; params
     {cancelled_by_role: "requester", previous_status}; "Order cancelled" /
     "The requester cancelled this order."
   - order.cancelled where cancelled_by != requester_id -> requester, plus the
     courier if courier_id is present; params
     {cancelled_by_role: "admin", previous_status}; "Order cancelled" /
     "Your order was cancelled by an administrator." for the requester, and
     "This order was cancelled by an administrator." for the courier.
   params never contains raw actor UUIDs.

Acceptance criteria:
- Each of the seven handled types produces exactly the recipients, roles,
  params, and text above.
- order.created and an unknown "order.*" type return Ignore. An event_type
  without the "order." prefix returns Malformed.
- A cancellation by the requester with no courier returns Event with an empty
  draft list (not Ignore).
- Every transport and required-field rule above has a test proving it returns
  Malformed, with a reason that identifies the failed check.
- The functions perform no I/O. Tests run without Kafka or a database.
- Unit tests cover every item in this prompt.

Out of scope:
- Kafka consumption, offsets, database writes, DLQ publishing, and retries.
- The NOTIFICATIONS_START_AT cutoff. This will be added later, together with
  the consumer.
- Looking up names in other services, and translating or localising the text.

Edge cases:
- Uppercase or non-canonical UUID strings in the payload or key compare equal
  after canonicalisation.
- Invalid JSON, a JSON array, an empty value, or a non-UTF-8 value.
- Missing, duplicated, or non-UTF-8 headers.
- A Kafka key that is null.
- schema_version given as true, "1", or 2.
- credit_amount given as 0, negative, a float, a string, or true.
- occurred_at without a timezone.
- order.rejected with an empty reason string, which is passed through unchanged.
- order.cancelled where cancelled_by equals courier_id, which takes the admin
  branch because it is not the requester.
```

### Key response 1

Verbatim excerpt:

I've read the spec, the event contract and the Order Service emitter. The spec leaves three behaviours open, and you asked me to stop and ask about gaps, so I'm checking those before I write any code.

Summary (not a quotation): the agent then asked three multiple-choice questions, covering the `order.opened` body when `credit_amount` is 1, an `order.rejected` `reason` that is present but not a string, and whether an uppercase `event_id` header matches the envelope.

### Prompt 2

```text
Your questions have been answered: "The order.opened text is specified as "N credits are on hold.", and the singular rule only swaps credit/credits. What should the body say when credit_amount is 1?"=""1 credit is on hold" (Recommended)", "For order.rejected, the spec says reason is the payload string, or null if absent. What should happen when reason is present but isn't a string, such as 42 or an explicit JSON null? The Order Service always sends a string today, so this only affects off-contract records."="Non-string is Malformed, null is null (Recommended)", "The spec says the event_id header must "match the envelope", but its canonicalisation edge case only names the payload and the key. If the header is the uppercase form of the envelope's event_id, does it match?"="Compare as UUIDs (Recommended)". You can now continue with these answers in mind.
```

### Key response 2

Verbatim excerpts of the final response; omitted passages are marked […]:

Event validation and translation are done, in `app/events.py`, with `parse_record(key, value, headers)` as the entry point. All 416 new tests pass. The full suite without a database gives 435 passed, 34 skipped (the PostgreSQL schema tests) and 1 warning, which doesn't come from the new tests.

I also broke the code on purpose in 21 ways, such as accepting bools or skipping the key comparison, and the tests caught every one. Nothing is committed.

[…]

- **Courier as canceller:** when `cancelled_by` equals `courier_id`, the courier is told "This order was cancelled by an administrator", even though they did it. That follows your edge case, and it can only happen today if the courier is an admin, because the Order Service blocks other non-requesters.
- **`courier_id: null`:** an explicit null counts as present, so it's Malformed. The Order Service leaves the field out when there's no courier, so its records aren't affected.

**For future increments:** `reason` is passed through unchanged, so a value containing `\u0000` or a lone surrogate returns a normal `Event`. I'd expect the JSONB insert to reject it, though I haven't tested that, so the consumer should treat that failure as a bad record rather than retry it forever.

[…]

### Prompt 3

```text
Could you rename parse_record to process_record? This covers the definition and docstring in app/events.py (lines 9 and 95), plus the import, helpers and tests in tests/test_events.py. Do not change the behaviour. The private _parse can keep its name.
```

### Key response 3

Verbatim excerpts of the final response; omitted passages are marked […]:

I've renamed `parse_record` to `process_record` in `app/events.py` (lines 9 and 95) and at all 22 places it appears in `tests/test_events.py`, with no behaviour changes. No references to the old name remain anywhere else in the repo. The full suite without a database gives the same result as before: 435 passed, 34 skipped, 1 warning.

As you asked, `_parse` keeps its name. I also left two similar names alone, so tell me if you want either changed:

[…]

### Scope

- `notification-service/app/events.py`: Writing implementation code; Refactoring and documentation improvements — write pure functions, result dataclasses, and docstrings that validate a raw `order.events` record and translate it into notification drafts, to the user's specification and clarifying answers; rename `parse_record` to `process_record` (Prompt 3).
- `notification-service/tests/test_events.py`: Writing implementation code; Debugging assistance; Refactoring and documentation improvements — write unit tests for transport validation, the type filter, per-type required fields, UUID canonicalisation, recipients, params, text, and purity; fix a test helper bug found on the first run; rename `parse_record` to `process_record` (Prompt 3).
- `notification-service/README.md`: Disclosure record only — add the event validation subsection to the AI Use Summary.
- `notification-service/ai/usage-log.md`: Disclosure record only — this entry.
- `README.md`: Disclosure record only — update the root AI Use Summary.

### Usage summary

Claude Code implemented the event validation and translation of the Notification Service to the user's specification: one module of pure functions that classifies a raw Kafka record as Malformed, Ignore, or Event, with unit tests that need neither Kafka nor a database. Three gaps in the specification were put to the user before any code was written, and all three recommended options were selected. A later prompt renamed the public entry point without changing behaviour. Kafka consumption and database writes remain out of scope for this entry.

## ai-20261104-003

- Recorded at: 2026-11-04T20:40:17+08:00; completed 2026-11-05T09:23:43+08:00.
- Exchange time: Original per-message timestamps unavailable; assistance occurred on 2026-11-04 (Asia/Singapore).
- Source: Claude Code (model: claude-opus-5-5); shell, file read/write/edit, Docker, and pytest tools in the local workspace.
- Mode and scenario: Agentic implementation of the Notification Service Kafka consumer (happy path) from the user's specification, with `credit-service/app/worker.py` as the conventions reference.
- Outcome: Retained `app/events.py` (the `start_at` cutoff, `BeforeCutoff`, identifiers on `Ignore`), `app/config.py` (`WorkerSettings`), `app/worker.py` (the consumer), `requirements.txt`, root `compose.yaml` and `.env.example`, updated tests, and new `tests/worker_support.py` and `tests/test_worker_postgres.py`. The idle-worker test was replaced. The user's local `.env` was not changed. An existing Order Service TLS trust problem was reported and not fixed. Nothing was committed by the agent.
- Verification: Agent checks. With a disposable PostgreSQL 16 container, `pytest` in `notification-service/`: 551 passed, 1 warning. Without `TEST_DATABASE_URL`: 494 passed, 57 skipped, 1 warning. `tests/test_events.py`: 450 passed. Of 21 mutations, the tests caught 20; the survivor led to a stronger test, which then caught it. A live run of an isolated Compose project with real Kafka and the real Order, Credit, User, and Supplier services showed the expected rows for the order walkthrough and both cancellations, lag 0, unchanged counts after an offset reset, exit 0 on SIGTERM, 12 `processed_events` rows and no notifications with a later cutoff, and a malformed record stopping the worker with exit 1 and lag 1. That run used a verification-only override that made Order Service trust the development CA, because `compose.yaml` gives it no way to verify the User Service certificate. `LISTEN` timing, concurrent delivery, a crash before the offset commit, and the `\u0000` rollback were tested only against real PostgreSQL with a Kafka test double. A record with an over-long or NUL `event_type` before the cutoff was not tested.
- Author review: Keith stated "Verified by Keith, with 551 tests passed on the Pytest suite" (2026-11-05). The command and environment were not stated. No wider code review is recorded.
- Missing evidence: Original per-message timestamps unavailable. Intermediate assistant progress messages and parts of the final response are not reproduced; Key response 1 contains verbatim excerpts. No redactions.
- Header exceptions: None.

### Prompt 1

```text
You are implementing the Kafka consumer for the Notification Service in the
FoC repository. Use the following specification as your single source of
truth. Do not make assumptions about any requirement not listed here. If
something needed is unspecified, stop and ask.

Feature: Order event consumption (happy path)

Overview:
Implement the notification-worker loop (python -m app.worker) with
confluent-kafka. Subscribe to order.events with group.id
notification-service-order, enable.auto.commit=false,
enable.auto.offset.store=false, and auto.offset.reset=earliest. NOTIFICATIONS_START_AT is a required ISO-8601 setting with a timezone.

First, extend the existing pure function process_record in app/events.py.
Do not change any of its existing validation or translation rules.
- Add a keyword argument start_at (a timezone-aware datetime) and a new result
  BeforeCutoff(event_id, event_type, order_id).
- Add event_id, event_type, and order_id fields to Ignore. Malformed keeps only
  its reason.
- The order becomes:
  (a) the existing transport validation (envelope, schema_version, UUIDs,
      occurred_at with a timezone, payload object, "order." prefix, headers,
      key), where any failure is still Malformed;
  (b) if occurred_at < start_at, return BeforeCutoff;
  (c) the existing type filter (Ignore) and per-type validation and
      translation (Malformed or Event).
- The cutoff therefore applies to every record that passes (a), whatever its
  type and payload fields. Per-type fields are never checked for records
  before the cutoff.
- Update the existing tests that call process_record or compare against
  Ignore, and add tests for the cutoff and the new fields.

Then, for each record, in this order:
1. Call process_record with start_at = NOTIFICATIONS_START_AT.
   - BeforeCutoff: insert only a processed_events row and commit the offset. A
     unique violation means the event is already processed: commit the offset.
   - Ignore: commit the offset.
   - Malformed: log it and stop the worker without committing. (This will be
     replaced in the future with dead-letter queue handling. Until then, run
     this worker only against a topic known to contain no malformed records.)
2. For an Event, in one database transaction:
   - insert processed_events(event_id, event_type, processed_at);
   - insert one notifications row per draft, copying event_id, order_id, type,
     and occurred_at from the event;
   - run "NOTIFY notifications, '<recipient_id>'" once for each distinct
     recipient.
   If the processed_events insert hits a unique violation on event_id, roll
   back, treat the event as already processed, and commit the offset.
3. Commit the Kafka offset synchronously, and only after the transaction has
   committed.
Any exception while processing a record rolls back and stops the worker without
committing the offset, so the record is processed again after a restart. (This
will be replaced in the future with retries and dead-letter queue handling.)
Log every outcome with event_id, event_type, order_id, topic, partition, and
offset. A Malformed record may have no valid identifiers, so log its reason,
topic, partition, and offset instead, and never the record contents. Follow
credit-service/app/worker.py for conventions.

Acceptance criteria:
- Alice creates an order; Bob accepts it and picks it up; Alice completes it.
  The notifications table then contains, for Alice (requester), order.opened,
  order.accepted, and order.picked_up, and for Bob (courier), order.completed.
  There is no row for order.created.
- Cancelling an OPEN order as the requester creates no notification, but a
  processed_events row is written.
- Cancelling an ACCEPTED order as the requester creates one order.cancelled
  notification for the courier.
- Resetting the consumer group offsets to the earliest position and restarting
  the worker leaves the row count of notifications unchanged.
- Events before NOTIFICATIONS_START_AT produce processed_events rows and no
  notifications. This includes order.created and records with missing or
  invalid per-type fields (e.g. order.completed with no courier_id), which
  return BeforeCutoff, not Malformed.
- A record before the cutoff whose envelope, headers, or key is invalid still
  returns Malformed.
- Records at or after the cutoff are validated and translated exactly as before;
  all existing process_record tests still pass once updated for the new
  argument.
- A session running LISTEN notifications receives one notification per
  recipient, and only after the transaction commits.
- After processing, the consumer group has a lag of 0.
- Log lines for BeforeCutoff, Ignore, and Event outcomes include event_id,
  event_type, order_id, topic, partition, and offset. A log line for Malformed
  includes its reason, topic, partition, and offset, and no record contents.
- The worker shuts down cleanly on SIGTERM: it closes the consumer and leaves
  any in-progress record uncommitted.
- Integration tests cover these criteria against real PostgreSQL. Kafka may be
  a test double, provided the commit ordering is asserted.

Out of scope:
- Retries, the dead-letter queue, and failure classification. These will be
  added in the future.
- The HTTP API and the SSE stream.
- Consuming credit.events.

Edge cases:
- An event that produces zero drafts still writes processed_events and commits.
- One event with two recipients (an admin cancellation with a courier) writes
  two rows and runs NOTIFY once for each recipient.
- The same event is delivered twice, including concurrently after a rebalance:
  only one set of rows is created.
- The worker crashes after the database commit and before the offset commit: on
  restart the event is detected as a duplicate and skipped.
- Kafka poll errors that are not fatal are logged and the loop continues. Fatal
  errors stop the worker.
- occurred_at and NOTIFICATIONS_START_AT are compared as timezone-aware values.
- A record whose occurred_at equals NOTIFICATIONS_START_AT is not before the
  cutoff, so it is validated and translated.
- An order.rejected record whose reason contains \u0000 returns Event, and
  PostgreSQL rejects the insert with a DataError. The worker rolls back and stops
  without committing the offset, leaving no partial rows.
```

### Key response 1

Verbatim excerpts of the final response; omitted passages are marked […]:

The Kafka consumer is finished and meets the acceptance criteria, but it needs one change to your `.env` before Compose will run. Nothing is committed.

[…]

- **Your `.env`:** add `NOTIFICATIONS_START_AT` to it. Compose marks the value as required, so until it's set every `docker compose` command fails, not just the worker's. I left `.env` alone and added a placeholder to `.env.example`.
- **Existing bug in Order Service:** in Compose, every authenticated order request returns 503. Its `USER_SERVICE_URL` is HTTPS, but it has no way to trust the private CA. This isn't part of my change and I didn't fix it, so the walkthrough below will fail for you until it's fixed.

[…]

`LISTEN` timing, concurrent delivery, a crash before the offset commit, and the `\u0000` rollback were tested only against real PostgreSQL with a fake Kafka consumer.

[…]

- **Malformed records and restarts:** the worker does stop, but the existing `restart: unless-stopped` restarts it, and it fails on the same record each time. That matches "processed again after a restart", but it looks like a crash loop in `docker compose ps`.
- **Long event types before the cutoff:** a record with an `event_type` over 64 characters should fail the `varchar(64)` insert and stop the worker, as should a NUL in the type. I didn't test either case. After the cutoff, such types are just ignored.

[…]

- **Settings:** `NOTIFICATIONS_START_AT` and `KAFKA_BOOTSTRAP_SERVERS` are required only by the worker, so the API starts without them.
- **SIGTERM mid-record:** a transaction already running finishes, but its offset isn't committed. On restart the record is treated as a duplicate; an ignored record is simply processed again.
- **Failure logs:** these show the exception type, SQL state and stack frames, but not the exception message, because database errors can quote record contents.
- **`event_type` in logs:** it's written with quotes and escaping (`event_type='order.created'`) so a crafted value can't forge log lines.

### Scope

- `notification-service/app/events.py`: Writing implementation code — add the `start_at` keyword argument, the `BeforeCutoff` result, and identifiers on `Ignore`, and apply the cutoff between the transport check and the type filter, to the user's specification.
- `notification-service/app/config.py`: Writing implementation code — add worker-only `WorkerSettings` with `KAFKA_BOOTSTRAP_SERVERS` and a required timezone-aware `NOTIFICATIONS_START_AT`.
- `notification-service/app/worker.py`: Writing implementation code — replace the idle loop with the `order.events` consumer: one transaction per event with `NOTIFY`, a synchronous offset commit after it, duplicate detection, outcome logging, and stopping on malformed records, exceptions, fatal Kafka errors, and SIGTERM.
- `notification-service/tests/test_events.py`: Writing implementation code — pass `start_at` through a helper, compare `Ignore` with its new fields, and add cutoff tests.
- `notification-service/tests/test_config.py`: Writing implementation code — add tests for worker settings, `NOTIFICATIONS_START_AT` validation, and the API not needing either setting.
- `notification-service/tests/test_worker.py`: Writing implementation code; Debugging assistance — replace the idle test with consumer tests that need no database; strengthen the stop test after a mutation survived.
- `notification-service/tests/test_worker_postgres.py`: Writing implementation code — write integration tests against real PostgreSQL with a Kafka test double, covering the acceptance criteria, commit ordering, redelivery, concurrency, `LISTEN`/`NOTIFY`, and failures.
- `notification-service/tests/worker_support.py`: Writing implementation code — write the Kafka test doubles and record builders shared by the worker tests.
- `notification-service/requirements.txt`: Boilerplate generation — pin `confluent-kafka==2.16.0`, the version the other services use.
- `compose.yaml`: Boilerplate generation — configure `notification-worker` with `KAFKA_BOOTSTRAP_SERVERS` and a required `NOTIFICATIONS_START_AT`, and start it after `kafka-topics`.
- `.env.example`: Boilerplate generation — configure a placeholder `NOTIFICATIONS_START_AT`.
- `notification-service/README.md`: Refactoring and documentation improvements — write the Worker section and update the test skip description. The AI Use Summary is a disclosure record.
- `notification-service/ai/usage-log.md`: Disclosure record only — this entry.
- `README.md`: Disclosure record only — update the root AI Use Summary.

### Usage summary

Claude Code implemented the Notification Service Kafka consumer to the user's specification: a cutoff in the pure record classifier, worker settings, and a worker that stores each event in one transaction and commits its offset only afterwards. The work was tested against real PostgreSQL with a Kafka test double and in a live isolated Compose run. Retries, the dead-letter queue, the HTTP API, the SSE stream, and `credit.events` remain out of scope for this entry.

## ai-20261105-001

- Recorded at: 2026-11-05T10:04:23+08:00.
- Exchange time: Original per-message timestamps unavailable; assistance occurred on 2026-11-05 (Asia/Singapore).
- Source: Claude Code (model: claude-opus-5-5); shell, file read/write/edit, Docker, and pytest tools in the local workspace.
- Mode and scenario: Agentic implementation of Notification Service consumer retries and the dead-letter queue from the user's specification, with `credit-service/app/worker.py` as the conventions reference.
- Outcome: Changed `app/events.py` (`correlation_id` on `BeforeCutoff` and `Event`), `app/config.py` (`NOTIFICATION_RETRY_BACKOFF_SECONDS`), `app/worker.py` (classification, retries, DLQ publishing, commit ordering), root `compose.yaml` and `.env.example`, the service README, and tests. No validation or translation rule changed. The user's local `.env` was not changed. Nothing was committed by the agent. 
- Verification: Agent checks. With a disposable PostgreSQL 16 container, `pytest` in `notification-service/`: 625 passed, 1 warning. Without `TEST_DATABASE_URL`: 550 passed, 75 skipped, 1 warning. `tests/test_events.py`: 450 passed. The tests caught all 26 mutations applied to a scratch copy, in a run before one further `correlation_id` assertion was added. A live run of an isolated Compose project with real Kafka and PostgreSQL showed: malformed records (including a null key and a null header value) in the DLQ with the correct headers and lag 0; `\u0000` and lone-surrogate text in the DLQ as `UNEXPECTED_PROCESSING_ERROR` after one attempt; five attempts at 0.5, 1, 2, and 4 second delays with the database stopped, then `TRANSIENT_RETRIES_EXHAUSTED`; a notification created and nothing added to the DLQ when the database recovered within the window; SIGTERM during a 60-second backoff exiting at once with code 0 and no commit, with the record stored after a restart; and a failed DLQ write stopping the worker with code 1 and no commit, with the record stored after a restart. An empty backoff list was checked by unit test and by `docker compose config`, not in the live run.
- Author review: Keith stated on 2026-11-08, verbatim: "I ran `.venv/bin/python -m pytest -rs` in notification-service with TEST_DATABASE_URL set to a throwaware PostgreSQL 16 container and TEST_KAFKA_BOOTSTRAP_SERVERS set to a throwaway Kafka 4.1.2 broker set up with event-broker/create-topics.sh. The result was that 645 tests passed. The code has also been manually read and verified. Manual checks were performed where a Compose run was performed in an isolated project as well. All 4 uncommitted entries make up this increment." The "increment" is the four uncommitted entries ai-20261105-001, ai-20261106-001, ai-20261106-002, and ai-20261107-001, so the 645-passed run was of their combined working tree. The specific checks in the Compose run were not stated. This replaces the earlier note that review was pending and no human review or test rerun was claimed.
- Review confirmation recorded at: 2026-11-08T17:09:20+08:00
- Missing evidence: Original per-message timestamps unavailable. Intermediate assistant progress messages are not reproduced. Key responses are verbatim excerpts of the final responses, with omissions marked […]; they were added on 2026-11-08 as a correction, because this entry first omitted them although they were available. No redactions.
- Header exceptions: None.

### Prompt 1

```text
You are implementing consumer failure handling for the Notification Service in
the FoC repository. Use the following specification as your single source of
truth. Do not make assumptions about any requirement not listed here. If
something needed is unspecified, stop and ask.

Feature: Consumer retries and dead-letter queue

Overview:
Extend notification-worker so that a failed record is either retried or
quarantined to notification-service.order-events.dlq, and never blocks its
partition. Follow credit-service/app/worker.py (process_delivery,
KafkaPublisher.dead_letter) for conventions.
First, add a correlation_id field to the Event and BeforeCutoff results of
process_record in app/events.py, so failure logs can include it. Do not change
any validation or translation rule.
Classification:
- Malformed (from validation): no retry. DLQ with failure code
  MALFORMED_MESSAGE.
- Transient database or infrastructure errors (OperationalError,
  InterfaceError, DisconnectionError, SQLAlchemy TimeoutError, DBAPIError with
  connection_invalidated): roll back, then retry after each delay in
  NOTIFICATION_RETRY_BACKOFF_SECONDS (a comma-separated list of positive
  numbers, which may be empty; default "0.5,1,2,4"). When the delays run out, DLQ with
  TRANSIENT_RETRIES_EXHAUSTED.
- Any other exception: roll back, no retry. DLQ with
  UNEXPECTED_PROCESSING_ERROR. This includes a DataError from a value PostgreSQL
  cannot store in params.
DLQ record:
- the exact source key and value, and the original headers;
- plus x-notification-failure-code, x-notification-failed-at (UTC ISO-8601 with
  Z), x-notification-failed-attempts, x-notification-source-topic,
  x-notification-source-partition, and x-notification-source-offset.
Publish with an idempotent producer (acks=all) and wait for delivery
confirmation. Commit the source offset only after the DLQ write is confirmed.

Acceptance criteria:
- A malformed record produced to order.events appears in the DLQ with
  x-notification-failure-code MALFORMED_MESSAGE and the correct source
  partition and offset. Its offset is committed, and later records keep being
  processed.
- When the database is stopped while an event is processed, the logs show
  len(delays) + 1 attempts at the configured delays, then the record is sent to
  the DLQ as TRANSIENT_RETRIES_EXHAUSTED.
- When the database recovers within the retry window, the notification is
  created and nothing goes to the DLQ.
- A failed attempt never leaves partial rows. Every attempt is rolled back.
- If publishing to the DLQ fails, the worker raises without committing, so the
  record is processed again after a restart.
- A duplicate event_id (unique violation) is not a failure. It keeps the
  existing behaviour: roll back, treat the event as already processed, and
  commit the offset.
- An invalid NOTIFICATION_RETRY_BACKOFF_SECONDS stops the worker at startup
  with a clear error.
- Logs for failures include the failure code, the attempts, and the identifiers
  the record has (event_id, event_type, order_id, correlation_id), but not the
  full payload. A Malformed record may have no valid identifiers, so its log
  includes its reason, topic, partition, and offset instead.
- An order.rejected or order.cancelled record whose reason or previous_status
  contains \u0000 or a lone surrogate, and that produces at least one draft, goes
  to the DLQ as UNEXPECTED_PROCESSING_ERROR after one attempt, leaves no partial
  rows, and has its offset committed.
- Tests cover each failure class, including the unstorable text case against
  real PostgreSQL, the retry count and delays (with an injected sleep), the DLQ
  headers, and the commit ordering.

Out of scope:
- Tools to replay or inspect the DLQ.
- Alerting or metrics.
- Changes to the existing event validation and translation rules.

Edge cases:
- A record with a null key, or no headers, is copied to the DLQ as it is.
- The error is transient on early attempts and then non-transient: classify by
  the final error.
- An empty backoff list means a single attempt with no retries.
- The worker receives SIGTERM during a backoff sleep: it exits without
  committing.
```

### Key response 1

Verbatim excerpts of the final response; omitted passages are marked […]:

Consumer retries and the DLQ are implemented and working, and nothing is committed. With PostgreSQL the full suite has 625 passed. Without it, 550 passed and 75 skipped. The tests also caught all 26 bugs I deliberately introduced on a scratch copy.

[…]

- **`app/events.py`:** `correlation_id` is now on `Event` and `BeforeCutoff`. No validation or translation rule changed.
- **`app/config.py`:** adds `NOTIFICATION_RETRY_BACKOFF_SECONDS`. Unset uses the default, empty means one attempt, and anything invalid stops the worker at startup.
- **`app/worker.py`:** adds `process_delivery` (classification and retries) and `KafkaPublisher.dead_letter`. The offset is committed only after Kafka confirms the DLQ write.
- **Supporting files:** I also updated `compose.yaml`, `.env.example`, the service README's Worker section, the tests and the AI disclosure records. The disclosure headers say review is pending until you've looked at it.

[…]

Tell me if you want any of these changed:
- **SIGTERM outside a backoff sleep:** if the worker is already stopping when a record fails, that record skips the DLQ and stays uncommitted, so the next run retries it. Once a DLQ write is confirmed, the offset is committed even if a stop has arrived, which avoids a second DLQ copy.
- **Whitespace-only backoff value:** it counts as empty, so one attempt.
- **Log event rename:** `notification_event_malformed` is now `notification_event_failed` with `failure_code=MALFORMED_MESSAGE`, so anything searching for the old name needs updating.

[…]

- **Duplicate DLQ copies:** if the offset commit fails after a confirmed DLQ write, the record reaches the DLQ twice after restart. This follows from at-least-once delivery and is noted in the README.
- **Retry window limit:** keep total backoff well under Kafka's 5-minute `max.poll.interval.ms`. Past that, the partition is reassigned and the commit fails. This is also in the README.

### Scope

- `notification-service/app/events.py`: Writing implementation code — add `correlation_id` to the `BeforeCutoff` and `Event` results.
- `notification-service/app/config.py`: Writing implementation code — parse and validate `NOTIFICATION_RETRY_BACKOFF_SECONDS`.
- `notification-service/app/worker.py`: Writing implementation code — add failure classification, transient retries, an interruptible backoff sleep, the idempotent DLQ publisher, and commit ordering.
- `notification-service/tests/test_events.py`, `tests/test_config.py`, `tests/test_worker.py`, `tests/test_worker_postgres.py`, `tests/worker_support.py`: Writing implementation code — update tests that expected the worker to stop on failure, and cover each failure class, retry counts and delays, DLQ headers, commit ordering, and stopping.
- `compose.yaml`: Boilerplate generation — pass `NOTIFICATION_RETRY_BACKOFF_SECONDS` to `notification-worker`, keeping an empty value empty.
- `.env.example`: Boilerplate generation — add `NOTIFICATION_RETRY_BACKOFF_SECONDS`.
- `notification-service/README.md`: Refactoring and documentation improvements — update the Worker section. The AI Use Summary is a disclosure record.
- `notification-service/ai/usage-log.md`: Disclosure record only — this entry.
- `README.md`: Disclosure record only — update the root AI Use Summary.

### Usage summary

Claude Code implemented Notification Service consumer failure handling to the user's specification: a failed record is retried or copied to the DLQ, and its offset is committed only after Kafka confirms the DLQ write. The work was tested against real PostgreSQL with Kafka test doubles and in a live isolated Compose run. Tools to replay or inspect the DLQ, alerting, and metrics remain out of scope.

## ai-20261106-001

- Recorded at: 2026-11-06T08:24:27+08:00.
- Exchange time: Original per-message timestamps unavailable; assistance occurred on 2026-11-06 (Asia/Singapore).
- Source: Claude Code (model: claude-opus-5-5); shell, file read/write/edit, Docker, and pytest tools in the local workspace.
- Mode and scenario: Reproduce a user-reported restart cycle caused by records too large for the DLQ, ask the user about implementation choices, then fix it.
- Outcome: Changed `app/worker.py` (`message.max.bytes` of 1,100,000 on the DLQ producer, `kafka_error` on `notification_dlq_publish_failed`), `event-broker/create-topics.sh` (`max.message.bytes=1100000` on the DLQ topic through `--alter`), `event-broker/README.md`, the service README, and tests, with new `tests/test_worker_kafka.py`. Records compressed at source that still do not fit remain a documented limit, by the user's choice. Credit and Order Service were not changed. Nothing was committed by the agent. 
- Verification: Agent checks. Before the change, a live isolated Compose run with a default-client 999,900-byte malformed record restarted the worker 11 times in about 2.5 minutes, with no record processed and no error code in the logs. After the change, the same record and a 1,048,400-byte record reached the DLQ with no restarts and later records on both partitions were stored. Rerunning `kafka-topics` restored the limit on a topic whose setting had been removed, and a second rerun also exited 0. A 5 MB gzip record still caused restarts, logging `kafka_error=MSG_SIZE_TOO_LARGE`. `pytest` with PostgreSQL 16 and Kafka 4.1.2: 634 passed, 1 warning. With neither: 554 passed, 80 skipped, 1 warning. `tests/test_worker_kafka.py` passed three times in a row. The tests caught all 7 mutations applied to a scratch copy.
- Author review: Keith stated on 2026-11-08, verbatim: "I ran `.venv/bin/python -m pytest -rs` in notification-service with TEST_DATABASE_URL set to a throwaware PostgreSQL 16 container and TEST_KAFKA_BOOTSTRAP_SERVERS set to a throwaway Kafka 4.1.2 broker set up with event-broker/create-topics.sh. The result was that 645 tests passed. The code has also been manually read and verified. Manual checks were performed where a Compose run was performed in an isolated project as well. All 4 uncommitted entries make up this increment." The "increment" is the four uncommitted entries ai-20261105-001, ai-20261106-001, ai-20261106-002, and ai-20261107-001, so the 645-passed run was of their combined working tree. The specific checks in the Compose run were not stated. This replaces the earlier note that review was pending and no human review or test rerun was claimed.
- Review confirmation recorded at: 2026-11-08T17:09:20+08:00
- Missing evidence: Original per-message timestamps unavailable. Intermediate assistant progress messages are not reproduced. Key responses are verbatim excerpts of the final responses, with omissions marked […]; they were added on 2026-11-08 as a correction, because this entry first omitted them although they were available. Prompt 2 is the clarifying-question answer record as the tool returned it, not free-form text typed by the user; it replaces, as a correction made on 2026-11-08, a four-line summary that was earlier presented in a prompt block as if verbatim. No redactions.
- Header exceptions: None. Correction (2026-11-08): this line first listed `event-broker/create-topics.sh` and `event-broker/README.md` as exceptions, but both formats accept comments, so headers for this entry were added to them.

### Prompt 1

```text
Oversized bad records can stop the notification worker which will be unable to copy it to the dead letter queue, then exits and restarts in a cycle until someone manually removes the record. This can cause later records to not be processed.
Can we increase message.max.bytes on the producer and max.message.bytes on the DLQ topic which leaves more room for headers, log the Kafka error code when a DLQ publish fails, and test this edge case with a broker.
Verify that this is a real issue first, then ask me any questions about implementation before solving
```

### Key response 1

Verbatim excerpts of the final response; omitted passages are marked […]:

**This is a real issue.** I reproduced it with the real worker and broker, and I haven't changed any code. The verification stack is removed, and Docker Desktop is still running because I had to start it.

[…]

I produced a malformed 999,900-byte record to partition 0 with a default client, then good records to partitions 0 and 1:
- **Restart cycle:** the worker failed the DLQ write and aborted, then restarted 11 times in about 2.5 minutes.
- **Later records blocked:** nothing was processed (`processed_events` stayed at 0), and that included the good record on partition 1. So in this run it stalled more than just the bad record's partition.
- **Nothing in the logs says why:** they only show `exception_type=KafkaException`, not the `MSG_SIZE_TOO_LARGE` code.

[…]

- **Your two settings:** both are needed, and together they cover every uncompressed record the source topic accepts.
- **Compressed records:** these still get through. The broker checks a record's compressed size, but the worker sees it uncompressed. A 5 MB record passed at source; its DLQ copy failed at a 1.2 MB producer limit, and the broker still rejected it uncompressed at a 10 MB limit (DLQ topic limit 1.2 MB). It only went through with a 10 MB limit and gzip on the DLQ producer.

[…]

- **Existing topics:** `create-topics.sh` uses `--create --if-not-exists`, so a new `--config` wouldn't reach a DLQ topic that already exists.

[…]

Logging the error code needs no decision: I'll add `kafka_error=MSG_SIZE_TOO_LARGE` to the `notification_dlq_publish_failed` line. A flush timeout has no Kafka error code, so it would log `kafka_error=None`.

Summary (not a quotation): the agent then asked four multiple-choice questions, covering the size limit, records compressed at source, how the real-broker test runs, and how an existing DLQ topic gets the new limit.

### Prompt 2

```text
Your questions have been answered: "What limit should the DLQ producer's message.max.bytes and the DLQ topic's max.message.bytes use? The source topic accepts values up to about 1,048,500 bytes, and the DLQ headers add a few hundred bytes."="1,100,000 on both (Recommended)", "A record compressed at source can still be too large for the DLQ after raising the limits (a 5 MB gzip record was accepted by order.events), which would keep the worker in its restart cycle. How should that case be handled?"="Document the limit (Recommended)", "The Compose broker has no published port and advertises kafka:9092, so tests on the host can't reach it. How should the real-broker test for the oversized record run?"="Env-gated pytest (Recommended)", "create-topics.sh won't change the limit on a DLQ topic that already exists, such as one in an existing kafka-data volume. How should existing topics get the new limit?"="Alter in the script (Recommended)". You can now continue with these answers in mind.
```

### Key response 2

Verbatim excerpts of the final response; omitted passages are marked […]:

The restart cycle is fixed for uncompressed records: the record that used to trigger it now reaches the DLQ with no restarts, and later records keep flowing. A record compressed at source that's still too large will keep the worker cycling, which is the documented limit you chose. Nothing is committed.

With PostgreSQL and Kafka the full suite has 634 passed; with neither, 554 passed and 80 skipped. The tests also caught all 7 bugs I deliberately introduced on a scratch copy.

[…]

- **DLQ producer (`app/worker.py`):** `message.max.bytes` is now 1,100,000.
- **DLQ topic (`event-broker/create-topics.sh`):** `max.message.bytes=1100000` is applied with `--alter`, so existing topics get it at the next startup. A unit test checks the script and the worker use the same value.
- **Logging:** a failed publish now logs `notification_dlq_publish_failed kafka_error=MSG_SIZE_TOO_LARGE ...`. A flush timeout has no Kafka code, so it logs `kafka_error=None`.
- **Broker tests (`tests/test_worker_kafka.py`):** there are 5 tests, skipped unless `TEST_KAFKA_BOOTSTRAP_SERVERS` is set. They use the real producer and consumer, and the README has the throwaway-broker commands.
- **Docs:** I updated both READMEs and added disclosure entries, with author review marked pending.

[…]

- **Recovering from the compressed case:** someone still has to remove the record or move the consumer group's offset past it. The README says so, and a broker test pins this behaviour, so changing it later will fail that test on purpose.
- **Other services:** Credit and Order Service don't set `message.max.bytes` either, so they likely have the same restart cycle. I didn't test or change them.

[…]

- **Usage log:** "Prompt 2" in the new entry is a short summary of your four answers, not the exact wording of the question dialog. Edit it if your disclosure rules need the full text.

### Scope

- `notification-service/app/worker.py`: Writing implementation code — raise the DLQ producer's size limit and log the Kafka error code.
- `event-broker/create-topics.sh`: Boilerplate generation — set `max.message.bytes` on the DLQ topic, including a topic that already exists.
- `notification-service/tests/test_worker.py`: Writing implementation code — test the producer limit, the script's value, and the logged code.
- `notification-service/tests/test_worker_kafka.py`: Writing implementation code; Debugging assistance — write real-broker tests; fix a metadata race in a test helper and a test record that exceeded the source limit.
- `notification-service/README.md`, `event-broker/README.md`: Refactoring and documentation improvements — document the limit and the broker tests. The service README's AI Use Summary is a disclosure record.
- `notification-service/ai/usage-log.md`: Disclosure record only — this entry.
- `README.md`: Disclosure record only — update the root AI Use Summary.

### Usage summary

Claude Code confirmed the reported restart cycle on a real broker, measured where it occurs, and raised the DLQ size limits to the values the user chose, so that every uncompressed record the source topic accepts reaches the DLQ. Compressed source records that still do not fit are a documented limit.

## ai-20261106-002

- Recorded at: 2026-11-06T16:43:00+08:00.
- Exchange time: Original per-message timestamps unavailable; assistance occurred on 2026-11-06 (Asia/Singapore).
- Source: Claude Code (model: claude-opus-5-5); shell, file read/write/edit, Docker, and pytest tools in the local workspace.
- Mode and scenario: Agentic fix for a Notification Service worker hang when the database stops responding without returning an error, from the user's specification.
- Outcome: Changed `app/db.py` (a `worker_timeouts` option on `make_engine`), `app/worker.py` (uses it), the Worker section of the service README, and tests. The API's engine is unchanged. No client-side watchdog was added. No other service was changed. Nothing was committed by the agent.
- Verification: Agent checks. Real `lock_timeout` and `statement_timeout` errors were confirmed as SQLAlchemy `OperationalError` (`LockNotAvailable` 55P03, `QueryCanceled` 57014) and transient. Before the change, a network cut during a blocked insert in a live isolated Compose run gave no log line, DLQ write, or commit for 90 seconds. After the change, live runs showed: a network cut during a blocked insert reaching the DLQ as `TRANSIENT_RETRIES_EXHAUSTED` about 18 seconds later after 5 attempts; a network cut with an idle connection doing the same in about 8 seconds; the network returning within the window storing the notification with nothing added to the DLQ; a held lock retrying with sqlstate 55P03 and reaching the DLQ after about 33 seconds with no partial rows; a lock released within the window storing the notification; a stopped database behaving as before; and `docker pause` hanging the worker for 60 seconds, then Docker killing it (exit 137) with the offset uncommitted and the record stored after unpause and restart. `pytest` with PostgreSQL 16 and Kafka 4.1.2: 642 passed, 1 warning. With neither: 557 passed, 85 skipped, 1 warning. `tests/test_events.py`: 450 passed. The tests caught all 8 mutations applied to a scratch copy. The 72.5-second retry budget in the tests assumes each attempt ends at its first timeout; several statements in one attempt that each finish just under the limit could take longer.
- Author review: Keith stated on 2026-11-08, verbatim: "I ran `.venv/bin/python -m pytest -rs` in notification-service with TEST_DATABASE_URL set to a throwaware PostgreSQL 16 container and TEST_KAFKA_BOOTSTRAP_SERVERS set to a throwaway Kafka 4.1.2 broker set up with event-broker/create-topics.sh. The result was that 645 tests passed. The code has also been manually read and verified. Manual checks were performed where a Compose run was performed in an isolated project as well. All 4 uncommitted entries make up this increment." The "increment" is the four uncommitted entries ai-20261105-001, ai-20261106-001, ai-20261106-002, and ai-20261107-001, so the 645-passed run was of their combined working tree. The specific checks in the Compose run were not stated. This replaces the earlier note that review was pending and no human review or test rerun was claimed.
- Review confirmation recorded at: 2026-11-08T17:09:20+08:00
- Missing evidence: Original per-message timestamps unavailable. Intermediate assistant progress messages are not reproduced. Key responses are verbatim excerpts of the final responses, with omissions marked […]; they were added on 2026-11-08 as a correction, because this entry first omitted them although they were available. No redactions.
- Header exceptions: None.

### Prompt 1

```text
Fix a Notification Service worker hang when the database stops responding
without returning an error.

Problem:
The worker's retries and DLQ only react to database errors. Only opening a
connection has a timeout (connect_timeout=3 in app/db.py). If the network drops
silently or a query waits on a lock, the worker can wait indefinitely on an open
connection: no retries, no DLQ write, and the partition stays blocked. SIGTERM
only sets a stop flag, which isn't checked until the database call returns.

Fix:
Make these hangs raise normal database errors, so the existing retry and DLQ path
handles them.
1. Add TCP keepalives and tcp_user_timeout to detect a lost network. Start with
   keepalives=1, keepalives_idle=5, keepalives_interval=2, keepalives_count=3,
   tcp_user_timeout=10000 (milliseconds).
2. Add lock_timeout=5s and statement_timeout=10s to limit lock waits and slow
   queries.
3. Apply these settings to the worker only. make_engine is shared with the API,
   so add a worker-specific option and leave the API's behaviour unchanged.
4. Do not add a client-side watchdog.

Document:
In the Worker section of notification-service/README.md, state as a known
limitation that a frozen database server (for example, under docker pause) can
still hang the worker. The OS still answers TCP and the server can't enforce its
own timeouts. No data is lost, because the offset stays uncommitted and the record
is redelivered after a restart. Under Compose, Docker kills a worker that ignores
SIGTERM once its stop timeout runs out.

Also state that a long lock wait or database stall can now use up the retries and
send the record to the DLQ as TRANSIENT_RETRIES_EXHAUSTED, where it needs a manual
replay.

Acceptance criteria:
- With the network to the database cut (docker network disconnect) during
  processing, the worker logs retries and then sends the record to the DLQ as
  TRANSIENT_RETRIES_EXHAUSTED. If the network returns within the retry window, the
  notification is created and nothing goes to the DLQ.
- With a row or table lock held so that the insert blocks, the worker raises a
  lock timeout, retries it as transient, and leaves no partial rows.
- Confirm that lock and statement timeouts are classified as transient. If
  either isn't, stop and ask.
- The API's engine does not get these timeouts, and a test confirms it.
- A stopped database and all existing tests behave as before.
- Total retry time with the default backoff stays well under Kafka's 5-minute
  max.poll.interval.ms.

Out of scope:
- Handling a frozen server
- Changes to implementation in other services
```

### Key response 1

Verbatim excerpts of the final response; omitted passages are marked […]:

The hang is fixed for a lost network and for lock or statement waits: they now raise normal database errors and go through the existing retry and DLQ path. Nothing is committed. Lock and statement timeouts both classify as transient (`OperationalError`, sqlstate 55P03 and 57014), so I didn't need to stop and ask.

With PostgreSQL and Kafka the full suite has 642 passed; with neither, 557 passed and 85 skipped. The tests also caught all 8 bugs I deliberately introduced on a scratch copy.

[…]

- **`app/db.py`:** `make_engine(url, worker_timeouts=True)` adds your keepalive, `tcp_user_timeout`, `lock_timeout` and `statement_timeout` values. The default is off, so the API's engine is unchanged.
- **`app/worker.py`:** `run` passes `worker_timeouts=True`. There's no watchdog.
- **Docs and tests:** the README's Worker section has both limitations you specified, and the tests and disclosure records are updated.
- **API check:** tests confirm the API has none of these settings, both from the connection arguments and on a real connection (`SHOW lock_timeout` and `SHOW statement_timeout` return `0`).

[…]

- **Measured:** about 18s for a network cut and about 33s for a held lock. A stall on every attempt would take about 58s (calculated, not measured).
- **Upper figure:** a test holds the budget at 72.5s, which assumes each attempt ends at its first timeout and then has to reconnect.
- **Exception:** an attempt runs several statements, and the timeout applies to each one separately. If every statement in every attempt finished just under 10s, the total could approach 5 minutes. That's very unlikely. If it did happen, the commit would fail and the worker would restart and reprocess the record, so nothing is lost.

[…]

- **SIGTERM:** it's now noticed once the database call returns, within about 10s in these failure cases, but that can still be longer than Docker's stop timeout. If Docker kills the worker first, the offset stays uncommitted and the record is redelivered.

### Scope

- `notification-service/app/db.py`: Writing implementation code — add the worker-only timeout option.
- `notification-service/app/worker.py`: Writing implementation code — use the option.
- `notification-service/tests/test_worker.py`, `tests/test_worker_postgres.py`: Writing implementation code — test the settings on worker and API connections, real lock and statement timeouts, and the retry budget.
- `notification-service/README.md`: Refactoring and documentation improvements — document the timeouts and known limitations. The AI Use Summary is a disclosure record.
- `notification-service/ai/usage-log.md`: Disclosure record only — this entry.
- `README.md`: Disclosure record only — update the root AI Use Summary.

### Usage summary

Claude Code reproduced the hang on a real stack and gave the worker's connections the user's specified network and server-side timeouts, so that a lost network or long lock wait now follows the existing retry and DLQ path. A frozen server remains a documented limitation.

## ai-20261107-001

- Recorded at: 2026-11-07T15:42:02+08:00.
- Exchange time: Original per-message timestamps unavailable; assistance occurred on 2026-11-07 (Asia/Singapore).
- Source: Claude Code (model: claude-opus-5-5); shell, file read/write/edit, Docker, and pytest tools in the local workspace.
- Mode and scenario: Verify and apply a user-reported fix: `notification_offset_commit_failed` logged `failure_code=None` for a record already sent to the DLQ.
- Outcome: Changed `app/worker.py` to pass `outcome.failure_code` to the log, and `tests/test_worker.py` to assert the logged code. The user identified the defect and the fix. Behaviour other than this log field is unchanged. Nothing was committed by the agent.
- Verification: Agent checks. On a scratch copy, a failed offset commit logged `failure_code=None` for malformed, retries-exhausted, and unexpected records before the change and the real code after it, and `None` for stored and ignored records both times. With the defect restored on a scratch copy, 3 of the 5 offset-commit-failure tests failed; the other 2 cover records that have no failure code or do not read the log. `pytest` with PostgreSQL 16 and Kafka 4.1.2: 645 passed, 1 warning. With neither: 560 passed, 85 skipped, 1 warning. Kafka test doubles were used for the failed commit; it was not triggered on a live broker.
- Author review: Keith stated on 2026-11-08, verbatim: "I ran `.venv/bin/python -m pytest -rs` in notification-service with TEST_DATABASE_URL set to a throwaware PostgreSQL 16 container and TEST_KAFKA_BOOTSTRAP_SERVERS set to a throwaway Kafka 4.1.2 broker set up with event-broker/create-topics.sh. The result was that 645 tests passed. The code has also been manually read and verified. Manual checks were performed where a Compose run was performed in an isolated project as well. All 4 uncommitted entries make up this increment." The "increment" is the four uncommitted entries ai-20261105-001, ai-20261106-001, ai-20261106-002, and ai-20261107-001, so the 645-passed run was of their combined working tree. The specific checks in the Compose run were not stated. This replaces the earlier note that review was pending and no human review or test rerun was claimed.
- Review confirmation recorded at: 2026-11-08T17:09:20+08:00
- Missing evidence: Original per-message timestamps unavailable. Key response 1 is the full verbatim response to Prompt 1, and Key response 2 is the verbatim final response with its two section headings omitted; both were added on 2026-11-08 as a correction, because this entry first omitted them although they were available. No redactions.
- Header exceptions: None.

### Prompt 1

```text
If the offset commit fails after a record has gone to the DLQ, the log will say failure_code=None, even the record has a code. The worker hard-codes None instead of passing the code it already has at in line 455 of worker.py. 
Verify that changing the hardcoded None to outcome.failure_code allows this issue to be solved.
```

### Key response 1

Verbatim response:

**Yes, that change fixes it.** `worker.py:455` hard-codes `None`, and changing it to `outcome.failure_code` makes the log show the record's real code. I tested this on a scratch copy, so your working tree is unchanged and the fix still needs applying.

I made the offset commit fail for each kind of outcome, using Kafka test doubles rather than a real broker:

| Record | Sent to DLQ | Logged before | Logged after |
| --- | --- | --- | --- |
| Malformed | Yes | `failure_code=None` | `failure_code=MALFORMED_MESSAGE` |
| Retries exhausted | Yes | `failure_code=None` | `failure_code=TRANSIENT_RETRIES_EXHAUSTED` |
| Unexpected error | Yes | `failure_code=None` | `failure_code=UNEXPECTED_PROCESSING_ERROR` |
| Stored successfully | No | `failure_code=None` | `failure_code=None` (correct) |
| Ignored | No | `failure_code=None` | `failure_code=None` (correct) |

- **No side effects:** records that never failed still log `None`, because `outcome.failure_code` is `None` for them. The change only affects this log line, and `attempts` was already correct.
- **Test results:** with the change, the suite on the copy has 557 passed and 85 skipped. PostgreSQL and Kafka weren't running, so those 85 tests didn't run. They don't check this log line, so I don't expect them to be affected.
- **Test gap:** no existing test catches this bug. The only test that looks at this log line (`test_worker.py:753`) just checks that the event name appears, which is why it passed with `None`.

This was my mistake from the original DLQ work, and the bug matters most in this exact case. A failed commit means the record is reprocessed after restart and can reach the DLQ twice, and this log line is the clue that explains the duplicate.

Do you want me to apply it? I'd make the one-word change and add a test that a failed commit logs the real code for a DLQ record and `None` otherwise, then update the disclosure records.

### Prompt 2

```text
Apply
```

### Key response 2

Verbatim final response; the two section headings are omitted and marked […]:

The fix is applied: when the offset commit fails, `notification_offset_commit_failed` now logs the record's real failure code. Records that never failed still log `failure_code=None`. Nothing is committed.

[…]

- **`app/worker.py`:** the hard-coded `None` is now `outcome.failure_code`. The disclosure header I added pushed it from line 455 to line 459.
- **`tests/test_worker.py`:** tests now check the logged code for malformed, retries-exhausted and unexpected-error records, and `None` for a stored record. An ignored record logged `None` in the earlier scratch check but has no permanent test, since it takes the same code path as a stored one.
- **Disclosure records:** I added a new usage-log entry that credits you with finding the bug and the fix, and marks author review as pending.

[…]

- **Full suite:** 645 passed with PostgreSQL and Kafka, and 560 passed with 85 skipped without them.
- **Bug restored on a scratch copy:** 3 of the 5 offset-commit-failure tests fail, so this bug can't come back unnoticed. The other 2 don't depend on the code: one is the stored record, which logs `None` either way, and the other only checks the record wasn't sent to the DLQ.

The failed commit itself was only simulated with a Kafka test double, not triggered on a real broker. That doesn't affect this fix, since it only changes which value gets logged. All my test containers are removed, and Docker Desktop is still running.

### Scope

- `notification-service/app/worker.py`: Debugging assistance — log the record's failure code when the offset commit fails.
- `notification-service/tests/test_worker.py`: Writing implementation code — assert the logged code for each kind of record.
- `notification-service/README.md`: Disclosure record only — update the AI Use Summary.
- `notification-service/ai/usage-log.md`: Disclosure record only — this entry.
- `README.md`: Disclosure record only — update the root AI Use Summary.

### Usage summary

Claude Code verified the user's proposed one-word fix on a scratch copy, applied it, and added tests that fail if the defect returns.
