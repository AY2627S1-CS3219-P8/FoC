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
