<!--
AI Assistance Disclosure:
Tool: Claude Code (model: claude-opus-5-5), date: 2026-11-04
Scope: Refactoring and documentation improvements — write the "Running tests" section covering setup, runs with and without TEST_DATABASE_URL, a throwaway PostgreSQL example, and a warning that the schema tests run alembic downgrade base (ai-20261104-001). The AI Use Summary section is a disclosure record.
Author review: Keith confirmed that all tests and manual verification were completed and approved, and confirmed rerunning the tests himself, with commands and results unspecified (ai-20261104-001).
Details: notification-service/ai/usage-log.md; ai-20261104-001
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
and worker tests run, and the PostgreSQL schema tests in
`tests/test_schema.py` are skipped. Run `pytest -rs` to list the skips.

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
and documentation improvements** for the step 2 database schema. The work
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
