<!-- AI Assistance Disclosure:
Tool: Codex (model: GPT-6), date: 2026-09-28 to 2026-09-29
Scope: Documentation — describe database migration, role setup, and observed verification.
Author review: Keith confirmed review of all affected changes.
Details: ai/usage-log.md; ai-20260929-001
-->

# Supplier Service

The Supplier Service maintains the campus stores, facilities and locations
from which users can request pickups. It owns supplier information and
exposes an API for browsing and managing that information.

Other services access supplier information through the API. They do not
connect directly to the Supplier Service database.

The service provides validated startup configuration, `GET /health`,
interactive API documentation, and SQLAlchemy models for `supplier`,
`category`, and `supplier_category`. Application startup initializes a
database engine and session factory, and shutdown disposes of the engine.
Request-scoped sessions are closed without automatically committing;
service functions will own transaction boundaries.

The API and a persistent PostgreSQL/PostGIS database run through Docker
Compose. Alembic migrations create the schema and four controlled categories.
See [schema operations](docs/migrations.md) for bootstrap, role separation,
migration commands, and integration tests. The supplier business API remains future work.

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

These URLs and credentials are dummy local examples. The scaffold validates
URL formats but makes no database or User Service connections, so those
services do not need to be running for the health check.

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
not establish database readiness. Stop the server with **Ctrl+C**.

Run the tests from `supplier-service/`:

```bash
./.venv/bin/python -m pytest -q
```

Current unit and API tests use explicit dummy settings or temporary
environment variables and require no running database or User Service.
They cover the health response, configuration defaults and validation,
the required Psycopg driver scheme, rejection of invalid startup
configuration, and database engine initialization and disposal.

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

### Build and start

```bash
docker compose config --quiet
docker compose build supplier-db supplier-service
docker compose up -d supplier-db supplier-service
docker compose ps supplier-db supplier-service
```

The API starts after the database health check succeeds. Both containers
should eventually report healthy. These commands start only the supplier
containers; the scaffold does not yet require User Service to be running.

Open these addresses:

- Health: <http://127.0.0.1:8081/health>
- API documentation: <http://127.0.0.1:8081/docs>

The health endpoint returns HTTP 200 with `{"status":"healthy"}`.
It checks API liveness, not database connectivity. To inspect the response,
logs, or API runtime user:

```bash
curl -i http://127.0.0.1:8081/health
docker compose logs --tail=80 supplier-db supplier-service
docker compose exec supplier-service id
```

The API runs as UID 10001 (`supplier`).

### Networking and storage

The API joins the shared application network and the private supplier
network. The database joins only the private supplier network and has no
published host port. A `5432/tcp` entry in `docker compose ps` is not a host
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
The API initializes its database engine but does not yet authenticate through
User Service or gate readiness on the installed migration revision.

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

Browsing requires authentication; supplier mutations and administrative reads
require a verified `admin` role. Forward opaque bearer tokens to User Service
`GET /users/me`; do not decode JWTs or query its database. Use bounded timeouts
and no authentication caching initially. Administrator mode changes only the
frontend controls: the account role and session remain unchanged, and the
backend checks the verified role on each request. Never trust a mode/role header.

Return `401` for missing/invalid sessions, `403` for insufficient permissions,
`404` for unavailable records, `409` for stale active versions or duplicates,
`422` for invalid input, and `503` for unavailable database/authentication
dependencies. An authentication outage does not establish that the user has
logged out. The exact `/users/me` response remains deferred pending verification
against PR #6 before implementing the authentication integration.

POST returns `201 Created`; PATCH returns `200 OK`. Both return the complete
saved supplier using the same representation as detail reads: all supplier
fields, including timestamps, derived offset and version, with named location
coordinates and category objects rather than linking-table rows. DELETE
returns `204 No Content` with no body.

The [read example](#read) shows the complete supplier response shape.
The mutation rules above define editable inputs, version checks, and deletion
behaviour; error response examples appear below.

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

## Initial Data Import

Import the [existing supplier CSV](../data/csv/supplier-seed-data.csv)
through a separate, repeatable command after database migrations.

The import should:

- Handle the source encoding and normalize text consistently.
- Map source category labels into the controlled category list.
- Split combined categories such as `Food/Coffee` into assignments.
- Supply a reviewed campus-area mapping because the CSV has no area field.
- Convert supplied times into time values and a closing-day offset.
- Treat ambiguous schedules explicitly rather than silently guessing.
- Convert absent image references to null.
- Use stable seed identities so repeated imports do not create duplicates.
- Avoid overwriting later edits or restoring soft-deleted suppliers.

The reviewed initial mapping uses trimmed supplier names and normalized
buildings to locate permanent seed identities. Unmatched or ambiguous rows
require explicit review; do not infer identity from coordinates or row order.
Any invalid row rejects the entire batch before writes; database failures roll
back the entire import. Existing seed identities, including deleted records,
are skipped without overwriting later edits.

All seed schedules apply every day in Asia/Singapore. The five reviewed
0000hrs–2359hrs records (Printer @ Com 2, InstaChef, Cafe+ Robot Cafe, Octobox,
and Cheers Unmanned Convenience Store) represent 24 hours and are imported as
00:00–00:00 with offset 1. This is a per-record correction, not a general
23:59 conversion. Supersnacks retains 11:00–02:00 with offset 1.

Do not run a destructive reseed whenever an API instance starts.

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
