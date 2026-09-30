<!-- AI Assistance Disclosure:
Tool: Codex (model: GPT-6), date: 2026-09-28 to 2026-09-29
Scope: Refactoring and documentation improvements — write database setup, role, migration, and isolated verification instructions. Refactoring and documentation improvements; Debugging assistance — expand deployment/recovery instructions, explain isolated test setup, and correct disposable probe port selection (2026-09-29).
Author review: Keith confirmed review of all affected changes.
Details: ../ai/usage-log.md; ai-20260929-001; ai-20260929-004
-->

# Supplier schema operations

The API and `supplier-migrate` use the shared image `foc-supplier-service:local`,
built from `supplier-service/`. The image contains `alembic.ini` and `migrations/`
and runs as `supplier` (UID 10001). The migration job runs
`python -m alembic upgrade head` as database role `supplier_migrator`, joins only
`supplier-private`, publishes no ports, and has no HTTP health check or automatic
restart. Its required `USER_SERVICE_URL` comes from Compose; shared application
settings validate that URL even though migrations do not contact User Service.

Compose waits for `supplier-db` to be healthy and `supplier-migrate` to complete
successfully before starting a newly created API container. The API uses
`supplier_runtime`, retains its two networks and `127.0.0.1:8081` binding, and
has a `/ready` image health check with a three-second HTTP timeout and a
five-second Docker timeout.

| Probe | Success | Failure meaning |
| --- | --- | --- |
| `/health` | HTTP 200, `{"status":"healthy"}` | Application liveness only; no database access |
| `/ready` | HTTP 200, `{"status":"ready"}` | HTTP 503, `{"status":"not_ready"}` when connectivity, revision access, configuration, or exact head matching fails |

Readiness runs `SELECT 1`, reads installed heads with Alembic, and compares them
with the nonempty packaged heads. It releases connections and emits only a
generic failure diagnostic. Neither application startup nor readiness applies
migrations or creates tables. Probes do not require authentication.

## Fresh installation

Run these commands from the repository root with Docker running. Use the same
Compose project name throughout a deployment so it keeps the same named volume.
Execute steps in order and stop if a command fails.

1. If `.env` does not exist, copy `.env.example` to `.env`. Set these variables:

   ```dotenv
   POSTGRES_USER=foc
   POSTGRES_PASSWORD=REPLACE_WITH_USER_DB_PASSWORD
   SUPPLIER_POSTGRES_DB=supplier_db
   SUPPLIER_POSTGRES_USER=supplier_admin
   SUPPLIER_POSTGRES_PASSWORD=REPLACE_WITH_ADMIN_PASSWORD
   SUPPLIER_MIGRATION_PASSWORD=REPLACE_WITH_MIGRATION_PASSWORD
   SUPPLIER_RUNTIME_PASSWORD=REPLACE_WITH_RUNTIME_PASSWORD
   AUTH_TIMEOUT_SECONDS=3
   LOG_LEVEL=INFO
   ```

   The User database variables are needed to interpolate the complete Compose
   file even when starting only Supplier services. Use separate passwords;
   `openssl rand -hex 24` generates a URL-safe value. Migration and runtime
   passwords are interpolated into connection URLs, so use URL-safe values or
   correctly percent-encode URL components. Keep real credentials in the ignored
   `.env`, never in committed files or copied diagnostic output. The bootstrap
   administrator account is not used by the API.

   Compose loads `.env` for substitution; it does not export shell variables.
   In a shell with your trusted, shell-compatible `.env`, export the values for
   the bootstrap/grant commands too:

   ```bash
   set -a
   source .env
   set +a
   docker compose config --quiet
   ```

   Exported variables take precedence over `.env`; reload them after edits.
   Container `DATABASE_URL` and `USER_SERVICE_URL` are supplied explicitly by
   Compose. Standalone local-run examples of those variables in `.env` do not
   override the container settings. Avoid printing resolved Compose configuration
   because it includes connection credentials; `config --quiet` validates it.

2. Start the database and wait for its health check:

   ```bash
   docker compose up -d --build --wait supplier-db
   ```

3. As administrator, install PostGIS and provision the separate roles:

   ```bash
   docker compose exec -T \
     -e SUPPLIER_MIGRATION_PASSWORD -e SUPPLIER_RUNTIME_PASSWORD \
     supplier-db sh -c 'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"' \
     < supplier-service/database/bootstrap.sql
   ```

4. Build the shared application image, inspect its packaged revisions, and
   explicitly run migrations using the configured migration service:

   ```bash
   docker compose build supplier-service
   docker compose run --rm --no-deps supplier-migrate python -m alembic heads
   docker compose run --rm supplier-migrate
   docker compose run --rm supplier-migrate python -m alembic current
   ```

   `heads` inspects the image; `current` inspects the database. Both currently
   report `0002 (head)`. `run --rm` uses the job's image, network, settings, and
   role, waits for its database dependency, and removes its one-off container.
   A nonzero migration exit must halt deployment.

5. As migrator, apply the explicit runtime grants:

   ```bash
   docker compose exec -T -e PGPASSWORD="$SUPPLIER_MIGRATION_PASSWORD" \
     supplier-db sh -c 'psql -v ON_ERROR_STOP=1 -h 127.0.0.1 -U supplier_migrator -d "$POSTGRES_DB"' \
     < supplier-service/database/runtime-grants.sql
   ```

   A successfully migrated database is not sufficient: `supplier_runtime`
   needs `SELECT` on `alembic_version` for readiness. The script also grants
   category reads and supplier/assignment data access. It grants no schema
   mutation or revision-state writes. Without these grants, `/ready` returns
   503 even if `/health` returns 200 and the migration job succeeded.

6. Start the API and wait for readiness:

   ```bash
   docker compose up -d --wait --wait-timeout 90 supplier-service
   docker compose ps -a supplier-db supplier-migrate supplier-service
   curl --fail --max-time 5 http://127.0.0.1:8081/ready
   curl --fail --max-time 5 http://127.0.0.1:8081/health
   ```

   Compose also creates/runs its regular migration-job container as a dependency;
   upgrading an already-current database is a no-op. Expect the job to exit 0,
   the API to become healthy, and the two bodies shown in the probe table.
   No User Service or frontend container is needed for these checks.

Bootstrap and grants are repeatable. New tables require a permissions review,
and grants must be reapplied after objects are recreated. Neither script
transfers ownership of existing objects. If application tables were previously
created as administrator, explicitly arrange ownership of `supplier`, `category`,
`supplier_category`, and `alembic_version` for `supplier_migrator` before deployment.
Do not transfer ownership of PostGIS extension objects. Initial PostgreSQL
credentials only initialize an empty volume; changing `.env` does not update
existing database account passwords.

## Deploying a new image with the existing volume

Compose startup ordering is not a migration scheduler. A completed job from an
older image does not prove that a new image has been migrated. Dependencies also
do not stop an already-running API when the database or migration job fails.
Docker marks an unhealthy API but does not automatically stop it or migrate it.

Use this explicit maintenance-window sequence from the repository root. Keep
the existing project name, database name, credentials, and volume. Review the
new migration operations and back up persistent data before deployment. This
sequence intentionally stops the API; it is not a zero-downtime rollout.

```bash
docker compose config --quiet
docker compose build supplier-service
docker compose up -d --wait supplier-db
docker compose stop supplier-service

# Always recreate and run the job from the newly built shared image.
# This command waits and propagates the migration exit code.
docker compose up --no-deps --force-recreate --abort-on-container-exit \
  --exit-code-from supplier-migrate supplier-migrate
```

Continue only after exit 0. `--no-deps` is appropriate here because the database
has already passed `up --wait`; it prevents the attached command from managing
other services. Unlike `run --rm`, this leaves the job container available for
status/log inspection. Review grants for new objects, and reapply the existing
script when applicable:

```bash
docker compose exec -T -e PGPASSWORD="$SUPPLIER_MIGRATION_PASSWORD" \
  supplier-db sh -c 'psql -v ON_ERROR_STOP=1 -h 127.0.0.1 -U supplier_migrator -d "$POSTGRES_DB"' \
  < supplier-service/database/runtime-grants.sql

docker compose run --rm --no-deps supplier-migrate python -m alembic current
docker compose up -d --no-deps --force-recreate --wait --wait-timeout 90 supplier-service
curl --fail --max-time 5 http://127.0.0.1:8081/ready
```

The final `--no-deps` deliberately relies on the explicit successful job above;
it does not independently enforce the dependency. Do not run that step after a
failed migration. Recreating the API makes it use the new image while retaining
database data. Do not use `down -v`, reset the schema, or reseed existing data as
a deployment step.

## Inspection and recovery

From the repository root:

```bash
docker compose ps -a supplier-db supplier-migrate supplier-service
docker compose logs --tail=80 supplier-migrate
docker compose logs --tail=80 supplier-service
docker compose run --rm --no-deps supplier-migrate python -m alembic heads
docker compose run --rm --no-deps supplier-migrate python -m alembic current
docker inspect --format '{{json .State.Health}}' "$(docker compose ps -q supplier-service)"
curl -i --max-time 5 http://127.0.0.1:8081/ready
curl -i --max-time 5 http://127.0.0.1:8081/health
```

`heads` is packaged state, `current` is installed state, and `ps -a` includes the
exited migration job. A removed one-off job has no retained logs; use the regular
job invocation above when you need its status and logs afterward. Readiness
responses/logs are generic; migration-tool diagnostics can include operational
details, so review them before sharing.

- Database unavailable: restore database service/connectivity, then retry
  `/ready`. Connections are checked on each request and readiness can recover
  without restarting the API. `/health` remains a liveness-only check.
- Older schema: run the new image's migration job successfully and ensure grants
  are correct. Readiness recovers once installed and packaged heads match.
  Unknown or additional heads require diagnosis of image/database history;
  do not use `alembic stamp` merely to make readiness pass.
- Missing grants: apply the reviewed runtime grants, including revision-state
  reads. Recheck readiness without changing the API's database role.
- Migration failure: inspect the job logs, correct the migration/configuration
  cause, rebuild if needed, and explicitly rerun the migration job. Then apply
  grants and recreate/start the API. Keep the volume; do not delete data as a fix.

## Local Alembic commands and revision behavior

From `supplier-service/`, export `DATABASE_URL` for the migration role and
`USER_SERVICE_URL=http://localhost:8000` (required by shared settings):

```bash
.venv/bin/python -m alembic upgrade head
.venv/bin/python -m alembic heads
.venv/bin/python -m alembic current
.venv/bin/python -m alembic check
.venv/bin/python -m alembic upgrade head --sql > /tmp/supplier-schema.sql
```

Revision `0001` creates the schema; `0002` inserts Food, Coffee, Shopping and
Printing with permanent UUIDs. Those IDs must not be regenerated. Downgrading
`0002` removes only those categories and fails while assignments reference them.
Downgrading `0001` removes application tables and data while preserving PostGIS.
Downgrade experiments below belong only on disposable data.

Offline SQL generation does not connect. Review generated revisions;
autogeneration does not prove check-expression equivalence. PostGIS's
`spatial_ref_sys` is excluded from application comparisons; its other public
metadata relations are views. Review extension-owned objects before adding
other extensions to schema comparison.

## Isolated deployment and recovery rehearsal

Use a new terminal at the repository root. This setup uses the final Compose
file plus a temporary override: a unique project/volume/image, random localhost
ports, and disposable credentials. The test database additionally joins the
project default network so Docker can publish its localhost port for host-run
integration tests; production keeps its internal-only database network. Only
Supplier services are started. It
requires Docker Compose with `!override` support (verified with v5.5.1).

```bash
CHECK_ROOT="$PWD"
CHECK_DIR="$(mktemp -d "${TMPDIR:-/tmp}/foc-supplier-check.XXXXXX")"
CHECK_PROJECT="foc-supplier-check-$(date +%s)-$$"
cat > "$CHECK_DIR/test.env" <<'ENV'
POSTGRES_USER=unused_test
POSTGRES_PASSWORD=unused_test
SUPPLIER_POSTGRES_DB=supplier_deploy_test
SUPPLIER_POSTGRES_USER=supplier_test_admin
SUPPLIER_POSTGRES_PASSWORD=disposable_admin
SUPPLIER_MIGRATION_PASSWORD=disposable_migration
SUPPLIER_RUNTIME_PASSWORD=disposable_runtime
AUTH_TIMEOUT_SECONDS=3
LOG_LEVEL=INFO
ENV
set -a
source "$CHECK_DIR/test.env"
set +a
cat > "$CHECK_DIR/override.yaml" <<YAML
services:
  supplier-service:
    image: ${CHECK_PROJECT}-app:local
    ports: !override
      - "127.0.0.1::8080"
  supplier-migrate:
    image: ${CHECK_PROJECT}-app:local
  supplier-db:
    networks:
      - supplier-private
      - default
    ports:
      - "127.0.0.1::5432"
YAML
dc() {
  docker compose --env-file "$CHECK_DIR/test.env" -p "$CHECK_PROJECT" \
    -f "$CHECK_ROOT/compose.yaml" -f "$CHECK_DIR/override.yaml" "$@"
}
dc config --quiet
```

The disposable credentials are already loaded: do not copy or source the root
`.env` for this rehearsal. Run fresh-install **steps 2–4** above with `dc`
replacing every `docker compose`. Then demonstrate missing revision-read grants
by running `dc up -d supplier-service` without `--wait`, before step 5. Once
Uvicorn is listening, obtain its random port and inspect the probes:

```bash
CHECK_API="http://$(dc port supplier-service 8080)"
curl -i --max-time 5 "$CHECK_API/ready"   # 503, {"status":"not_ready"}
curl -i --max-time 5 "$CHECK_API/health"  # 200, {"status":"healthy"}
```

Apply the grant step with `dc`, then run
`dc up -d --wait --wait-timeout 90 supplier-service`. Readiness becomes 200.
Recalculate `CHECK_API` after any API recreation because its random port can change.

### Database outage and repair

Keep the API running and stop only this project's database:

```bash
dc stop supplier-db
curl -i --max-time 5 "$CHECK_API/ready"   # 503, safe generic body
curl -i --max-time 5 "$CHECK_API/health"  # 200
dc up -d --wait supplier-db
curl -i --max-time 5 "$CHECK_API/ready"   # 200 again
```

Container health may take the next health-check interval to catch up with the
HTTP result. No API restart or volume removal is needed.

### Older revision and upgrade with surviving data

On this disposable database only, with no seeded-category assignments, prepare
revision `0001` and insert a representative supplier:

```bash
dc run --rm supplier-migrate python -m alembic downgrade 0001
dc exec -T supplier-db sh -c 'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"' <<'SQL'
INSERT INTO supplier (id, name, area, location, created_at, updated_at, version)
VALUES ('00000000-0000-0000-0000-000000000123', 'Persistent deployment probe',
        'Test area', ST_GeogFromText('SRID=4326;POINT(103.77 1.30)'), now(), now(), 1);
SQL
curl -i --max-time 5 "$CHECK_API/ready"   # 503: current image expects 0002
curl -i --max-time 5 "$CHECK_API/health"  # 200
CHECK_VOLUME="$(docker inspect --format '{{range .Mounts}}{{if eq .Destination "/var/lib/postgresql/data"}}{{.Name}}{{end}}{{end}}' "$(dc ps -q supplier-db)")"
```

Follow the **existing-volume deployment** sequence above with `dc`, including
rebuilding the shared image, explicitly recreating the job, reapplying grants,
and recreating the API. Replace that sequence's final fixed-port
`curl --fail --max-time 5 http://127.0.0.1:8081/ready` with the following commands
immediately after API recreation. Recalculate the disposable project's address
before probing it; port 8081 may belong to an unrelated development API.

```bash
CHECK_API="http://$(dc port supplier-service 8080)"
curl --fail --max-time 5 "$CHECK_API/ready"
```

Then verify the installed revision, unchanged volume, and saved row:

```bash
dc run --rm --no-deps supplier-migrate python -m alembic current
test "$CHECK_VOLUME" = "$(docker inspect --format '{{range .Mounts}}{{if eq .Destination "/var/lib/postgresql/data"}}{{.Name}}{{end}}{{end}}' "$(dc ps -q supplier-db)")"
dc exec -T supplier-db sh -c 'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"' <<'SQL'
SELECT id, name, version FROM supplier
WHERE id = '00000000-0000-0000-0000-000000000123';
SQL
```

Expect `0002`, the same volume name, and `Persistent deployment probe` at version
1. This stages a real older database revision with the current source image;
it does not test an archived historical image or an arbitrary future migration.

### Failed migration blocks a new API, then recovers

Create an extra failing revision only in a temporary copy. Production revision
files remain untouched. This fixture assumes the current packaged head `0002`;
update its parent if the packaged migration chain changes.

```bash
cp -R supplier-service/migrations "$CHECK_DIR/failing-migrations"
cat > "$CHECK_DIR/failing-migrations/versions/failure_probe.py" <<'PY'
revision = 'disposable_failure_probe'
down_revision = '0002'
branch_labels = None
depends_on = None

def upgrade():
    raise RuntimeError('Intentional disposable migration failure')

def downgrade():
    pass
PY
cat > "$CHECK_DIR/failure.yaml" <<YAML
services:
  supplier-migrate:
    volumes:
      - "$CHECK_DIR/failing-migrations:/app/migrations:ro"
YAML
# Remove only these disposable containers, keeping the database and its volume.
dc rm -s -f supplier-service supplier-migrate
# Expected nonzero exit; do not use --no-deps here: this tests startup gating.
dc -f "$CHECK_DIR/failure.yaml" up -d supplier-service
dc ps -a supplier-service supplier-migrate
dc logs --tail=20 supplier-migrate
```

Expect migration exit 1 and the API to remain `Created`, never started. Remove
the failure by invoking the normal configuration without `failure.yaml`:

```bash
dc up --no-deps --force-recreate --abort-on-container-exit \
  --exit-code-from supplier-migrate supplier-migrate
# Continue only after exit 0.
dc exec -T -e PGPASSWORD="$SUPPLIER_MIGRATION_PASSWORD" \
  supplier-db sh -c 'psql -v ON_ERROR_STOP=1 -h 127.0.0.1 -U supplier_migrator -d "$POSTGRES_DB"' \
  < supplier-service/database/runtime-grants.sql
dc up -d --force-recreate --wait --wait-timeout 90 supplier-service
CHECK_API="http://$(dc port supplier-service 8080)"
curl --fail --max-time 5 "$CHECK_API/ready"
```

Repeat the saved-row and volume checks above. The failure and recovery must
preserve both; no database reset, stamp, production revision edit, or reseeding
is required.

## Unit, API, and database integration checks

From `supplier-service/`, unit/API checks need no external services:

```bash
.venv/bin/python -m pytest tests/unit tests/api -q
```

For full database coverage, use the isolated Compose project above after it is
migrated and granted. Remove only the demonstration row before running the
existing tests, which assume their own application fixtures. From the root in
the same rehearsal terminal:

```bash
dc exec -T supplier-db sh -c 'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"' <<'SQL'
DELETE FROM supplier WHERE id = '00000000-0000-0000-0000-000000000123';
SQL
CHECK_DB_ADDRESS="$(dc port supplier-db 5432)"
export TEST_DATABASE_URL="postgresql+psycopg://supplier_migrator:${SUPPLIER_MIGRATION_PASSWORD}@${CHECK_DB_ADDRESS}/${SUPPLIER_POSTGRES_DB}"
export TEST_RUNTIME_DATABASE_URL="postgresql+psycopg://supplier_runtime:${SUPPLIER_RUNTIME_PASSWORD}@${CHECK_DB_ADDRESS}/${SUPPLIER_POSTGRES_DB}"
export TEST_ADMIN_DATABASE_URL="postgresql+psycopg://${SUPPLIER_POSTGRES_USER}:${SUPPLIER_POSTGRES_PASSWORD}@${CHECK_DB_ADDRESS}/${SUPPLIER_POSTGRES_DB}"
# In this disposable-test terminal only; avoid a conflicting local application URL.
unset DATABASE_URL
(cd supplier-service && .venv/bin/python -m pytest tests/integration -q)
# Or run everything together:
(cd supplier-service && .venv/bin/python -m pytest tests -q)
```

Install `supplier-service/requirements-dev.txt` into the service virtual
environment first if needed. Test URLs must use `postgresql+psycopg`, target a
separate database ending in `_test`, and differ from the application database
name when `DATABASE_URL` is set. Fixtures never fall back to application settings.
They apply Alembic migrations and roll back row tests; concurrency checks clean
up their committed rows. Runtime tests require the provisioned runtime role on
the same test database. Without `TEST_RUNTIME_DATABASE_URL`, that test is skipped.
The lifecycle test creates and removes its own uniquely named database; its admin
URL needs database-creation and extension-install privileges. Without
`TEST_ADMIN_DATABASE_URL`, that test is skipped. Supply all three URLs for full
coverage, using only disposable data.

### Observed verification

Verified on 2026-09-29 using Docker Desktop (Apple Silicon), Compose v5.5.1,
and isolated project `foc-supplier-docs-19148` with disposable credentials/data:

| Check | Observed result |
| --- | --- |
| Compose configuration and image builds | Passed; packaged and installed head `0002` |
| Fresh bootstrap, migration, and grants | Before grants: readiness 503 and liveness 200; after grants: readiness 200 and API healthy |
| Database stopped, then restarted | Safe readiness 503 and liveness 200 during outage; readiness returned to 200 without API restart |
| Revision `0001` with a saved supplier, upgraded to `0002` | Outdated schema gave readiness 503/liveness 200; explicit job and API recreation restored health; volume name and supplier name/version survived |
| Temporary failing revision | Migration exited 1; newly created API remained `Created`, never started |
| Failure removed and migration rerun | Job exited 0, API became healthy, and the saved supplier survived without deleting the volume |
| Existing unit/API/integration suite | **74 passed**, no skips: 40 unit/API and 34 database checks, including runtime permissions and lifecycle coverage; one Starlette/AnyIO deprecation warning |
| Cleanup | Only the disposable project's containers, networks, and volume were removed |

An initial integration attempt used only the internal database network: Docker
reported no usable published host port, so database checks could not connect
(40 passed, 33 setup errors, one failure). Adding the default network **only in
the temporary test override** enabled the localhost mapping; the full rerun
passed as recorded above. The instructions include that corrected test setup.

Not verified: the full multi-service stack, native AMD64 execution, deployment
against development/production data, an archived older application image, or
future migration compatibility. The older-state check used the existing `0001`
revision with the current source image. Production revisions were not modified;
the intentional failure existed only in a disposable mounted copy.

### Cleanup

After all rehearsal/tests, from the same terminal:

```bash
dc down -v --remove-orphans
```

This removes only the uniquely named rehearsal project's containers, networks,
and volumes. Keep `CHECK_DIR` while inspecting its temporary fixtures, or remove
that specific directory afterward. Never run an unqualified `docker compose
down -v` against the development project as test cleanup. To stop development
containers while preserving data, use
`docker compose stop supplier-service supplier-db`. Built test images may remain
in the local image cache.
