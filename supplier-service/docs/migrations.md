# Supplier schema operations

Revision `0001` creates the schema; `0002` inserts Food, Coffee, Shopping and
Printing with permanent UUIDs. Category IDs are literals in the revision and
must not be regenerated. Downgrading `0002` removes only those IDs and fails
if assignments still reference them. Downgrading `0001` removes application
tables and their data, but preserves PostGIS.

## Roles and Compose setup

Use a dedicated supplier database. The administrator installs PostGIS and
creates two roles: `supplier_migrator` owns application schema objects;
`supplier_runtime` can read categories and revision state, and read/write
supplier and assignment rows. Runtime cannot change categories or schema.
The API Compose service uses the runtime role. Migration startup gating and
readiness are a subsequent reference-07 change; apply migrations manually
before starting the API for now.

Set `SUPPLIER_MIGRATION_PASSWORD` and `SUPPLIER_RUNTIME_PASSWORD` in the root
`.env`, alongside the existing administrator settings. Export these values
into your shell too for the commands below; Compose's `.env` substitution
does not export shell variables. Use URL-safe local passwords; percent-encode
passwords if constructing a URL containing reserved characters.

From the repository root, start and bootstrap the database:

```bash
docker compose up -d --build supplier-db
# Run after supplier-db is healthy.
docker compose exec -T \
  -e SUPPLIER_MIGRATION_PASSWORD -e SUPPLIER_RUNTIME_PASSWORD \
  supplier-db sh -c 'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"' \
  < supplier-service/database/bootstrap.sql

docker compose build supplier-service
docker compose run --rm --no-deps \
  -e DATABASE_URL="postgresql+psycopg://supplier_migrator:${SUPPLIER_MIGRATION_PASSWORD}@supplier-db:5432/${SUPPLIER_POSTGRES_DB}" \
  supplier-service python -m alembic upgrade head

docker compose exec -T -e PGPASSWORD="$SUPPLIER_MIGRATION_PASSWORD" \
  supplier-db sh -c 'psql -h 127.0.0.1 -U supplier_migrator -d "$POSTGRES_DB"' \
  < supplier-service/database/runtime-grants.sql

docker compose up -d supplier-service
```

Bootstrap and grants are repeatable. Grants are explicit: newly introduced
tables require a permissions review, rather than automatically receiving
runtime writes. Reapply grants after recreating tables. Neither script changes
ownership of existing objects: if a previous development schema was created
as administrator, transfer its three application tables and `alembic_version`
to `supplier_migrator` as administrator before using that migration role.
Do not transfer ownership of PostGIS extension objects.

## Local commands

From `supplier-service/`, set `DATABASE_URL` to the migration role's connection
URL and set `USER_SERVICE_URL=http://localhost:8000` (required by shared settings).

```bash
.venv/bin/python -m alembic upgrade head
.venv/bin/python -m alembic current
.venv/bin/python -m alembic check
.venv/bin/python -m alembic upgrade head --sql > /tmp/supplier-schema.sql
```

Offline mode emits SQL and does not connect. Review generated revisions;
autogeneration does not prove check-expression equivalence. PostGIS's
`spatial_ref_sys` is excluded from application comparisons. The installed
base PostGIS extension's other public metadata relations are views, not
application tables. If adding other extensions, review their owned objects
before changing the comparison filter.

## Disposable integration database

Build and start from the repository root:

```bash
docker build -t foc-supplier-postgis-test supplier-service/database
docker run -d --rm --name foc-supplier-db-test \
  -e POSTGRES_USER=supplier_test -e POSTGRES_PASSWORD=supplier_test \
  -e POSTGRES_DB=foc_supplier_test -p 127.0.0.1:5433:5432 \
  foc-supplier-postgis-test
docker exec foc-supplier-db-test pg_isready -U supplier_test -d foc_supplier_test
```

After readiness, from `supplier-service/`:

```bash
export TEST_DATABASE_URL='postgresql+psycopg://supplier_test:supplier_test@127.0.0.1:5433/foc_supplier_test'
export TEST_ADMIN_DATABASE_URL="$TEST_DATABASE_URL"
.venv/bin/python -m pytest tests -q
```

The database must end in `_test` and differ from `DATABASE_URL`. Fixtures apply
migrations, never `create_all()`. Row tests roll back; the concurrency test
cleans up its uniquely named record. The admin URL enables a lifecycle test
that creates a new randomly named database, checks both downgrades and
re-upgrades, and removes only that new database. The administrator needs
CREATEDB and extension-install privileges. Omit the admin URL to skip this test.

To validate least privilege, bootstrap a fresh test database with the same SQL
scripts, migrate with `supplier_migrator`, and apply `runtime-grants.sql`.
Set `TEST_DATABASE_URL` to that migration login and
`TEST_RUNTIME_DATABASE_URL` to the same database using `supplier_runtime`.
The runtime permissions test is skipped unless the latter is supplied.
Keep `TEST_ADMIN_DATABASE_URL` as an administrator connection on that test
server to include lifecycle checks. All three variables are needed for full
integration coverage, including permissions and downgrades.

Stop the disposable container when finished:

```bash
docker stop foc-supplier-db-test
```

Its data is discarded. Never run destructive downgrade experiments against
a shared or development database.
