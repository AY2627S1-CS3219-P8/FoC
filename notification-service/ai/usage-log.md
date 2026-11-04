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
- Mode and scenario: Agentic implementation of Notification Service step 2 (database schema) from the user's specification (Prompt 1, the agent prompt in `notification-service/docs/implementation-steps.md`), followed by two rounds of user code-review feedback (Prompts 2 and 3) that the agent implemented. credit-service was used for conventions only (migration layout, model style, `TEST_DATABASE_URL`-gated PostgreSQL tests).
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
