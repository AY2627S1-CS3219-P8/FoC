# AI Usage Log — Supplier Service

## ai-20260929-001

- Recorded at: 2026-09-29T00:39:10+08:00
- Disclosure updated at: 2026-09-29T02:24:17+08:00
- Source: Codex (model: GPT-6); `functions.exec` for workspace inspection and edits; web tool for primary Alembic and PostgreSQL documentation.
- Mode and scenario: Guided implementation planning, SQLAlchemy/Alembic explanation, iterative review of user-authored checkpoint work, then agentic implementation of supplier database migrations, tests, access configuration, and commit preparation. At the user's request, work was committed as `1f9648a`.
- Outcome: Added the initial PostGIS schema and fixed-ID category seed revisions; Alembic configuration; migration integration fixtures and database rule tests; separate migration/runtime roles and grants; image and Compose wiring; and operational setup guidance. The model coordinate-index expression was aligned with the migration after a drift check identified a difference. The user authored guided checkpoint implementations and later authorized agentic completion. Commit `1f9648a` contains the implementation changes.
- Verification: Agent ran the supplier test suite against a disposable PostGIS 16 container with migration/runtime roles and an admin lifecycle URL: 54 passed, one existing Starlette/AnyIO deprecation warning. `alembic check` reported no new upgrade operations. Offline SQL rendering showed both migrations and fixed category inserts. Docker image build succeeded and reported `0002 (head)`. `docker compose --env-file .env.example config --quiet` and `git diff --check` succeeded. These are observed agent checks; no claim that a human reran them.
- Author review: The prior record states that Keith confirmed review of all affected implementation changes during the disclosure update. Earlier in the exchange, he reviewed incremental metadata wiring, migration SQL, and early integration tests through repeated `review` checkpoints, requested an implementation walkthrough, and authorized the implementation commit.

### Prompt 1

```text
Configure Alembic for Supplier Service using its existing settings, models, and SQLAlchemy/Psycopg stack. Explain the migration environment and provide the boilerplate needed for online migrations and offline SQL generation.

Files to edit:

- `supplier-service/alembic.ini` (new)
- `supplier-service/migrations/env.py` (new)
- `supplier-service/migrations/script.py.mako` (new)

Acceptance criteria:

- Load connection settings and all model metadata without embedding credentials.
- Resolve migration paths reliably, manage transactions, and release database connections after execution.
- Exclude PostGIS-owned objects from application schema comparisons.
- Provide a revision template that fails clearly when migration operations are unfinished.
- Explain metadata registration and the difference between executing migrations and generating SQL.
```

### Key response 1

The migration environment uses the service settings and registered model metadata. Online execution applies migrations inside a transaction and releases the connection; offline execution emits SQL without connecting. Configuration paths are relative to the service configuration file, and credentials remain external.

The revision template provides the migration structure and fails clearly for unfinished operations. The comparison filter excludes PostGIS's spatial reference table so autogeneration does not propose removing extension-managed data.

### Prompt 2

```text
Create the initial migration for `category`, `supplier`, and `supplier_category` on PostgreSQL 16 with PostGIS. Derive the schema from the existing models and documented requirements, explain the database rules, and review generated SQL for correctness.

Files to edit:

- `supplier-service/migrations/versions/0001_initial_schema.py` (new)
- `supplier-service/app/models.py`

Acceptance criteria:

- Enable PostGIS before creating geographic columns and preserve the agreed column types, defaults, and nullability.
- Enforce nonblank names, positive record versions, case-insensitive category uniqueness, valid assignments, and restricted deletion of referenced categories.
- Allow opening hours to be entirely absent or complete, with a duration greater than zero and at most 24 hours; reject partial schedules.
- Add active-listing and category-lookup indexes, exactly one spatial index, and active-only uniqueness based on trimmed, case-insensitive names and exact coordinates.
- Diagnose and resolve differences between model metadata and migration definitions, particularly coordinate-index expressions, without changing unrelated model behavior.
- Verify upgrade on a disposable database. Downgrade removes application tables in dependency order while preserving PostGIS.

Do not implement (out of scope):

- API validation, endpoints, or application-startup table creation.
```

### Key response 2

The initial migration enables PostGIS and creates category, supplier, and supplier_category with the agreed constraints and indexes. Opening hours must be wholly absent or complete, because a nullable SQL check alone can allow partial schedules. Active supplier uniqueness uses normalized names and exact coordinates, with one explicit spatial index.

The completed model adjustment aligns coordinate expressions with the migration to avoid repeated index drift. Downgrade removes dependent application tables first and leaves PostGIS installed. Upgrade and drift checks belong on a disposable database.

### Prompt 3

```text
Add a separate data migration that seeds Food, Coffee, Shopping, and Printing as controlled categories with permanent UUIDs. Keep the migration independent of future ORM changes.

Files to edit:

- `supplier-service/migrations/versions/0002_initial_categories.py` (new)

Acceptance criteria:

- Follow the initial schema migration and store category IDs as fixed migration data, never generating new IDs during execution. Preserve existing IDs when adapting completed code.
- Upgrading to the latest revision produces exactly the four controlled categories without duplicating them on subsequent upgrades.
- Downgrade removes only the seeded categories and fails when assignments still reference them.
- Re-upgrading restores the same IDs, and offline SQL generation includes the category inserts.
```

### Key response 3

The category migration follows the schema revision and stores Food, Coffee, Shopping, and Printing with fixed UUIDs. Its data definition is independent of the ORM, and upgrades reuse the same identities.

Downgrade targets only those seeded IDs. Referencing assignments prevent their deletion through the existing foreign-key restriction; after a permitted downgrade, re-upgrade restores the same categories and IDs.

### Prompt 4

```text
Separate administrator bootstrap, migration ownership, and runtime access for the supplier database. Add repeatable setup scripts, package migrations in the service image, and configure the Compose API service to use restricted runtime credentials.

Files to edit:

- `supplier-service/database/bootstrap.sql` (new)
- `supplier-service/database/runtime-grants.sql` (new)
- `supplier-service/Dockerfile`
- `compose.yaml`
- `.env.example`

Acceptance criteria:

- Administrator bootstrap enables PostGIS and provisions separate migration and runtime roles using externally supplied passwords.
- The migration role can manage application schema objects. Runtime can read and write suppliers and assignments, but only read categories and migration state.
- Runtime cannot create permanent or temporary tables, alter schema, or change controlled categories or migration state.
- Scripts stop on errors, use transactions, and can be rerun without silently changing existing object ownership.
- The image includes Alembic configuration and revisions under the existing non-root user; example configuration contains safe credential placeholders.
- Verify image packaging and the bootstrap, migration, and grant workflow on a disposable database.

Do not implement (out of scope):

- Automatic migration startup gating, readiness changes, or seed-import services.
```

### Key response 4

Administrator bootstrap installs PostGIS and provisions separate migration and runtime roles using passwords supplied through the environment. The migration role owns application schema work; runtime receives supplier and assignment data access plus read-only access to categories and migration state.

The setup scripts use transactions and stop on errors. The service image includes Alembic configuration and revisions, while Compose connects the API with runtime credentials. Existing object ownership requires deliberate handling rather than an automatic transfer. Migration startup gating remains outside this change.

### Prompt 5

```text
Extend the existing integration fixtures and add direct-SQL tests for the migrated supplier schema. Explain the fixture structure and provide its boilerplate before implementing isolated Alembic setup and per-test transaction rollback.

Files to edit:

- `supplier-service/tests/integration/conftest.py`
- `supplier-service/tests/integration/test_schema.py` (new)

Acceptance criteria:

- Preserve test database validation: require an explicit PostgreSQL/Psycopg URL for a separate database whose name ends in `_test`; fail clearly on invalid configuration.
- Apply Alembic migrations using isolated test settings, release connections, and roll back test writes. Explain cleanup and savepoints for expected failures.
- Verify application tables, migration state, and controlled category data.
- Test name, version, schedule, assignment, and deletion constraints, including partial schedules, overnight hours, and exactly 24 hours.
- Verify longitude/latitude order, normalized active identity uniqueness, exact coordinate distinctions, soft-deletion reuse, and conflicting restoration.
- Inspect required indexes and check that model metadata agrees with the migrated schema.
- Run the tests against disposable PostGIS and report observed results.
```

### Key response 5

The integration fixtures retain the explicit disposable-database checks, apply Alembic using temporary test settings, and provide a connection whose transaction is rolled back after each test. Savepoints allow expected constraint failures to be checked without invalidating the surrounding test transaction.

Direct-SQL tests cover the migrated tables, revision, categories, constraints, opening-hours boundaries, coordinate order, active identity rules, soft-deletion reuse, indexes, and metadata agreement. The existing URL validation and engine lifecycle are extended rather than replaced. Test execution results must be reported separately from this description of coverage.

### Prompt 6

```text
Add integration coverage for concurrent duplicate creation, runtime permissions, and migration downgrade/re-upgrade behavior. Explain how these tests isolate committed writes and destructive operations, and diagnose failures using database errors and schema comparisons.

Files to edit:

- `supplier-service/tests/integration/test_schema.py`

Acceptance criteria:

- Simultaneous inserts of the same active supplier identity result in exactly one commit and one uniqueness failure, with bounded waits and explicit cleanup.
- Verify allowed runtime data access and rejection of schema changes, temporary tables, category mutations, and migration-state updates using the runtime role on the same test database.
- In a uniquely named disposable database, verify that referenced categories block downgrade, re-upgrades preserve category IDs, and a full downgrade removes application tables while retaining PostGIS.
- Re-upgrade successfully and confirm no metadata drift; always clean up the database created by the lifecycle test.
- Clearly skip optional permission or lifecycle checks when their credentials are unavailable, and distinguish passed, skipped, and blocked checks in the report.
```

### Key response 6

The concurrency test uses independent transactions, bounded waits, and cleanup of its committed record. It expects one successful insert and one uniqueness rejection for the same active identity.

Permission checks use the runtime role on the same disposable database. Lifecycle checks create their own database, exercise blocked category removal and downgrade/re-upgrade behavior, verify stable category IDs and retained PostGIS, and then remove only that database. Optional checks are explicitly skipped without their credentials. Database errors and schema differences guide diagnosis; a coverage description alone does not establish that the checks passed.

### Prompt 7

```text
Document how to bootstrap, migrate, and verify the Supplier Service database. Update the README to reflect completed persistence work and explain the operational choices and limitations.

Files to edit:

- `supplier-service/docs/migrations.md` (new)
- `supplier-service/README.md`

Acceptance criteria:

- Document administrator setup, migration-role execution, runtime grants, and API startup in order, including environment configuration and credential handling.
- Explain permanent category IDs, downgrade restrictions and data loss, PostGIS preservation, ownership of existing application objects, and reapplying grants after table recreation.
- Provide commands for migration execution, revision inspection, drift checks, offline SQL generation, and disposable integration testing with cleanup.
- Explain optional permission and lifecycle checks and how to run complete coverage.
- Link the operations guide from the README and keep startup gating, readiness, and business API work identified as future work.
- Verify the documented workflow and report only observed results, identifying unavailable checks.
```

### Key response 7

The operations guide explains bootstrap, migration execution, grants, and API startup, with local commands and disposable testing instructions. It covers credentials, ownership, permanent category IDs, downgrade effects, PostGIS preservation, and reapplying grants after recreating tables.

The README links the guide and distinguishes completed persistence from future startup gating, readiness, and business API work. Validation reporting should identify the checks actually executed and any unavailable coverage. Historical verification remains recorded in the entry metadata; this reconstructed response does not represent a new test run.

### Scope

- `.env.example`: Boilerplate generation — add safe example variables for the separate migration and runtime database roles.
- `README.md`: Refactoring and documentation improvements — summarize the shared database configuration work and link to the relevant disclosures.
- `compose.yaml`: Boilerplate generation — configure the Supplier API database URL to use its restricted runtime role.
- `supplier-service/Dockerfile`: Boilerplate generation — package the Alembic configuration and revisions in the service image.
- `supplier-service/README.md`: Refactoring and documentation improvements — describe Supplier database migrations, role setup, and observed verification.
- `supplier-service/alembic.ini`: Boilerplate generation — configure the migration script location and path handling.
- `supplier-service/app/models.py`: Debugging assistance; Refactoring and documentation improvements — identify metadata drift and align coordinate-index expressions with the migration.
- `supplier-service/database/bootstrap.sql`: Writing implementation code — create PostGIS and provision migration/runtime roles with separated schema privileges.
- `supplier-service/database/runtime-grants.sql`: Writing implementation code — grant runtime operations for supplier and assignment rows and read access for categories/revision state.
- `supplier-service/docs/migrations.md`: Refactoring and documentation improvements — write database setup, role, migration, and isolated verification instructions.
- `supplier-service/migrations/env.py`: Learning support; Boilerplate generation; Writing implementation code — load application metadata and configure online/offline migration execution.
- `supplier-service/migrations/script.py.mako`: Boilerplate generation — provide the revision structure and fail-fast operation placeholders.
- `supplier-service/migrations/versions/0001_initial_schema.py`: Requirements work; Learning support; Writing implementation code — create the PostGIS tables, database constraints, indexes, and downgrade behavior from the agreed schema requirements.
- `supplier-service/migrations/versions/0002_initial_categories.py`: Writing implementation code — insert the four controlled category rows with permanent UUIDs and a guarded downgrade.
- `supplier-service/tests/integration/conftest.py`: Learning support; Boilerplate generation; Writing implementation code — configure isolated Alembic integration fixtures and transaction rollback per test.
- `supplier-service/tests/integration/test_schema.py`: Learning support; Writing implementation code; Debugging assistance — test schema rules, indexes, category data, concurrency, role permissions, drift, and downgrade/re-upgrade behavior.

This is the canonical Supplier Service record, including root-file changes
that supported the service. Disclosure edits to READMEs and usage logs are
excluded from recursive scope entries.

### Usage summary

The assistant first planned the supplier database work as guided, user-implemented checkpoints and explained SQLAlchemy/Alembic syntax in response to questions. The user implemented checkpoint portions and requested repeated reviews; the assistant inspected those changes and identified corrections. The user later changed the collaboration mode to agentic implementation, after which the assistant completed the remaining schema migration, role setup, test suite, image/Compose integration, and operational setup. The model change was retained because Alembic's live drift check showed the migration and metadata index expressions differed. Commit `1f9648a` contains the implementation; the disclosure update is recorded separately.

## ai-20260929-002

- Recorded at: 2026-09-29T21:37:03+08:00
- Exchange time: Exact original message timestamps unavailable; assistance occurred on 2026-09-29.
- Source: Codex (model: GPT-6); `functions.exec` for workspace inspection, edits, and checks.
- Mode and scenario: Agentic implementation and test writing from the user's readiness requirements and specified existing FastAPI, SQLAlchemy engine, and Alembic architecture.
- Outcome: Retained the readiness endpoint and isolated tests in the three requested files. No rejected suggestions were recorded. No startup migrations, business endpoints, or authentication changes were made.
- Verification: Agent ran `.venv/bin/python -m pytest tests/api tests/unit -q` from `supplier-service/`: 40 passed with one Starlette/AnyIO dependency deprecation warning. `git diff --check` passed. PostgreSQL integration tests were not run; SQLite and injected failures supplied database coverage. An earlier test-file write used an incorrect relative path and failed; the corrected write preceded the 40-test run.
- Author review: Keith confirmed review of all affected readiness changes. No human test rerun is claimed.
- Review confirmation recorded at: 2026-09-29T21:44:21+08:00
- Missing evidence: Original per-message timestamps unavailable. The implementation prompt and final response are available verbatim below; no redactions. Keith confirmed review of the affected files.
- Header exceptions: None.

### Prompt 1

```text
Add a readiness endpoint to the Supplier Service so we can tell whether its database is usable. Use the existing application engine and Alembic configuration to check connectivity and compare the installed revisions with the revisions packaged in the application. Resolve the configuration relative to the application files so the check still works when the working directory changes.

Keep `/health` as a simple liveness check that does not need the database. Read `supplier-service/app/main.py`, `supplier-service/app/db.py`, and `supplier-service/alembic.ini` to follow the existing setup. Use Alembic APIs to inspect revisions rather than parsing command output or hardcoding a revision.

Files to edit:

- `supplier-service/app/routes/health.py`

- `supplier-service/tests/api/test_health.py`

- `supplier-service/tests/api/test_readiness.py` (new)

Acceptance criteria:

- The `/ready` endpoint returns HTTP 200 with `{"status":"ready"}` when a lightweight connectivity query succeeds and the installed revision heads exactly match a nonempty set of packaged heads.

- It returns HTTP 503 with `{"status":"not_ready"}` when the database cannot be reached, revision state cannot be read, revisions do not match, or migration configuration is missing, invalid, or empty. Responses and diagnostic logs must not expose credentials or sensitive connection details.

- Connections are released after each check, including failed checks. Readiness recovers once database access or the schema is repaired. The `/health` endpoint continues returning HTTP 200 with `{"status":"healthy"}` even when the database is unavailable.

- Add tests for matching revisions, missing revisions, older or unexpected revisions, extra heads, empty packaged heads, connection and query failures, invalid configuration, and a changed working directory. Keep unit and API tests independent of external services.

- Suggest suitable test commands based on the project setup and explain where to run them. Report the results of any checks you run and identify anything you could not verify.

- Keep migrations and table creation out of application startup and readiness requests. Leave business endpoints and authentication outside this change.
```

### Key response 1

Implemented `/ready` using the existing engine, `SELECT 1`, and Alembic APIs with an application-relative configuration path.

- Returns 200 only when installed heads exactly match nonempty packaged heads; otherwise 503.
- Releases connections and logs only a generic failure message.
- Keeps `/health` database-independent.
- Adds no migrations or table creation to startup or readiness.

From `supplier-service/`, run:

```bash
.venv/bin/python -m pytest tests/api tests/unit -q
```

Result: **40 passed**, with one dependency deprecation warning. `git diff --check` passed.

PostgreSQL integration tests were not run; database tests used in-memory SQLite and injected failures.

### Scope

- `supplier-service/app/routes/health.py`: Writing implementation code — write readiness using the existing engine and Alembic APIs, application-relative configuration, exact nonempty head matching, connection cleanup, and generic failure diagnostics; preserve database-independent liveness.
- `supplier-service/tests/api/test_health.py`: Writing implementation code — add a test proving liveness does not connect to an unavailable database.
- `supplier-service/tests/api/test_readiness.py`: Writing implementation code — write isolated SQLite and injected-failure tests for revision matching, configuration failures, connection release, recovery, safe diagnostics, and changed working directory.

### Usage summary

Codex implemented readiness by inspecting the configured migration scripts with Alembic and comparing their heads to database revision heads after a lightweight connectivity query. The endpoint uses the existing application engine, closes connections through a context manager, and reports generic failures without exception details. Tests cover success, mismatched and absent revisions, multiple heads, invalid or empty migration configuration, database failures, cleanup, recovery, and path independence. Existing liveness behavior remains database-independent.

## ai-20260929-003

- Recorded at: 2026-09-29T22:00:59+08:00
- Exchange time: Exact original message timestamps unavailable; assistance occurred on 2026-09-29.
- Source: Codex (model: GPT-6); `functions.exec` for workspace edits and Docker/Compose verification.
- Mode and scenario: Agentic configuration work following the specified shared-image, migration-role, startup-dependency, and readiness-probe requirements, after reading the migration environment and operations guide.
- Outcome: Retained the shared application image identity, dedicated migration job, successful-completion dependency, and readiness health check in the two requested files. No rejected suggestions were recorded. Existing packaging, application user, API port/networks, and runtime role were preserved; no bootstrap automation, additional seeding, other-service changes, or privilege expansion was added.
- Verification: Agent validated Compose with `.env.example`, built the application and database images, discovered packaged head `0002`, and explicitly ran migrations and inspected the installed head through the configured migration service. In isolated project `foc-supplier-gating-16880`, the agent manually provisioned existing roles and grants on disposable PostGIS, observed migration exit 0 before API startup, healthy readiness/liveness responses, and UID 10001. A temporary failing revision mounted only into the disposable migration container produced exit 1 and left the newly created API in the created state. Restoring packaged migrations recovered healthy startup. Test containers, networks, and database volume were removed. `git diff --check` passed. The isolated configuration used a test-only image tag and ephemeral localhost port. The full multi-service stack and existing development database were not tested.
- Author review: Keith confirmed review of all affected Compose migration-gating changes. No human test rerun is claimed.
- Missing evidence: Original per-message timestamps unavailable. The implementation prompt and relevant final-response excerpts are available below without redactions.
- Header exceptions: None.

### Prompt 1

```text
Update Docker Compose so the Supplier API starts only after its migration job finishes successfully. The API exposes `/ready` for database connectivity and migration revision checks, while `/health` remains independent of the database. Use `/ready` for the API container health check.

Add a `supplier-migrate` service that uses the same built application image as `supplier-service`. The image already includes `alembic.ini` and `migrations/`. Keep that packaging and the existing application user. Read the migration environment and database operations guide before choosing the container settings. Alembic uses shared application settings, so it also needs a valid `USER_SERVICE_URL` even though migrations do not contact User Service.

Files to edit:
- `compose.yaml`
- `supplier-service/Dockerfile`

Acceptance criteria:
- Both services use an explicit shared image identity and retain the existing Supplier Service build context. The migration job upgrades the database to the Alembic head, does not restart automatically, and waits for the database health check to succeed.
- The migration job joins `supplier-private` without publishing a port. It connects as `supplier_migrator` using the existing migration password and database settings. The API continues using `supplier_runtime` with its existing networks and port binding.
- Compose requires successful migration completion before starting a newly created API container. A failed migration blocks that startup.
- The API image health check calls `/ready` with a bounded timeout. Any Compose override uses the same endpoint. Disable the inherited HTTP health check for the migration job because it does not run an API server.
- Verify that the image can discover its packaged revisions and run migrations. Check that the migration job can also be invoked explicitly using the configured image, network, settings, and provisioned database role.
- Use an isolated Compose project to check successful startup and a deliberately failed migration. Inject failures only in disposable test material. Suggest the commands needed to validate Compose, build the image, run the job, and inspect the result. Report what you verified and what remains untested.
- Keep administrator bootstrap, automatic seeding, other services, and broader runtime privileges outside this change.
```

### Key response 1

Verbatim excerpts from the final response:

- Both services share `foc-supplier-service:local` and the existing build context.
- Migration runs as `supplier_migrator`, waits for database health, disables HTTP health checks, and never restarts automatically.
- API startup requires successful migration completion. Its health check calls `/ready` with a three-second timeout.
- Existing image packaging, application user, API networks, and port binding are preserved.

Verified in an isolated Compose project: image build, packaged revision discovery, explicit migration execution, successful gated startup, and healthy API responses. An injected disposable migration failure exited nonzero and left the API unstarted. Removing the failure restored successful startup. Test containers, networks, and database volume were removed. Compose validation and `git diff --check` passed.

From the repository root, with `.env` configured:

```bash
docker compose config --quiet
docker compose build supplier-service supplier-db
docker compose run --rm --no-deps supplier-migrate python -m alembic heads
docker compose run --rm supplier-migrate
docker compose run --rm supplier-migrate python -m alembic current
docker compose up -d --wait supplier-service
docker compose ps -a supplier-migrate supplier-service
docker compose logs supplier-migrate
```

Administrator bootstrap and runtime grants remain manual prerequisites described in the operations guide. The full multi-service stack and existing development database were not tested.

### Scope

- `compose.yaml`: Boilerplate generation — configure a shared Supplier application image, a private-network migration job with the existing migrator role and required shared settings, database-health and successful-migration dependencies, no automatic restart, and disabled HTTP health checking for the job.
- `supplier-service/Dockerfile`: Boilerplate generation — configure the existing bounded HTTP health check to call `/ready` while preserving packaged Alembic files and the existing application user.

### Usage summary

Codex configured Supplier API startup to depend on successful completion of the dedicated migration job and changed the image health probe to readiness. The job uses the same built image and existing migration credentials while runtime access stays separate. Disposable Compose checks exercised explicit job execution, successful startup, migration failure blocking a new API container, and recovery. Operational validation commands were supplied; administrator bootstrap and runtime grants remained manual prerequisites.

## ai-20260929-004

- Recorded at: 2026-09-29T22:26:14+08:00
- Exchange time: Exact original message timestamps unavailable; assistance occurred on 2026-09-29.
- Source: Codex (model: GPT-6); `functions.exec` for documentation edits, Docker/Compose rehearsal, and validation.
- Mode and scenario: Agentic deployment documentation and verification against the existing Compose configuration, followed by diagnosis and correction of the user's reported fixed-port probe issue.
- Outcome: Retained fresh-install and existing-volume deployment instructions, explicit migration reruns and grants, inspection/recovery exercises, isolated test setup, cleanup commands, and updated README behavior descriptions. Corrected the rehearsal to explicitly replace the development-port probe with a recalculated disposable address immediately after API recreation. Production revisions were not changed.
- Verification: Agent used isolated Compose project `foc-supplier-docs-19148` on Docker Desktop/Apple Silicon with Compose v5.5.1. Builds and packaged/installed head inspection succeeded at `0002`. Missing grants, database outage, and revision `0001` each produced safe readiness 503 and liveness 200; repaired access/schema restored readiness. Upgrade and failed-migration recovery retained the volume and representative supplier row. A temporary mounted failing revision exited 1 and left a newly created API unstarted; recovery succeeded without deleting persistent data. The initial host integration connection setup failed because the internal-only network did not publish a usable port (40 passed, 33 setup errors, one failure). Adding the default network only in the disposable override corrected the setup; the full suite passed with 74 tests, no skips, and one Starlette/AnyIO deprecation warning. Shell blocks passed `bash -n`, relative links resolved, and `git diff --check` passed. Disposable containers, networks, and volume were removed. For the follow-up wording correction, `git diff --check` passed; Docker tests were not rerun. Full-stack deployment, native AMD64, development/production data, an archived older application image, and future migrations were not verified.
- Author review: Keith confirmed review of the affected documentation and follow-up correction. No human test rerun is claimed.
- Missing evidence: Original per-message timestamps unavailable. Both underlying prompts and relevant final-response excerpts are available below without redactions.
- Header exceptions: None.

### Prompt 1

```text
Update the Supplier Service documentation to explain how to deploy with migration checks and verify recovery from failures. The deployment uses a shared application image for the API and a separate migration job. Compose waits for database health and successful migration completion before starting the API. The `/ready` endpoint checks database connectivity and installed revisions, while `/health` checks application liveness.

Follow the existing administrator bootstrap and runtime grant workflow. Verify the instructions with an isolated Compose project and disposable data, then document the commands that match the actual project configuration.

Files to edit:
- `supplier-service/docs/migrations.md`
- `supplier-service/README.md`

Acceptance criteria:
- Explain a fresh installation in order, covering credentials, database startup, PostGIS and role bootstrap, image building, explicit migration execution, runtime grants, and API startup. Make clear that a migrated database still needs to grant the runtime role permission to read revision state.
- Explain how to deploy a new image against an existing volume. Include explicitly rerunning the migration job, reviewing or reapplying grants when needed, and recreating the API after successful migration. Provide the appropriate commands in the documentation after checking them against the final Compose configuration.
- Explain that Compose startup ordering does not schedule migrations for every deployment. A previously completed job does not prove that a new image has been migrated, and startup dependencies do not stop an API that is already running.
- Verify that a fresh installation reaches the packaged revision and that the API becomes healthy after grants are applied. Verify an upgrade from an older revision using the same persistent volume and confirm that representative existing data survives.
- Check that database unavailability and an outdated schema each make `/ready` return a safe HTTP 503 while `/health` still returns HTTP 200. Confirm readiness recovers after the database or schema is repaired.
- Check that a failed migration prevents a newly created API container from starting. Fix the cause and rerun the migration to demonstrate recovery without deleting persistent data.
- Replace README statements that describe readiness as future work or say startup depends only on database health. Explain how to inspect migration status, job logs, installed revisions, and container health.
- Suggest suitable commands for the existing unit, API, and database integration checks, including the required isolated test configuration. Record actual results and identify checks that were skipped or unavailable. Explain cleanup for the disposable project without removing development volumes.
- Do not change production revisions just to inject test failures or introduce destructive reseeding.
```

### Key response 1

Verbatim excerpts from the final response:

Verified with disposable Compose data:

- Fresh installation and healthy startup after grants.
- Older-revision upgrade preserving a supplier row and volume.
- Safe readiness failures during database/schema problems, followed by recovery.
- Failed migration blocking API startup, then recovery without deleting data.
- **74 tests passed**, no skips; one dependency warning.

Shell syntax, documentation links, and `git diff --check` passed. Disposable resources were removed.

Full-stack deployment, AMD64, and development/production databases remain untested.

### Prompt 2

```text
The isolated upgrade rehearsal includes a probe against the development port. `supplier-service/docs/migrations.md:349` instructs readers to repeat the existing-volume sequence with `dc`, but that sequence ends with `curl http://127.0.0.1:8081/ready`. The disposable project uses a random port, so this command can fail or check an unrelated development API. Explicitly replace that probe with a recalculated `CHECK_API` before running it. 

Diagnose this. Is this a possible documentation issue?
```

### Key response 2

Verbatim excerpts from the final response:

Yes—this was a documentation bug. Replacing `docker compose` with `dc` does not change the hardcoded curl URL. Readers could probe an unrelated development API or get a misleading connection failure.

```bash
CHECK_API="http://$(dc port supplier-service 8080)"
curl --fail --max-time 5 "$CHECK_API/ready"
```

`git diff --check` passed. Docker tests were not rerun for this wording-only correction.

### Scope

- `supplier-service/docs/migrations.md`: Refactoring and documentation improvements; Debugging assistance — write ordered deployment, role-grant, revision inspection, recovery, isolated-test, and cleanup instructions; explain the test network connection failure and correct the fixed-port rehearsal probe reported by the user.
- `supplier-service/README.md`: Refactoring and documentation improvements — replace stale readiness/startup descriptions with the implemented migration gating and probe behavior, and summarize deployment, inspection, tests, recovery, and verified limitations with links to the operations guide.

### Usage summary

Codex documented the existing shared-image migration-job architecture and rehearsed deployment/recovery against disposable PostGIS data. The guide separates administrator bootstrap, migrator execution, and runtime grants; requires an explicit migration run for each new image; and explains the limits of Compose startup ordering. The user then identified that reusing the deployment sequence could probe the fixed development port before resolving the disposable port. Codex confirmed the issue and made that replacement explicit, preserving the production deployment probe while correcting the isolated rehearsal.
