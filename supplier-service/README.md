<!-- AI Assistance Disclosure:
Tool: Codex (model: GPT-6), date: 2026-09-28 to 2026-09-30
Scope: Documentation — describe database migration, role setup, and observed verification. Refactoring and documentation improvements — update migration-gated deployment, readiness/liveness behavior, inspection, recovery, and verification guidance (2026-09-29).
Scope: Refactoring and documentation improvements — document future API/import calls to aggregate validation, omission versus null, stored-time PATCH merging, caller-supplied category IDs, safe error responses, test commands, and coverage against the domain-input guide.
Scope: Refactoring and documentation improvements — document the executable seed dry run, JSON diagnostics, exit behavior, daily schedules, identity-preserving review, and future persistence classification.
Scope: Refactoring and documentation improvements — replace source-only dry-run instructions with configuration, bootstrap/migration/grant prerequisites, explicit preview/import commands, JSON outcomes, identity and lock behavior, and isolated verification guidance. (ai-20260930-012)
Scope: Refactoring and documentation improvements — document mounted public reads, protected administrator dependencies, the verified identity contract, lifecycle and error mappings, verification commands, and a test-only live login/logout and simulated-outage smoke harness with prerequisites and observed limits. (ai-20260930-022)
Author review: Keith confirmed review of all affected changes, including the dry-run documentation (ai-20260930-008). Keith confirmed review of the packaging changes (ai-20260930-012). Keith confirmed review of public-read registration changes (ai-20260930-022).
Details: ai/usage-log.md; ai-20260929-001; ai-20260929-004; ai-20260930-003; ai-20260930-008; ai-20260930-012; ai-20260930-022
-->

# Supplier Service

The Supplier Service maintains the campus stores, facilities and locations
from which users can request pickups. It owns supplier information and
exposes an API for browsing and managing that information.

Other services access supplier information through the API. They do not
connect directly to the Supplier Service database.

The service provides validated startup configuration, `GET /health`,
`GET /ready`, interactive API documentation, and SQLAlchemy models for `supplier`,
`category`, and `supplier_category`. Application startup initializes a
database engine and session factory, and shutdown disposes of the engine.
Request-scoped sessions are closed without automatically committing;
service functions will own transaction boundaries.

The API and a persistent PostgreSQL/PostGIS database run through Docker
Compose. A separate migration job shares the application image and applies
Alembic revisions before a newly created API starts. Migrations create the schema
and four controlled categories; startup and probes do not create tables.
See [schema operations](docs/migrations.md) for ordered installation, deployment
to an existing volume, role grants, recovery rehearsals, and integration tests.
Public supplier and reference-data reads are mounted; administrator mutations
and administrative reads remain future work.

## Local Development

Use Python 3.12 (the `.python-version` file pins 3.12.12). From the repository
root, create the service's virtual environment and install dependencies:

```bash
cd supplier-service
python3.12 -m venv .venv
./.venv/bin/python -m pip install -r requirements-dev.txt
```

The development requirements include the runtime requirements. Keep `.venv/`
untracked; each developer creates their own environment.

Set configuration in the terminal where you will start the server:

```bash
export DATABASE_URL='postgresql+psycopg://test_user:test_password@localhost:5432/test_supplier'
export USER_SERVICE_URL='http://localhost:8000'
export AUTH_TIMEOUT_SECONDS='3'
export LOG_LEVEL='INFO'
```

These URLs and credentials are dummy local examples. Startup validates settings
and creates the engine without connecting. `/health` needs neither a database
nor User Service. `/ready` needs a reachable, migrated database and runtime
permission to read its revision state; User Service is not contacted by either probe.

| Variable | Requirement |
| --- | --- |
| `DATABASE_URL` | Required PostgreSQL connection URL using `postgresql+psycopg` |
| `USER_SERVICE_URL` | Required HTTP or HTTPS base URL for User Service |
| `AUTH_TIMEOUT_SECONDS` | Positive, finite number; defaults to `3.0` |
| `LOG_LEVEL` | `DEBUG`, `INFO`, `WARNING`, `ERROR`, or `CRITICAL`; defaults to `INFO` |

Settings are validated during application startup. Missing required values
or invalid values prevent startup. The root `.env.example` documents example
values; copying it to `.env` does not automatically load it into this
application. Export variables explicitly for local runs. Compose reads the
root `.env` and passes settings into the containers explicitly. Keep real
credentials out of committed files.

Start the API using the virtual environment's Python to avoid accidentally
running a globally installed Uvicorn:

```bash
./.venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8081
```

Open <http://127.0.0.1:8081/health> and expect HTTP 200 with
`{"status":"healthy"}`. Open <http://127.0.0.1:8081/docs> to inspect the API
and execute `GET /health` using **Try it out**. Neither endpoint requires
authentication. The health endpoint indicates application liveness; it does
not establish database readiness. `GET /ready` returns HTTP 200 with
`{"status":"ready"}` only when connectivity succeeds and installed Alembic heads
exactly match the nonempty packaged heads. Otherwise it returns HTTP 503 with
`{"status":"not_ready"}` and a generic diagnostic without connection details.
Stop the server with **Ctrl+C**.

Run the tests from `supplier-service/`:

```bash
./.venv/bin/python -m pytest tests/unit tests/api -q
```

Current unit and API tests use explicit dummy settings or temporary
environment variables and require no running database or User Service.
They cover the health response, configuration defaults and validation,
the required Psycopg driver scheme, rejection of invalid startup
configuration, database engine initialization and disposal, revision matching,
configuration/connection failures, connection release, and readiness recovery.
They also cover standalone domain checks, creation and merged PATCH validation,
and shared HTTP 422 handlers through routes registered only by tests. Supplier
mutation endpoints are not implemented; explicit CSV import is available below.

### Integration-test database configuration

Database integration tests use `TEST_DATABASE_URL`, which must
be configured explicitly. The fixtures never fall back to `DATABASE_URL`.

The test URL must:

- Use `postgresql+psycopg`.
- Specify a database name ending in `_test`.
- Use a different database name from `DATABASE_URL`, when that variable is set.

These checks guard against accidental development-database use. Configure
the URL to point to a separate database reserved for tests.

Fixtures validate configuration and apply Alembic migrations to the explicitly
configured test database. See [schema operations](docs/migrations.md) for
disposable database setup and optional privilege/lifecycle checks.

Current unit and API tests do not require `TEST_DATABASE_URL`.

## Docker Compose

Run these commands from the repository root. Docker must be running with
Linux container support. Stop any local Uvicorn process using port 8081
before starting the API container.

### Configuration

If a root `.env` does not already exist, copy `.env.example` to `.env`:

```bash
cp .env.example .env
```

Set these database initialization values in `.env`:

- `SUPPLIER_POSTGRES_DB`, for example `supplier_db`.
- `SUPPLIER_POSTGRES_USER`, for example `supplier_admin`.
- `SUPPLIER_POSTGRES_PASSWORD`, using a local development password.

Keep real credentials in the ignored `.env` file. Compose constructs the
database URL from these values; use letters and numbers for the local
password to avoid characters requiring URL encoding. The bootstrap database
account is reserved for bootstrap. Configure `SUPPLIER_MIGRATION_PASSWORD` and
`SUPPLIER_RUNTIME_PASSWORD`, then follow [schema operations](docs/migrations.md)
before starting the API with its restricted runtime role.

Compose reads `.env` for variable substitution and explicitly passes
settings into the containers. VS Code terminal environment injection is
not required. Existing shell variables take precedence over `.env` values.
`AUTH_TIMEOUT_SECONDS` defaults to `3` and `LOG_LEVEL` defaults to `INFO`
when unset or empty in the Compose environment.

### Fresh installation and later deployments

For a fresh database, follow the [ordered installation guide](docs/migrations.md#fresh-installation):
configure credentials, start the database with `--wait`, run administrator
PostGIS/role bootstrap, build the application image, explicitly run
`supplier-migrate`, apply runtime grants, then start the API. Migration success
alone does not grant `supplier_runtime` permission to read `alembic_version`;
without that grant, readiness returns 503.

After bootstrap, migrations, and grants have succeeded:

```bash
docker compose up -d --wait --wait-timeout 90 supplier-service
docker compose ps -a supplier-db supplier-migrate supplier-service
```

Compose waits for database health and successful migration-job completion before
starting a newly created API. Expect a migration job exited with code 0 and
healthy database/API containers. Both API and job use `foc-supplier-service:local`
from the existing Supplier build context. The job has no HTTP health check,
published port, or automatic restart. Both run as application UID 10001 while
using separate database roles.

For each new image, use the [existing-volume deployment sequence](docs/migrations.md#deploying-a-new-image-with-the-existing-volume):
rebuild the shared image, wait for the database, stop the API for maintenance,
explicitly recreate/run the migration job and check its exit code, review/reapply
grants, then recreate the API. A previously completed job does not prove a new
image has been migrated. Compose dependencies do not schedule every deployment
or stop an API that is already running when a dependency fails.

### Probes and inspection

- Readiness: <http://127.0.0.1:8081/ready> — connectivity and exact migration heads;
  returns 200 with `{"status":"ready"}` or safe 503 with `{"status":"not_ready"}`.
- Liveness: <http://127.0.0.1:8081/health> — returns 200 with
  `{"status":"healthy"}` independently of database availability.
- API documentation: <http://127.0.0.1:8081/docs>.

The image health check uses `/ready` with a three-second HTTP timeout. Inspect
packaged versus installed revisions, the migration job, and container health:

```bash
curl -i --max-time 5 http://127.0.0.1:8081/ready
curl -i --max-time 5 http://127.0.0.1:8081/health
docker compose ps -a supplier-db supplier-migrate supplier-service
docker compose logs --tail=80 supplier-migrate supplier-service
docker compose run --rm --no-deps supplier-migrate python -m alembic heads
docker compose run --rm --no-deps supplier-migrate python -m alembic current
docker inspect --format '{{json .State.Health}}' "$(docker compose ps -q supplier-service)"
docker compose exec supplier-service id
```

Readiness recovers after database access, schema revisions, or grants are
repaired. See the [isolated recovery rehearsal](docs/migrations.md#isolated-deployment-and-recovery-rehearsal)
for outage, older-schema, and failed-migration checks that preserve persistent
data. A failed migration blocks a new API container; fix the cause and rerun the
job instead of resetting its database.

### Networking and storage

The API joins the shared application network and the private supplier
network. The migration job and database join only the private supplier network
and have no published host port. A `5432/tcp` entry in `docker compose ps` is not a host
port mapping. The API publishes only `127.0.0.1:8081`.

Inside the API container, the database address is `supplier-db:5432` and
the User Service address is `http://user-service:8080`. These names refer
to Compose services; `localhost` refers to the current container.

The named volume `supplier-db-data`, mounted at `/var/lib/postgresql/data`,
preserves database files when the database container is recreated. Compose
normally prefixes the volume name with the project name. Removing this
volume deletes the stored database contents.

Database initialization credentials apply when the data directory is
first created. Editing the password in `.env` afterward does not change
the existing PostgreSQL account password; change the account password in
PostgreSQL and update the corresponding configuration together.

To stop the supplier containers while retaining their data:

```bash
docker compose stop supplier-service supplier-db
```

### Implementation status

The database image extends PostgreSQL 16 with PostGIS packages. Its base
image is pinned to a multi-platform index digest supporting AMD64 and
ARM64. Compose builds for the host architecture without forcing AMD64
emulation. PostGIS packages installed through apt are not version-pinned,
so pinning the base image alone does not make the whole build immutable.

Local Apple Silicon checks have confirmed container health, the API
response, non-root API execution, PostGIS availability, and persistence
across database container recreation. The PostgreSQL cluster identifier
remained unchanged after recreation. Native AMD64 execution still needs
verification.

The administrator bootstrap enables PostGIS; migrations create the schema.
The API initializes its database engine and gates readiness on connectivity and
installed migration revisions. Public reads do not authenticate; reusable
User Service authentication dependencies are covered through test-only protected
routes until production administrator operations are implemented.
Compose gates new API startup on database health and successful migration completion.

Deployment verification on disposable data covered fresh bootstrap and grants,
upgrade from `0001` to packaged head `0002` on the same volume with a surviving
supplier row, database-outage and schema-repair readiness recovery, and a temporary
failed migration blocking new API startup before successful recovery. See the
[verification record](docs/migrations.md#observed-verification) for test results,
limits, and project-scoped cleanup commands.

## Initial Scope

The initial implementation supports:

- Creating suppliers with one or more categories.
- Listing and retrieving suppliers.
- Updating supplier information and category assignments.
- Removing suppliers from available listings through soft deletion.
- Importing the initial supplier dataset.
- Storing a general daily opening schedule.
- Filtering suppliers by area and category.

Direct supplier mutations are restricted to administrators. User-submitted
change requests and their approval workflow will be introduced later.

Supplier menus, product inventories, checkout and vendor payments are
outside this service's scope.

## Database

The proposed database is PostgreSQL with PostGIS.

PostgreSQL stores supplier records, categories and their relationships.
PostGIS stores geographic pickup points and supports future distance
filtering and sorting.

The initial schema contains three tables:

| Table | Responsibility |
| --- | --- |
| `supplier` | Supplier details, availability and general daily hours |
| `category` | Controlled category definitions |
| `supplier_category` | Assignments between suppliers and categories |

### Relationships

A supplier must have at least one category. A category may be assigned to
any number of suppliers, including none.

```mermaid
erDiagram
    SUPPLIER ||--|{ SUPPLIER_CATEGORY : "has assignments"
    CATEGORY ||--o{ SUPPLIER_CATEGORY : "is assigned through"

    SUPPLIER {
        uuid id PK
        text name
        text area
        geography location
        text description
        text building
        text floor
        text image_key
        time opening_time
        time closing_time
        smallint closing_day_offset
        timestamptz created_at
        timestamptz updated_at
        timestamptz deleted_at
        integer version
    }

    CATEGORY {
        uuid id PK
        text name UK
    }

    SUPPLIER_CATEGORY {
        uuid supplier_id PK, FK
        uuid category_id PK, FK
    }
```

## Supplier Table

Mandatory fields cannot be null. Server-managed fields are populated by
the service rather than accepted as ordinary user-editable inputs.

| Field | PostgreSQL type | Mandatory | Ownership and purpose |
| --- | --- | --- | --- |
| `id` | `UUID` | Yes | Server-generated, immutable random UUID primary key |
| `name` | `TEXT` | Yes | Nonblank supplier name |
| `area` | `TEXT` | Yes | General campus area from a controlled list |
| `location` | `GEOGRAPHY(Point, 4326)` | Yes | Geographic pickup location |
| `description` | `TEXT` | No | Additional pickup directions |
| `building` | `TEXT` | No | Building name or identifier |
| `floor` | `TEXT` | No | Floor label, such as `1` or `B1` |
| `image_key` | `TEXT` | No | Reference to an externally stored image |
| `opening_time` | `TIME WITHOUT TIME ZONE` | No* | General daily opening time |
| `closing_time` | `TIME WITHOUT TIME ZONE` | No* | General daily closing time |
| `closing_day_offset` | `SMALLINT` | No* | Server-derived: `0` for same-day closing or `1` for next-day closing |
| `created_at` | `TIMESTAMPTZ` | Yes | Server sets on creation |
| `updated_at` | `TIMESTAMPTZ` | Yes | Server sets on creation and modification |
| `deleted_at` | `TIMESTAMPTZ` | No | Null while active; server sets on soft deletion |
| `version` | `INTEGER` | Yes | Starts at `1` and increments on modification |

*The three opening-hours fields must either all be populated or all be null.*

### Supplier Identifier

Supplier IDs are immutable, server-generated random UUIDs. This chosen identity
scheme replaces D1's location-and-name hash. Generate the UUID once when
creating a supplier. Store it
using PostgreSQL's native `UUID` type and enforce uniqueness through the
primary key.

The ID is independent of the supplier's name and coordinates and remains
unchanged when the supplier is renamed, edited or soft-deleted.

Duplicate supplier checks are separate from primary-key uniqueness:
creating the same supplier twice would otherwise produce two different IDs.
Only active records participate in duplicate detection. Compare names after
trimming leading/trailing whitespace and lowercasing, and require exactly equal
numeric latitude and longitude. Preserve display capitalization. Area does not
affect duplication: same-name branches at different coordinates are allowed,
and different names may share coordinates.

Enforce this rule with a partial unique database index on the normalized name
and numeric coordinate expressions, restricted to `deleted_at IS NULL`. A
pre-insert lookup alone is insufficient under concurrency. Map violations of
this specific index to `409 Conflict`, including conflicting renames, and roll
back the mutation. Deleted records do not block a new supplier with a new UUID;
existing historical references continue to identify the deleted record.

The seed importer must use stable seed identifiers or a persistent mapping
to existing supplier UUIDs. It must not generate fresh UUIDs for the same
seed records on every run or overwrite existing records on an ID conflict.

### Location Details

Location fields serve different purposes:

| Field | Example | Purpose |
| --- | --- | --- |
| `area` | `Science` | Broad campus grouping and filtering |
| `building` | `S16` | Specific building |
| `floor` | `1` | Specific floor |
| `description` | `Near the entrance facing the bus stop` | Additional directions |
| `location` | Latitude and longitude | Geographic pickup point |

`area` uses a controlled list to avoid inconsistent values such as
`Science`, `Sci` and `Faculty of Science`. The initial implementation can
maintain this list in service validation without introducing an area table.

The initial values are `Engineering`, `FASS`, `SoC`, `BIZ`, `PGP`, `Science`,
`USC/UHC`, `UTown`, `YIH`, `YST`, and `KR/NUH`. Each slash-separated label is
one combined area. `GET /areas` exposes the approved choices. Adding a value
requires updating validation and deploying; renaming, merging, or removing
values also requires migrating affected suppliers and updating seed mappings
and clients. Building-to-area mappings still require review.

The geographic point should identify the pickup point or accessible
entrance as accurately as possible.

The API may represent coordinates as named `latitude` and `longitude`
properties. PostGIS point construction uses longitude first, then latitude.

Under the existing D1 requirement, geographic coordinates are supplied
during creation and are immutable during ordinary updates.

### Opening Hours

Initially, a supplier has one general schedule applying equally to every
day from Monday through Sunday.

All opening and closing times are interpreted in `Asia/Singapore`.

| Opens | Closes | Offset | Meaning |
| --- | --- | --- | --- |
| `10:00` | `19:30` | `0` | Opens and closes on the same day |
| `18:00` | `02:00` | `1` | Closes at 02:00 the following day |
| `00:00` | `00:00` | `1` | Open for 24 hours |
| `NULL` | `NULL` | `NULL` | Hours are unknown |

Validation rules:

- Clients supply opening and closing times only; reject client-supplied
  `closing_day_offset` on POST and PATCH.
- Derive offset `0` when closing is later than opening, otherwise `1`. Equal
  times mean open for 24 hours.
- Both times null mean unknown hours and produce a null offset. Reject a
  resulting schedule with only one populated time with `422`.
- Store all three fields populated together, or all three null.
- Accept only `0` or `1` as a populated closing-day offset.
- Require the represented duration to be greater than zero and no more
  than 24 hours.
- Treat unknown hours as unknown, rather than closed or always open.
- Store the closing time and offset separately. The UI may display them
  as `02:00 next day` or `02:00+1`.

For a partial update, validate the resulting record. Updating only the
closing time retains the existing opening time and recalculates the offset.
Changing only the opening time also recalculates the offset. Clearing a known
schedule requires both times to be explicitly null. A validation failure
rejects the entire request, including unrelated field changes.

The initial CSV does not specify weekdays. Treating its hours as applicable
every day is an assumption that must be documented during import.

### Optional Values

Store absent optional values as SQL `NULL` and return them as JSON `null`.

Normalize empty or whitespace-only optional text to null.

Suggested UI behaviour:

| Missing value | UI behaviour |
| --- | --- |
| `description` | Omit additional directions |
| `building` | Show the supplier name and map location |
| `floor` | Omit the floor label |
| `image_key` | Show a standard placeholder image |
| Opening-hours fields | Display "Hours unknown" |

Image files are stored separately from the database. Initially, bundle the
six seed images in `frontend-service/public/images/suppliers/` inside the
frontend container. Supplier Service stores and returns filename keys, such as
`ANNA.jpeg`; the frontend resolves `/images/suppliers/ANNA.jpeg` on its own
origin and displays a placeholder for null. Keep original files in `data/images/`
and copy them during asset integration. Image updates require a frontend
rebuild; runtime uploads are outside the initial implementation.

## Category Table

Categories form a controlled vocabulary, such as `Food`, `Coffee`,
`Shopping` and `Printing`.

| Field | PostgreSQL type | Mandatory | Purpose |
| --- | --- | --- | --- |
| `id` | `UUID` | Yes | Server-generated primary key |
| `name` | `TEXT` | Yes | Unique, nonblank category name |

Trim category names and apply a consistent case-insensitive uniqueness
policy so `Food` and `food` cannot be created as separate categories.

No optional fields are required initially.

## Supplier Category Table

This table implements the many-to-many relationship between suppliers
and categories.

| Field | PostgreSQL type | Mandatory | Purpose |
| --- | --- | --- | --- |
| `supplier_id` | `UUID` | Yes | Foreign key to `supplier.id` |
| `category_id` | `UUID` | Yes | Foreign key to `category.id` |

Constraints:

- Use `(supplier_id, category_id)` as the composite primary key.
- Silently deduplicate repeated valid category IDs on create and update.
  Validate unknown entries using their original request positions before
  deduplication. Store and return each assignment once; the frontend uses
  category IDs as keys and displays each category once.
- Prevent duplicate category assignments at the database level as well.
- Require referenced suppliers and categories to exist.
- Reject category deletion while assignments still reference it.
- Require at least one category when creating a supplier or replacing
  its categories.

The foreign keys do not enforce the minimum of one category per supplier.
The service enforces this rule within the same transaction as the mutation.

For example:

| Supplier | Category |
| --- | --- |
| Campus Café | Food |
| Campus Café | Coffee |
| Library Printer | Printing |

Retain category assignments when a supplier is soft-deleted.

## CRUD Behaviour

### Create

The service:

1. Validates required supplier fields and category identifiers.
2. Requires at least one category.
3. Validates optional fields and opening hours.
4. Generates an immutable random UUID for the supplier ID.
5. Sets `created_at` and `updated_at`, initializes `version` to `1`,
   and leaves `deleted_at` null.
6. Inserts the supplier and category assignments in one transaction.

A failed operation must not leave a partially created supplier.

### Read

Normal listings include only active suppliers:

```sql
WHERE deleted_at IS NULL
```

Return categories as an array alongside supplier details. The API hides
the linking-table structure from consumers.

```json
{
  "id": "supplier-uuid",
  "name": "Campus Café",
  "area": "Science",
  "location": {
    "latitude": 1.296,
    "longitude": 103.773
  },
  "categories": [
    {
      "id": "food-category-uuid",
      "name": "Food"
    },
    {
      "id": "coffee-category-uuid",
      "name": "Coffee"
    }
  ],
  "description": null,
  "building": "S16",
  "floor": "1",
  "image_key": null,
  "opening_time": "10:00:00",
  "closing_time": "19:30:00",
  "closing_day_offset": 0,
  "created_at": "2026-09-26T02:00:00Z",
  "updated_at": "2026-09-26T02:00:00Z",
  "deleted_at": null,
  "version": 1
}
```

This example shows the complete supplier representation; identifier values
are placeholders.

Lists return `{ "items": [...], "total": 42, "limit": 20, "offset": 0 }`.
`total` counts suppliers matching all filters before pagination. Default limit
is 20, maximum 100, and default offset is 0; require limit 1–100 and nonnegative
offset. Sort by name then ID. Repeated `category_id` filters match any selected
category, without duplicate suppliers; combine categories with an area filter
using AND.

Removed suppliers remain retrievable through appropriately authorised
administrative or historical access.

### Update

The PATCH allowlist is `name`, `description`, `area`, `building`, `floor`,
`image_key`, `opening_time`, `closing_time`, and `category_ids`. This expands
D1's name-and-description-only updates. Coordinates, identity, timestamps,
deletion state, version, and derived offset are not client-editable.

For partial updates:

- Omitted fields remain unchanged.
- Explicit null clears a nullable field, subject to validation.
- Required fields cannot be cleared.
- `category_ids`, when supplied, replaces the current category selection.
- An empty category selection is rejected.
- Server-managed fields cannot be set directly by the caller.
- Geographic coordinates remain immutable under the current requirement.

PATCH and DELETE require a positive `expected_version` query parameter.
The client supplies the version on which its edit is based. The service
applies the update only if that version still matches the stored version.

A successful update changes `updated_at` and increments `version`,
including category-only changes and requests whose values equal the saved
values. Every successful PATCH increments the version. Stale active-record versions
return `409`, even when the competing edits affect different fields.

Supplier updates and category changes occur in one transaction.

### Delete

Removal uses soft deletion. The supplier stays in the `supplier` table.

The service:

1. Sets `deleted_at`.
2. Updates `updated_at`.
3. Increments `version`.
4. Retains all supplier details and category assignments.

The supplier then disappears from ordinary available-supplier listings.
Repeated deletion must not repeatedly increment the version or replace
the original deletion timestamp. An authenticated, authorized repeat DELETE
with a valid positive expected-version parameter returns `204` even if that
version is stale, because the record is already deleted.

Existing orders should retain their supplier identifier and a snapshot
of the pickup details needed to preserve historical information.
Cross-service references are not database foreign keys.

## Authentication and HTTP Contract

Ordinary browsing is public. `GET /suppliers`, `GET /suppliers/{id}`,
`GET /categories`, and `GET /areas` require no session and never contact User
Service. They ignore Authorization headers, including invalid or expired
credentials. Ordinary supplier reads expose active suppliers only.

Supplier creation, updates, deletion, and administrative reads require an
authenticated account with a verified `admin` role. For those operations,
forward opaque bearer tokens to User Service `GET /users/me`. Do not decode
JWTs or query its database. Use bounded timeouts and no authentication caching
initially. Administrator mode changes only frontend controls. Check the
verified account role on every protected request and never trust a mode/role header.

The contract was verified on `main` at
`f27533c16ad57f8fa9df0fdc72aef8c5cbf34e77`. Extract UUID `id`, `role` (`user`
or `admin`), and `status` (`active`) from the successful profile response and
ignore unrelated fields. User Service checks revocation, expiry, and account
status and refreshes the session inactivity deadline.

Public browsing must remain available independently of User Service
availability, subject to Supplier Service's own database dependencies. Client
construction and application startup must not contact User Service. Neither
`/health` nor `/ready` includes a User Service check. Protected operations
still depend on User Service and fail closed during an authentication outage.
All four public read adapters are mounted in the production application, with
no authentication dependencies or OpenAPI security requirements. Administrator
CRUD and administrative reads remain unimplemented; `get_current_user` and
`require_admin` are exercised on test-only protected routes, which declare
HTTP bearer security.

Each application lifespan creates one reusable synchronous `UserServiceClient`
from the existing settings and stores it at `app.state.user_service_client`.
Synchronous dependencies run its blocking HTTP work in worker threads. The client
uses bounded timeouts, strips URL credentials, and never follows redirects.
Identity resolution is shared within a protected request through dependency
composition, but every new protected request checks User Service again.
Shutdown closes the client and disposes the database engine; partial startup
failures release resources already created. Client construction makes no network
request. No tokens, profile payloads, or upstream error bodies are logged.

On protected routes, return `401` for missing/invalid sessions and `403` for
insufficient permissions. Across the API, return
`404` for unavailable records, `409` for stale active versions or duplicates,
`422` for invalid input, and `503` for unavailable database/authentication
dependencies. Authentication failures apply only to protected routes and do
not interrupt public browsing. An authentication outage does not establish
that the user has logged out. Map upstream 401 to 401. Map every other non-200
response, transport failure, timeout, or malformed success response to 503.
An unknown role or non-active status in a success response violates the
verified contract and also produces 503. Do not follow redirects carrying tokens.
Use the `error.code` and `error.message` envelope with
`AUTHENTICATION_REQUIRED`, `FORBIDDEN`, and `AUTHENTICATION_UNAVAILABLE` for
401, 403, and authentication-related 503 respectively. Include
`WWW-Authenticate: Bearer` on 401.

POST returns `201 Created`; PATCH returns `200 OK`. Both return the complete
saved supplier using the same representation as detail reads: all supplier
fields, including timestamps, derived offset and version, with named location
coordinates and category objects rather than linking-table rows. DELETE
returns `204 No Content` with no body.

The [read example](#read) shows the complete supplier response shape.
The mutation rules above define editable inputs, version checks, and deletion
behaviour; error response examples appear below.

### Public-read and authentication verification

From `supplier-service/`, with Python 3.12 and `requirements-dev.txt` installed
in `.venv`, run these database-independent checks:

```bash
./.venv/bin/python -m pytest tests/api/test_supplier_reads.py tests/api/test_health.py tests/api/test_readiness.py -q
./.venv/bin/python -m pytest tests/unit/test_user_service_client.py tests/api/test_auth.py tests/api/test_startup.py tests/api/test_validation_errors.py -q
./.venv/bin/python -m pytest tests/unit tests/api -q
```

The public-read tests use the real application factory, controlled supplier
services, and a recording User Service mock transport. They assert unchanged
responses for absent, user, administrator, malformed, expired, and revoked
credentials, including an authentication outage, with zero identity-resolution
or transport calls. Probe tests run with an unavailable authentication transport;
readiness still depends only on Supplier database/revision health. `/areas`
remains independent of both database access and session validation.

To recheck active-only database filtering and deleted-supplier exclusion, run:

```bash
./.venv/bin/python -m pytest tests/integration/test_supplier_reads.py -q
```

This requires an explicitly configured `TEST_DATABASE_URL` using
`postgresql+psycopg`, a reachable isolated PostGIS database with a name ending
in `_test` and different from `DATABASE_URL`, and migration permissions.

### Live session smoke check

Run the following from `supplier-service/` with the same Python environment.
Prerequisites: exported `DATABASE_URL` for a migrated disposable Supplier database
with at least one active supplier, exported `USER_SERVICE_URL` reachable from
this process, and an existing active administrator account in User Service.
Set `ADMIN_STUDENT_NUMBER` to that account's student number; the script prompts
for its password without echoing it. Do not put passwords or tokens in command
arguments, logs, or committed files. Compose does not publish User Service's port
by default: use a reachable development instance or run in a configured network
environment; see [User Service setup](../user-service/README.md).

The harness adds a protected route only to an in-process test application. It
uses live User Service login/profile/logout calls, confirms public browsing
before login and after revocation, and simulates a User Service connection outage
without stopping shared services. Keep supplier data unchanged during the check
so before/after response comparisons are meaningful.

```bash
./.venv/bin/python - <<'PYSMOKE'
import os
from getpass import getpass
from typing import Annotated

import httpx
from fastapi import Depends
from fastapi.testclient import TestClient

from app.auth import require_admin
from app.clients.user_service import TrustedIdentity, UserServiceClient
from app.config import Settings
from app.main import create_app

settings = Settings()
app = create_app(settings)

@app.get("/test-only/admin")
def check_admin(user: Annotated[TrustedIdentity, Depends(require_admin)]):
    return {"id": str(user.id), "role": user.role}

with TestClient(app) as supplier, httpx.Client(
    base_url=str(settings.user_service_url),
    timeout=settings.auth_timeout_seconds,
    follow_redirects=False,
    trust_env=False,
) as users:
    assert supplier.get("/ready").status_code == 200
    listing = supplier.get("/suppliers")
    assert listing.status_code == 200
    assert listing.json()["items"], "Seed an active supplier first"
    identity = listing.json()["items"][0]["id"]
    paths = ["/suppliers", f"/suppliers/{identity}", "/categories", "/areas"]
    baseline = {}
    for path in paths:
        response = supplier.get(path)
        assert response.status_code == 200
        baseline[path] = response.json()

    def browse(headers):
        for path in paths:
            response = supplier.get(path, headers=headers)
            assert response.status_code == 200
            assert response.json() == baseline[path]

    login = users.post("/login", json={
        "nus_student_number": os.environ["ADMIN_STUDENT_NUMBER"],
        "password": getpass("Administrator password: "),
    })
    assert login.status_code == 200, "Administrator login failed"
    payload = login.json()
    headers = {"Authorization": "Bearer " + payload["access_token"]}
    try:
        assert payload["user"]["role"] == "admin", "Use an administrator account"
        assert supplier.get("/test-only/admin", headers=headers).status_code == 200
        browse(headers)
    finally:
        assert users.post("/logout", headers=headers).status_code == 204

    rejected = supplier.get("/test-only/admin", headers=headers)
    assert rejected.status_code == 401
    assert rejected.headers["WWW-Authenticate"] == "Bearer"
    browse({})
    browse(headers)  # The revoked token must not interrupt public browsing.

    def unavailable(request):
        raise httpx.ConnectError("Simulated outage", request=request)

    original = app.state.user_service_client
    outage = UserServiceClient(settings, transport=httpx.MockTransport(unavailable))
    app.state.user_service_client = outage
    try:
        browse({})
        browse(headers)
        assert supplier.get("/health").status_code == 200
        assert supplier.get("/ready").status_code == 200
        assert supplier.get("/test-only/admin", headers=headers).status_code == 503
    finally:
        app.state.user_service_client = original
        outage.close()
print("Public browsing, administrator authorization, revocation, and outage checks passed.")
PYSMOKE
```

The live login/logout check was not performed during this increment: no services
were running in this checkout's Compose project. The mock-backed public-read,
protected-route, and probe tests were run; they do not establish live deployment
or database integration behavior.

### Administrative listings

`GET /admin/suppliers` accepts `status=active|deleted|all`, defaulting to
`active`. Active selects null `deleted_at`, deleted selects non-null values,
and all applies no deletion filter. Unsupported values return `422`.
All views require administrator authorization and use the same area/category
filters, name-then-ID sorting, and pagination envelope as ordinary listings.
Apply the status filter before pagination and before counting `total`.
Ordinary listings remain active-only. Administrative detail reads can retrieve
active or deleted records; these views do not introduce restoration or editing
of deleted suppliers. The UI starts with Active and offers Deleted and All.

### Error bodies

Errors contain an `error` object with a stable machine-readable `code` and a
human-readable `message`. Frontend logic branches on the code, not message text.
Use `SUPPLIER_DUPLICATE` for duplicate conflicts and `VERSION_CONFLICT` for
stale versions (both `409`). A stale-version response instructs the frontend
to reload; omit the current version and supplier data and do not automatically
retry the edit.

```json
{
  "error": {
    "code": "VERSION_CONFLICT",
    "message": "This supplier has changed. Reload it before trying again."
  }
}
```

Validation errors use `422` and `VALIDATION_ERROR`, with a `details` array of
issues. Each issue has `fields` (an array of field paths), `code`, and `message`.
Report all independently detectable issues together. Use paths such as `area`,
`location.latitude`, `query.expected_version`, and `category_ids.1`; array
positions are zero-based and refer to the original request before deduplication.
Identify each unknown category entry separately. Never save part of an invalid
mutation.

```json
{
  "error": {
    "code": "VALIDATION_ERROR",
    "message": "Some fields are invalid.",
    "details": [
      {
        "fields": ["opening_time", "closing_time"],
        "code": "INCOMPLETE_SCHEDULE",
        "message": "Set both opening and closing times, or clear both for unknown hours."
      }
    ]
  }
}
```

A schedule-pair error is one issue associated with both fields; the frontend
highlights the pair and displays the message once. Single-field issues also
use a `fields` array. An optional frontend "Hours unknown" control may clear
both times together; server validation remains mandatory.

### Reusing validation in future API and import code

`app/schemas.py` defines separate client inputs and cleaned results.
`app/validation/suppliers.py` provides the entry points that collect parsing
errors and all independently detectable domain issues:

```python
from app.validation.suppliers import (
    validate_supplier_create,
    validate_supplier_patch,
)

# The caller obtains category UUIDs; validation performs no database queries.
created_values = validate_supplier_create(raw_create_body, existing_category_ids)
updated_values = validate_supplier_patch(
    raw_patch_body, stored_editable_values, existing_category_ids,
)
```

These are usage examples for future callers, not implemented mutation routes.
Callers must pass the existing category UUIDs as an iterable of `UUID` objects.
Every supplied category is checked at its original zero-based position before
valid duplicates are removed in first-seen order. A supplied PATCH category list
replaces the stored selection. Category definitions remain migration-managed.
Only successful validation returns cleaned values; any issue raises
`DomainValidationError`, and the future caller must not save part of that input.

Future create and update routes must call these aggregate-validation functions.
Accept an unparsed JSON value, for example a FastAPI parameter
`payload: Any = Body(...)`, then pass it to the appropriate function. Do not use
`SupplierCreateInput` or `SupplierPatch` as an automatic route-body parser before
calling the aggregate validator: an early parsing failure would stop category
membership or schedule checks that could still find errors. Likewise, do not
pre-validate individual business fields and return on the first issue. Invalid
JSON cannot reach domain validation because no usable input object exists.

Creation validates complete input. PATCH must merge with a snapshot of stored
editable values first: name, area, category UUIDs, optional text, and both times.
The update service should build that mapping explicitly from the stored record;
do not pass an ORM object with server-managed fields through the creation schema.
`validate_supplier_patch` copies editable values, applies the raw patch, validates
the merged result, and recalculates the closing-day offset. It does not mutate
the supplied mapping or category list. Persistence, concurrency checks, and
version increments (including for empty patches) belong to the future service.

Omitted PATCH fields retain stored values. Explicit null clears nullable fields;
null required text or category lists is invalid. Blank optional text becomes
null; required text must remain nonblank after trimming. Floor values remain
strings, including `01` and `B1`. For callers using the patch model to inspect
presence, `SupplierPatch().model_dump(exclude_unset=True)` is empty, whereas
`SupplierPatch(description=None).model_dump(exclude_unset=True)` includes
`description: None`. Preserve that distinction when passing data onward.

Changing only one time uses the other stored time. Later closing means offset 0;
earlier or equal closing means offset 1 (equal times represent 24 hours). Both
times missing or null on creation mean unknown hours. Clearing a known PATCH
schedule requires both times to be null; clearing just one produces one
`INCOMPLETE_SCHEDULE` issue naming both fields. An invalid time is reported as a
parsing/time issue without also being called an incomplete schedule. Clients
cannot supply the derived offset, supplier ID, or other server-managed fields;
PATCH also forbids coordinates and `expected_version` in its body.

The application factory registers handlers for `DomainValidationError` and
FastAPI `RequestValidationError`. Both return HTTP 422 using
`DomainValidationError.to_dict()` and the envelope above. Request body paths
omit `body.` (for example `location.latitude` and `category_ids.1`), while query
paths retain `query.`. Malformed JSON returns `INVALID_JSON` with an empty
`fields` array. Responses contain only issue `fields`, `code`, and safe `message`
values; raw bodies, rejected values, exception context, and internal messages
are not copied into the response. This handler unifies request-error formatting;
it does not replace calling aggregate validation in future mutation routes.

The seed parser applies reviewed source mappings and calls
`validate_supplier_seed_values` for shared scalar rules without category UUIDs.
It translates `DomainValidationError` into contextual source issues. Controlled
category names remain unresolved until persistence is implemented. Domain
validation itself performs no CSV parsing, seed corrections, or database access.

### Validation tests and coverage

Run all unit and API checks from `supplier-service/`:

```bash
./.venv/bin/python -m pytest tests/unit tests/api -q
```

Coverage reviewed against [the domain-input guide](reference/08-validate-supplier-input.md):

| Coverage | Tests |
| --- | --- |
| Finite coordinates, inclusive boundaries, precision, approved slash-combined areas, and daily offsets/unknown hours | `tests/unit/test_domain_validation.py` |
| Whitespace, optional nulls, string floor labels, unknown areas, empty/malformed/unknown categories, forbidden fields, and aggregate creation failures | `tests/unit/test_supplier_create_validation.py` |
| Missing versus null, stored-time merging, transitions from either time, category replacement, immutable fields, aggregate failures, and unchanged inputs | `tests/unit/test_supplier_patch_validation.py` |
| Both 422 handlers, body/query paths, invalid JSON, safe messages, original category positions, and multiple issues including a single schedule-pair issue | `tests/api/test_validation_errors.py` |
| Existing liveness and readiness behavior | `tests/api/test_health.py`, `tests/api/test_readiness.py` |

Observed agent verification: 357 unit/API tests passed with one existing
Starlette/AnyIO dependency deprecation warning. No requested checks were
unavailable. These checks require neither a live database nor User Service;
database integration and real mutation/import workflows were not exercised.

## Explicit seed import

The `supplier-seed` tools service imports the reviewed CSV explicitly; ordinary
API startup never seeds. It shares `foc-supplier-service:local` with the API and
migrator. The image packages `app/`, Alembic files, and module-relative
`seed/manifest.json` and `seed/area_mapping.json`, readable by UID 10001.
The root CSV is mounted read-only at `/seed/supplier-seed-data.csv`.
The job joins only `supplier-private`, publishes no ports, disables the API
healthcheck, and never automatically restarts. No User Service connection is made.

Run from the repository root with Docker and Compose available. Configure the
root `.env` as described in [fresh installation](docs/migrations.md#fresh-installation):
`POSTGRES_USER` and `POSTGRES_PASSWORD` are needed for full Compose interpolation;
set `SUPPLIER_POSTGRES_DB`, `SUPPLIER_POSTGRES_USER`,
`SUPPLIER_POSTGRES_PASSWORD`, `SUPPLIER_MIGRATION_PASSWORD`, and
`SUPPLIER_RUNTIME_PASSWORD`. Provision PostGIS and the migrator/runtime roles, apply migrations, and
apply `database/runtime-grants.sql` before seeding. Use URL-safe passwords or
correctly encode URL components. Compose supplies required `USER_SERVICE_URL`
and optional timeout/log settings; local Python runs must export those settings
and `DATABASE_URL` explicitly. The command does not load `.env` itself.

```bash
docker compose --profile tools config --quiet
docker compose build supplier-service
# After administrator bootstrap; stop if migration fails:
docker compose run --rm supplier-migrate
# Apply/review runtime grants using the linked installation guide.
docker compose --profile tools run --rm supplier-seed --dry-run
docker compose --profile tools run --rm supplier-seed
```

The empty Compose command lets appended `--dry-run` reach the Python entrypoint.
Both modes wait for healthy `supplier-db` and successful `supplier-migrate`
completion. A previous migration job is not a deployment scheduler: follow the
[existing-volume sequence](docs/migrations.md#deploying-a-new-image-with-the-existing-volume)
for a new image. The command independently requires installed Alembic heads to
exactly match the nonempty packaged heads. It never applies migrations itself.

From `supplier-service/`, the equivalent local commands are:

```bash
./.venv/bin/python -m app.commands.seed_suppliers --file ../data/csv/supplier-seed-data.csv --dry-run
./.venv/bin/python -m app.commands.seed_suppliers --file ../data/csv/supplier-seed-data.csv
```

Validation, accepted records, and diagnostics use one loaded input snapshot.
Any invalid input rejects the whole batch; diagnostic valid rows are never a
partial import. Mappings resolve relative to the module, regardless of CSV
location. No mode generates permanent UUIDs or changes the source or mappings.

Dry run classifies in a read-only transaction. Its proposed inserts, existing
identity skips (including deleted identities), and conflicts are a preview that
may change before execution. Real imports acquire PostgreSQL transaction-scoped
advisory lock `3219001`, then reclassify and insert suppliers and all assignments
in one transaction. A waiting importer classifies after acquiring the lock.
API-style writers do not take this lock; `uq_supplier_active_name_location`
remains the final active-duplicate concurrency guard.

An existing manifest UUID is skipped only when immutable longitude and latitude
match exactly at database point precision. All editable values, timestamps,
versions, category assignments, and soft deletion are preserved. Coordinate
mismatches require review, never overwrites or restoration. Missing UUIDs are
checked for active duplicates using `lower(btrim(name))` and exact coordinates,
including candidates within the batch. Deleted matches do not block a new UUID.
Categories must already exist from migrations. See the
[confirmed identity policy](docs/seed-mapping.md#confirmed-database-classification-policy).

The JSON report includes:

- `source_count`, `validated_supplier_count`, `category_counts`, and
  `total_category_assignments`: source/diagnostic totals, not committed row counts.
- `reviewed_corrections` and `validated_records`: the reviewed corrections and
  normalized diagnostic values with source context; never an accepted partial batch.
- `decisions` and `issues`: seed key, UUID, source file/row, action and reason,
  with independently detectable validation or classification issues retained.
- `proposed_insert_count`, `inserted_count`, `skipped_count`, `conflict_count`:
  distinguish classified candidates from confirmed committed inserts. A preview
  has zero committed inserts; a rerun normally has 21 skips.
- `valid`, `preview`, `dry_run`, `batch_rejected`, `committed`, `rolled_back`,
  `commit_outcome`, and `message`: batch status. Confirmed rollback reports zero
  inserts. `commit_outcome: "unknown"` means acknowledgement was lost: inserted
  count, committed, rolled-back and rejection flags are null, not proof of no
  writes. Reconcile manifest UUIDs or rerun the idempotent import with the same
  source/mappings once connectivity returns. `not_attempted` / `not_committed`
  do not claim a successful commit; `committed` confirms it.

Exit 0 means a valid conflict-free preview or successful import. Invalid input,
conflicts, configuration/migration/connectivity/write failures, and uncertain
commit outcomes return nonzero; argparse usage errors return 2. Database
errors use safe diagnostics. Review conflicts and source associations while
preserving permanent keys and UUIDs; do not regenerate identities to bypass them.

The real source contains 21 suppliers and 26 assignments across four migrated
categories (Food 16, Coffee 5, Shopping 3, Printing 2). Exactly five reviewed
midnight-to-23:59 pairs become daily 24-hour schedules; Supersnacks remains
11:00–02:00, closing-day offset 1. Schedules use Asia/Singapore wall-clock times.
A first import into an empty migrated database inserts 21; the second inserts
zero and preserves totals of 21 suppliers, four categories, and 26 assignments.

### Isolated verification

Packaging verification on 30 September 2026 passed on retry using Docker
Linux/ARM64 and the actual repository CSV bind mount. Compose configuration and
both image builds passed. The disposable database became healthy; administrator
bootstrap, migrations, and runtime grants completed. UID 10001 could read the
packaged metadata and Alembic configuration. The migration dependency exited 0
before seed execution. A first read-only preview left totals at 0 suppliers,
four categories, and zero assignments; the first import inserted 21 suppliers;
the second inserted zero and skipped 21, retaining totals of 21/4/26. A final
preview skipped 21 and preserved those totals. All command checks exited 0.
The disposable project's containers, network, and volume were removed.
The earlier Docker `Created` stall did not recur. Native AMD64 execution was
not tested in this rehearsal.

Use a unique Compose project name (for example `foc-seed-check`) and disposable
database credentials/name. Prefix **every** installation and test command with
`docker compose -p foc-seed-check`; this isolates the named volume and network.
Follow fresh installation steps 1–5 for bootstrap, migration, and runtime grants,
without starting the API. Then run:

```bash
docker compose -p foc-seed-check --profile tools config --quiet
docker compose -p foc-seed-check build supplier-service
docker compose -p foc-seed-check --profile tools run --rm supplier-seed --dry-run
docker compose -p foc-seed-check --profile tools run --rm supplier-seed
docker compose -p foc-seed-check --profile tools run --rm supplier-seed
docker compose -p foc-seed-check --profile tools run --rm supplier-seed --dry-run
docker compose -p foc-seed-check ps -a supplier-db supplier-migrate
docker compose -p foc-seed-check exec -T supplier-db sh -c \
  'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT (SELECT count(*) FROM supplier) AS suppliers, (SELECT count(*) FROM category) AS categories, (SELECT count(*) FROM supplier_category) AS assignments"'
# Only for this disposable project:
docker compose -p foc-seed-check --profile tools down --volumes --remove-orphans
```

Check counts before and after each preview: it must leave them unchanged.
Inspect JSON for first import 21 inserts and second import 0 inserts/21 skips;
check migration exit 0 and database totals 21/4/26. Do not run the cleanup against
a persistent project. For automated rollback, identity and concurrency checks,
from `supplier-service/` run:

```bash
./.venv/bin/python -m pytest tests/unit tests/api -q
./.venv/bin/python -m pytest tests/integration/test_seed_import.py -q
```

The integration command requires `TEST_DATABASE_URL` pointing to isolated
PostgreSQL/PostGIS with a database name ending `_test`, distinct from
`DATABASE_URL`. Its role must create disposable databases and install PostGIS;
see the integration configuration above. Install `requirements-dev.txt` first.

## Deployment and Verification

Run the API and PostgreSQL/PostGIS as separate containers. Persist database
state using a named volume and keep database access private to the service.

Manage schema changes through versioned migrations.

Initial verification should cover:

- Required-field and opening-hours validation.
- Creation with multiple categories.
- Prevention of duplicate category assignments.
- Transaction rollback when a mutation fails.
- Partial updates and explicit clearing of optional fields.
- Rejection of stale versions.
- Soft deletion and exclusion from available listings.
- Repeatable imports and persistence across container recreation.

## Requirements to Reconcile

The following design choices should be reflected in the project requirements:

- Supplier IDs are immutable random UUIDs, replacing D1's location-and-name
  hash definition.
- Description is optional and specifically represents pickup directions.
- Area and one or more categories are mandatory.
- General daily hours are supported initially.
- The PATCH allowlist above expands D1's name-and-description-only updates.
- Closing-day offset is derived by the server, not supplied by clients.
- Direct administrator CRUD is an intermediate implementation before
  user proposals and administrator approval are introduced.

## Future Enhancements

### Weekly Opening Schedules

Introduce a `supplier_hours` table when weekday-specific schedules are
required.

It can represent each weekday as open, closed or unknown, with opening
time, closing time and closing-day offset for open days.

Migrate existing daily schedules into seven weekday records. Migrate
unknown hours into seven unknown records. Update the API and UI before
removing the original hours columns.

### Supplier Audit History

Introduce `supplier_audit` to record successful changes.

Proposed information includes:

- Audit entry ID.
- Supplier ID.
- Operation.
- Authenticated actor ID.
- Timestamp.
- Before and after values, including categories.
- Optional change-request ID once approval workflows exist.

Write the audit record in the same transaction as the supplier mutation.
An initial baseline can be captured when auditing is introduced, but
earlier changes cannot be reconstructed as historical events.

### Supplier Change Requests

Introduce `supplier_change_request` for user-proposed creations, updates
and removals.

Proposed information includes:

- Request ID and operation.
- Target supplier ID where applicable.
- Proposed values.
- Supplier version on which the proposal is based.
- Request status.
- Requester ID.
- Reviewer ID, decision timestamp and review reason.
- Creation timestamp.

Pending and rejected requests do not modify approved supplier records.

Approval should check for stale versions, apply the supplier mutation,
record the audit entry and finalize the request in one transaction.

The approval workflow should reuse the same validation and mutation logic
as direct administrator CRUD.

## AI Use Summary (Supplier Service)

Codex (GPT-6) provided **Requirements work**, **Learning support**,
**Boilerplate generation**, **Writing implementation code**, **Debugging
assistance**, and **Refactoring and documentation improvements** for database
migrations, role access, service image setup, and integration checks, including
Supplier-related changes to root `.env.example`, `compose.yaml`, and `README.md`. The
coordinate-index expression was aligned after Alembic detected metadata drift.

Observed verification: 54 tests passed against disposable PostGIS, including
runtime-role and isolated downgrade/re-upgrade checks; Alembic found no drift;
the service image built and reported revision `0002` as head. Keith confirmed
review of all affected changes.

See the [canonical Supplier Service usage record](ai/usage-log.md#ai-20260929-001).
Some prompt excerpts are redacted at the user's request; original
per-message timestamps are unavailable. No file header exceptions apply.

For the readiness change, Codex (GPT-6) provided **Writing implementation code**
for `app/routes/health.py`, `tests/api/test_health.py`, and the new
`tests/api/test_readiness.py`, following the specified existing engine and Alembic
architecture. The endpoint and isolated tests were retained. Agent verification:
40 API/unit tests passed with one dependency deprecation warning, and
`git diff --check` passed. PostgreSQL integration was not verified for this change.
Keith confirmed review of all affected readiness changes; no human test rerun
is claimed. The [readiness usage record](ai/usage-log.md#ai-20260929-002)
contains the exact implementation prompt and final response. Original message
timestamps are unavailable; no redactions or header exceptions apply to this entry.

For Compose migration gating, Codex (GPT-6) provided **Boilerplate generation**
for root `compose.yaml` and `supplier-service/Dockerfile`: a shared image,
a dedicated migration job, successful-completion startup gating, and a bounded
`/ready` image probe. These changes were retained and reviewed by Keith.
Agent checks passed for Compose validation, image build, packaged revision
inspection, explicit migration execution, healthy startup, deliberate disposable
migration failure blocking API startup, recovery, and `git diff --check`.
The full multi-service stack and existing development database were not tested;
no human test rerun is claimed. See the [Compose migration-gating record](ai/usage-log.md#ai-20260929-003)
for the exact prompt and verbatim response excerpts. Original message timestamps
are unavailable; no redactions or header exceptions apply to this entry.

For deployment documentation and the follow-up port correction, Codex (GPT-6)
provided **Refactoring and documentation improvements** and **Debugging assistance**
for `docs/migrations.md` and this README. The guide and README changes were
retained and reviewed by Keith. Disposable checks verified fresh installation,
grants, revision upgrade with surviving data, readiness/liveness failure and
recovery, and failed-migration startup blocking. After correcting the test-only
network setup, all 74 tests passed with no skips and one dependency warning.
Shell syntax, links, and `git diff --check` passed. The later wording correction
passed `git diff --check`; Docker checks were not rerun for it. Full-stack,
AMD64, archived-image, and development/production deployments were not verified.
See the [deployment documentation record](ai/usage-log.md#ai-20260929-004) for
both exact prompts, verbatim response excerpts, initial test-setup failures,
and verification limits. Original timestamps are unavailable; no redactions or
header exceptions apply. No human test rerun is claimed.


For creation validation, Codex (GPT-6) provided **Writing implementation code**
for `app/schemas.py`, `app/validation/suppliers.py`, the parsing-error adapter in
`app/validation/errors.py`, and `tests/unit/test_supplier_create_validation.py`.
The work remains in the working tree. Agent verification: 112 creation tests and
97 existing domain tests passed, with one dependency deprecation warning per run;
no requested checks remained unavailable. The initial test-file path error was
corrected. Keith confirmed review of all four affected files; no human test rerun
is claimed. The
[creation validation record](ai/usage-log.md#ai-20260930-001) contains the exact
prompt and verbatim final response. Original timestamps are unavailable; no
redactions or header exceptions apply to this entry.


For PATCH validation, Codex (GPT-6) provided **Writing implementation code** and
**Refactoring and documentation improvements** for `app/schemas.py` and
`app/validation/suppliers.py`, plus **Writing implementation code** for
`tests/unit/test_supplier_patch_validation.py`. The retained work tracks supplied
fields, validates merged editable values without mutating inputs, and documents
future update-service usage. Keith confirmed review of all three affected files.
Agent checks passed 90 PATCH tests and 209 creation/domain regression tests, with
one existing dependency warning per run and no unavailable requested checks.
No human test rerun is claimed. The [PATCH validation record](ai/usage-log.md#ai-20260930-002)
contains the exact prompt and verbatim final response. Original timestamps are
unavailable; no redactions or header exceptions apply to this entry.


For HTTP validation integration, Codex (GPT-6) provided **Writing implementation
code** for `app/main.py`, `app/validation/errors.py`, and
`tests/api/test_validation_errors.py`, plus **Refactoring and documentation
improvements** for error conversion and this README's future API/import guidance.
The handlers, safe error conversion, test-only routes, and documentation were
retained and all four affected files were reviewed by Keith. Agent verification:
357 unit/API tests passed, including health and readiness, with one existing
dependency warning and no unavailable requested checks. Coverage was reviewed
against the domain-input guide; final syntax, whitespace, and documentation
checks passed. No human test rerun is claimed. The
[HTTP validation record](ai/usage-log.md#ai-20260930-003) contains the exact prompt
and verbatim final response. Original timestamps are unavailable; no redactions
or header exceptions apply to this entry.


For permanent seed data, Codex (GPT-6) provided **Requirements work** interpreting
and formatting `seed/manifest.json` and `seed/area_mapping.json`, authored fixed
seed labels and one-time UUIDv4 values, and provided **Writing implementation code**
for `tests/unit/test_seed_mapping.py`. All three files were retained and reviewed
by Keith. Agent verification: 12 focused tests passed with one dependency warning;
the source CSV SHA-256 was unchanged. No human test rerun is claimed. The
[permanent seed mapping record](ai/usage-log.md#ai-20260930-004) contains the exact
prompt and verbatim final response. Original timestamps are unavailable; no
redactions apply. Header exceptions: `supplier-service/seed/manifest.json` and
`supplier-service/seed/area_mapping.json` are strict JSON, which cannot contain
comments.


For CSV source loading, Codex (GPT-6) provided **Writing implementation code** and
**Refactoring and documentation improvements** for `app/commands/seed_parsing.py`,
**Writing implementation code** for `tests/unit/test_seed_source.py`, and
**Boilerplate generation** for `app/commands/__init__.py` and the CP1252 fixture.
The retained implementation validates source and JSON structures, matches permanent
identities, and collects structured issues. Final refinements retain malformed rows
for duplicate detection and correct syntax-error line numbers after blank lines.
Agent verification: 55 focused tests passed with one existing dependency warning;
all 21 real associations survive reordering. The production CSV hash was verified
unchanged during implementation. Keith confirmed review of all four affected files,
including the final refinements. No human test rerun is claimed.
The [CSV source-loading record](ai/usage-log.md#ai-20260930-005) records the original
exact prompt and response excerpts for the combined task. Original timestamps are
unavailable. Header exception: `supplier-service/tests/fixtures/seed_source.csv`
is CP1252 CSV data; comments would alter its contents and parsing.


For shared seed scalar validation, Codex (GPT-6) provided **Writing implementation
code** and **Refactoring and documentation improvements** for `app/schemas.py` and
`app/validation/suppliers.py`, plus **Writing implementation code** for
`tests/unit/test_supplier_seed_validation.py`. The retained work shares text, area,
location, and schedule rules while keeping category names with the importer and
preserving API create/PATCH contracts. Keith confirmed review of all three files.
Agent verification: 473 unit/API tests passed, including 61 new seed tests, with
one existing dependency warning; `git diff --check` passed. No human test rerun is
claimed. The [shared scalar validation record](ai/usage-log.md#ai-20260930-006)
contains the exact prompt and verbatim final response. Original timestamps are
unavailable; no redactions or header exceptions apply to this entry.


For seed normalization, Codex (GPT-6) provided **Writing implementation code** and
**Refactoring and documentation improvements** for `app/commands/seed_parsing.py`,
and **Writing implementation code** for `tests/unit/test_seed_normalization.py`.
The retained implementation returns typed scalar values and controlled category
names, applies identity-based reviewed schedule corrections, maps exact image URLs,
and withholds every parsed record when any issue exists. Keith confirmed review
of both files. Agent verification: 163 focused tests passed with one existing
dependency warning; real-dataset checks covered all 21 records, five corrections,
Supersnacks, category totals, image assignments, and unchanged CSV bytes.
`git diff --check` passed; no human test rerun is claimed. The
[seed normalization record](ai/usage-log.md#ai-20260930-007) contains the exact prompt
and verbatim final response. Original timestamps are unavailable; no redactions
or header exceptions apply to this entry.


For the seed dry-run command, Codex (GPT-6) provided **Writing implementation
code** for `app/commands/seed_suppliers.py` and `tests/unit/test_seed_command.py`,
and **Refactoring and documentation improvements** for this README. The command,
subprocess tests, and usage guidance were retained and reviewed by Keith.
Agent verification: the real CSV produced 21 suppliers, 26 category assignments,
five corrections, and no issues; 528 unit/API tests passed with one existing
dependency warning. Subprocess checks verified absent database configuration,
inert import, no database imports, stable UUIDs/counts, and unchanged source/mapping
bytes. Final source-data, syntax, whitespace, and README checks passed. No requested
checks were unavailable; no human test rerun is claimed. The
[dry-run command record](ai/usage-log.md#ai-20260930-008) contains the exact prompt
and verbatim final response. Original timestamps are unavailable; no redactions
or header exceptions apply to this entry.


For database seed classification, Codex (GPT-6) provided **Boilerplate generation**
for `app/repositories/__init__.py` and `app/services/__init__.py`, **Writing
implementation code** for `app/repositories/suppliers.py`,
`app/services/seed_import.py`, and `tests/integration/test_seed_import.py`, and
**Refactoring and documentation improvements** for `docs/seed-mapping.md`.
All six files were retained and reviewed by Keith. Classification preserves
caller-owned sessions, checks immutable coordinates for existing active/deleted
UUIDs, resolves migrated categories, and collects active and batch duplicates.
Agent verification: 545 tests passed (17 isolated migrated PostgreSQL/PostGIS
integration tests and 528 unit/API tests), with one existing dependency warning.
Database snapshots and pending caller state were unchanged by classification.
The scoped documentation whitespace check passed; the repository-wide check
reported pre-existing whitespace in the usage log. No human test rerun is claimed.
The [database classification record](ai/usage-log.md#ai-20260930-009) contains the
exact prompt and verbatim final response. Original timestamps are unavailable;
no redactions or header exceptions apply to this entry.


For atomic supplier import, Codex (GPT-6) provided **Writing implementation code**
and **Refactoring and documentation improvements** for
`app/services/seed_import.py` and `app/repositories/suppliers.py`, plus **Writing
implementation code** for `tests/integration/test_seed_import.py`. All three files
were retained and reviewed by Keith. The service owns one transaction, acquires
advisory lock 3219001 before classification, preserves skipped identities, inserts
suppliers and assignments atomically, and separates duplicate/UUID conflicts.
Agent verification: 558 tests passed (30 seed integration cases and 528 unit/API
tests), with one existing dependency warning. Coverage includes real CSV reruns,
unchanged administrator edits and deletion state, assignment and pre-commit
rollback, and synchronized independent-connection import/API races for both
commit and rollback. Disposable migrated databases and the test container were
removed. Python syntax and whitespace checks passed for the three changed files.
No human test rerun is claimed. The
[atomic import record](ai/usage-log.md#ai-20260930-010) contains the exact prompt
and verbatim final response. Original timestamps are unavailable; no redactions
or header exceptions apply to this entry.


For the [database-aware seed command](ai/usage-log.md#ai-20260930-011), Codex
(GPT-6) provided **Writing implementation code** and **Refactoring and documentation
improvements** for `app/commands/seed_suppliers.py`, `app/services/seed_import.py`,
`tests/unit/test_seed_command.py`, and `tests/integration/test_seed_import.py`.
Retained changes added database previews/imports, exact migration-head gating,
read-only transactions, safe reporting, resource lifecycle checks, and CLI tests.
Agent verification passed 591 tests with one existing dependency warning.

For the [snapshot and passwordless fixes](ai/usage-log.md#ai-20260930-011), Codex
(GPT-6) provided **Writing implementation code** and **Refactoring and documentation
improvements** for `app/commands/seed_parsing.py`, `app/commands/seed_suppliers.py`,
and the two seed command/import test files. The retained fixes use one loaded
snapshot for accepted records and diagnostics and guard optional password checks.
Agent verification passed 596 tests, including the seed integration suite against
passwordless PostGIS, with one existing dependency warning.

For [uncertain commit outcomes](ai/usage-log.md#ai-20260930-011), Codex (GPT-6)
provided **Writing implementation code**, **Refactoring and documentation
improvements**, and **Debugging assistance** for `app/services/seed_import.py`,
`app/commands/seed_suppliers.py`, and `tests/integration/test_seed_import.py`.
The retained fix distinguishes confirmed rollback from unknown commit outcomes,
uses null committed counts when acknowledgement is lost, preserves safe guidance,
and discards uncertain connections without masking the original failure. Tests
confirmed persisted rows after simulated lost acknowledgement and an unchanged
idempotent rerun. Final agent verification passed 599 tests with one existing
dependency warning; syntax and whitespace checks passed. Temporary database
resources were removed after each task.

Keith confirmed review of all five affected files and all retained changes across
these three exchanges. No human test rerun is claimed. The consolidated record contains Prompts 1–3 and their verbatim final responses.
Original message timestamps are unavailable; no redactions or header exceptions
apply to these entries.


For [explicit seed command packaging](ai/usage-log.md#ai-20260930-012), Codex
(GPT-6) provided **Boilerplate generation** for `Dockerfile` and root
`compose.yaml`, and **Refactoring and documentation improvements** for this
README and `docs/seed-mapping.md`. Retained changes package metadata, configure
the explicit tools service, and document setup, preview/import outcomes,
identity preservation, locking, and isolated checks. Within this exchange,
Compose validation, both image builds, isolated bootstrap, migrations, and
grants passed on Linux/ARM64. Docker then stalled container startup; seed runs,
non-root metadata access, dependency-order execution, and rerun totals were
unverified, and cleanup timed out. These are the historical results for this
entry, not a claim about subsequent operational checks. Keith confirmed review
of all four affected files; no human test rerun is claimed. The exact prompt and
verbatim final response are recorded. Original message timestamp unavailable;
no redactions or header exceptions apply.


For [active supplier detail reads](ai/usage-log.md#ai-20260930-013), Codex
(GPT-6) provided **Writing implementation code** and **Refactoring and
documentation improvements** for `app/repositories/suppliers.py` and
`app/services/suppliers.py`, and **Writing implementation code** for
`tests/integration/test_supplier_reads.py`. Retained work provides immutable
active-only details, eager categories, named PostGIS coordinates, and safe
availability failures while preserving seed identity behavior. Agent checks
passed 612 tests across the new reads, seed integration, unit, and API suites,
with one existing dependency warning; syntax and scoped whitespace checks passed.
The disposable PostGIS container was removed. The full schema/runtime-role
integration suite was not run. Keith confirmed review of all three files;
no human test rerun is claimed. The exact prompt and final response are recorded;
original message timestamp unavailable. No redactions or header exceptions apply.


For [active supplier listing and pagination](ai/usage-log.md#ai-20260930-014),
Codex (GPT-6) provided **Writing implementation code** and **Refactoring and
documentation improvements** for `app/repositories/suppliers.py` and
`app/services/suppliers.py`, and **Writing implementation code** for
`tests/integration/test_supplier_reads.py`. Retained changes add active filtered
pages with matching totals, deterministic ordering, pagination validation, and
shared detail/list loading and failure handling. Agent checks passed 639 tests
across reads, seed integration, unit, and API suites, with one existing dependency
warning; syntax and scoped whitespace checks passed. Fresh-session tests verified
three queries per nonempty page at multiple limits and unchanged stored data.
The disposable PostGIS container was removed. The full schema/runtime-role
integration suite was not run. Keith confirmed review of all three files;
no human test rerun is claimed. The exact prompt and final response are recorded;
original message timestamp unavailable. No redactions or header exceptions apply.


For [controlled category and area readers](ai/usage-log.md#ai-20260930-015),
Codex (GPT-6) provided **Writing implementation code** and **Refactoring and
documentation improvements** for `app/repositories/suppliers.py` and
`app/services/suppliers.py`, and **Writing implementation code** for
`tests/integration/test_supplier_reads.py`. Retained readers return ordered,
immutable category values independently of supplier assignments and exact
approved area choices without database access. Category failures reuse the safe
service boundary. Agent checks passed 653 read/seed integration and unit/API
tests, plus a separate database-independent area test, with an existing dependency
warning. Syntax and scoped whitespace checks passed; the disposable PostGIS
container was removed. Full schema/runtime-role integration coverage was not run.
Keith confirmed review of all three files; no human test rerun is claimed.
The exact prompt and final response are recorded; original message timestamp
unavailable. No redactions or header exceptions apply.


For [supplier read response models](ai/usage-log.md#ai-20260930-016), Codex
(GPT-6) provided **Writing implementation code** for `app/schemas.py` and
`tests/api/test_supplier_reads.py`. Retained models explicitly convert loaded
read values, preserving nulls, precision, ordering, and pagination metadata.
Agent checks passed 11 new serialization tests and all 552 unit/API tests with
one dependency warning; scoped whitespace checks passed. Database integration
tests were not run. Keith confirmed review of both files; no human test rerun
is claimed. The exact prompt and verbatim final response are recorded; original
message timestamp unavailable. No redactions or header exceptions apply.


For [unregistered supplier GET adapters](ai/usage-log.md#ai-20260930-017),
Codex (GPT-6) provided **Writing implementation code** for
`app/routes/suppliers.py` and `tests/api/test_supplier_reads.py`. Retained handlers
use existing read services, parsed UUIDs/pagination, explicit response conversion,
and safe error envelopes. Tests verify cleanup and production route exclusion.
During this exchange, agent checks passed 37 serialization/read HTTP tests and
all 578 unit/API tests with one dependency warning; scoped whitespace checks
passed. Database integration tests were not run. Keith confirmed review of both affected files;
no human test rerun is claimed. The exact prompt and verbatim
final response are recorded; original timestamp unavailable. No redactions or
header exceptions apply. The router remains unregistered pending authentication.


For [controlled reference-data GET adapters](ai/usage-log.md#ai-20260930-018),
Codex (GPT-6) provided **Writing implementation code** for
`app/routes/reference_data.py` and `tests/api/test_supplier_reads.py`. Retained
handlers preserve controlled choices, safe category errors, and database-free
areas. Tests mount all four read adapters together and verify production exclusion.
Agent checks passed 43 read HTTP/serialization tests and all 584 unit/API tests
with one dependency warning; combined read collection passed with 97 tests and
scoped whitespace checks passed. Database integration tests were not run. Keith confirmed
review of both affected files; no human test rerun is claimed. The exact prompt
and verbatim final response are recorded; original timestamp unavailable. No
redactions or header exceptions apply. Production mounting awaits authentication.


For the [synchronous User Service client](ai/usage-log.md#ai-20260930-019),
Codex (GPT-6) provided **Writing implementation code** for
`app/clients/user_service.py` and `tests/unit/test_user_service_client.py`, and
**Boilerplate generation** for `app/clients/__init__.py`, `requirements.txt`,
and `requirements-dev.txt`. Retained work resolves opaque sessions through the
fixed profile endpoint, validates minimal trusted identities, maps failures to
explicit exceptions, closes the reusable client, and moves HTTPX into runtime
dependencies. During the implementation exchange, agent checks passed 71 focused
tests and all 655 unit/API tests with one existing dependency warning; scoped
whitespace checks passed. Live-service and database integration checks were not
run. Keith approved the original implementation across all five files; no human
test rerun is claimed. The exact prompt and verbatim final response are recorded;
original timestamp unavailable. No redactions or header exceptions apply.


For [User Service client lifecycle management](ai/usage-log.md#ai-20260930-020),
Codex (GPT-6) provided **Writing implementation code** for `app/main.py` and
`tests/api/test_startup.py`. Retained changes construct and share one client per
lifespan using existing settings, and clean up client and database resources on
shutdown or partial startup failure. Agent checks passed 10 startup tests and
all 666 unit/API tests with one existing dependency warning; scoped whitespace
checks passed. Live User Service and database integration checks were not run.
Keith subsequently confirmed review of both affected files; no human test rerun is claimed.
The exact prompt and verbatim final response are recorded; original timestamp
unavailable. No redactions or header exceptions apply.


For [composable authentication and administrator dependencies](ai/usage-log.md#ai-20260930-021),
Codex (GPT-6) provided **Writing implementation code** for `app/auth.py`,
`app/main.py`, and `tests/api/test_auth.py`. Retained changes resolve trusted
identities through the shared client, authorize administrators, and return safe
401/403/503 envelopes through a dedicated handler. Protection remains opt-in.
Agent checks passed 47 combined authentication/validation-error tests and all
695 unit/API tests, including 29 new authentication tests, with one existing
dependency warning; scoped whitespace checks passed. An initial test-file path
error was corrected before successful verification. Live-service and database
integration checks were not run. Keith confirmed review of all three files for
this implementation; no human test rerun is claimed. The exact prompt and
verbatim final response are recorded; original timestamp unavailable.
No redactions or header exceptions apply.


For [public supplier and reference-data reads](ai/usage-log.md#ai-20260930-022),
Codex (GPT-6) provided **Writing implementation code** for `app/main.py`,
`tests/api/test_supplier_reads.py`, `tests/api/test_health.py`,
`tests/api/test_readiness.py`, and the additional stale assertion correction in
`tests/api/test_validation_errors.py`; **Refactoring and documentation improvements**
updated both read-router docstrings and this README. Retained work mounts public
reads, proves authentication-outage independence with recording mock transports,
and documents a test-only login/logout and simulated-outage smoke harness.
Agent checks passed 121 focused tests and all 723 unit/API tests after the stale
exclusion assertion was corrected, with one existing dependency warning.
Python and smoke-harness syntax and scoped whitespace checks passed. No Compose
services were running, so live login/logout checks were not performed; database
integration tests were not run. Keith confirmed review of all eight affected
files; no human test rerun is claimed. The exact prompt and verbatim final
response are recorded; original timestamp unavailable. No redactions or header
exceptions apply.
