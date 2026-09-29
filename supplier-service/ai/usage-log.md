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
