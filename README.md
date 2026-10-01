# CS3219 — Software Design and Architecture (AY2627 Sem 1)

## Friend on Campus (FoC)

**Friend on Campus (FoC)** is a peer-to-peer campus errand platform where
students can request items to be collected from stores or facilities on
campus, and other students can fulfil (and deliver) those requests. The
platform runs on a closed credit economy — credits cannot be bought,
withdrawn, or exchanged for money, and only circulate within the platform.

---

## Team Members

| Name        | Role             |
| ----------- | ---------------- |
| Swee Kah Ho | Frontend Service |
| Your Name   | Your ownership   |
| Your Name   | Your ownership   |
| Your Name   | Your ownership   |
| Your Name   | Your ownership   |

---

## Repository Structure

This repository follows a **one-service-per-folder** structure: each
microservice (`user-service/`, `supplier-service/`, `order-service/`,
`credit-service/`) lives in its own top-level folder.

```text
.
├── user-service/
├── supplier-service/
├── order-service/
├── credit-service/
├── <n2h-service>/
└── README.md
```

- Any **nice-to-have (N2H)** feature that warrants its own service should
  be added as an **additional folder** at the same level, following the
  same per-service structure.
- Files for agentic coding tools (e.g. agent configs, prompts, skills)
  may be added as needed, but must still **respect the
  one-service-per-folder skeleton** for core implementation.

---

## Running Locally with Docker Compose

Services can be run via the root [`compose.yaml`](./compose.yaml).

Start the services:

```bash
docker compose up
```

Rebuild after making changes:

```bash
docker compose up --build
```

Stop and remove the containers:

```bash
docker compose down
```

---

## AI Use Summary (FoC)

Codex (GPT-6) assisted Supplier Service work. The
[Supplier Service summary](supplier-service/README.md#ai-use-summary-supplier-service)
and [usage log](supplier-service/ai/usage-log.md) record the affected files and evidence.

- [Database and migration work](supplier-service/ai/usage-log.md#ai-20260929-001):
  Requirements work, Learning support, Boilerplate generation, Writing implementation
  code, Debugging assistance, and Refactoring and documentation improvements covered
  migrations, role access, image configuration, integration checks, and related root
  configuration. The prior record reports 54 passing disposable-PostGIS tests,
  no Alembic drift, a successful image build, and confirmed author review. It also
  records unavailable original timestamps; the service summary notes redacted excerpts.
- [Readiness work](supplier-service/ai/usage-log.md#ai-20260929-002): Writing
  implementation code covered `/ready` and isolated readiness/liveness tests using
  the existing engine and Alembic setup. Changes were retained; 40 API/unit tests
  and `git diff --check` passed, with one dependency deprecation warning.
  PostgreSQL integration was not run for this change. Keith confirmed review of
  all affected readiness changes; no human test rerun is claimed.
  The exact prompt and final response are recorded; original timestamps are unavailable.

- [Compose migration gating](supplier-service/ai/usage-log.md#ai-20260929-003):
  Codex (GPT-6) provided Boilerplate generation for `compose.yaml` and the Supplier
  Dockerfile, configuring a shared image, migration job, startup dependencies,
  and readiness health check. Changes were retained and reviewed by Keith.
  Agent checks verified image build, packaged revisions, explicit migration,
  successful startup, disposable failure blocking startup, recovery, Compose
  validation, and `git diff --check`. The full stack and development database
  were not tested; no human test rerun is claimed. Exact prompt and response
  excerpts are recorded; original timestamps are unavailable.

- [Deployment documentation and port correction](supplier-service/ai/usage-log.md#ai-20260929-004):
  Codex (GPT-6) provided Refactoring and documentation improvements and Debugging
  assistance for the Supplier README and operations guide. Keith reviewed the
  retained work. Disposable deployment/recovery checks passed; after a test-only
  network correction, 74 tests passed with no skips and one dependency warning.
  Shell syntax, links, and `git diff --check` passed. The later wording correction
  was checked without rerunning Docker tests. Full-stack, AMD64, archived-image,
  and development/production deployments were not verified. Exact prompts and
  response excerpts are recorded; original timestamps are unavailable. No human
  test rerun is claimed.

- [Creation validation](supplier-service/ai/usage-log.md#ai-20260930-001):
  Codex (GPT-6) provided Writing implementation code for Pydantic client/result
  types, aggregate creation validation, the shared parsing-error adapter, and
  focused tests. The work remains in the working tree. Agent checks passed 112
  creation tests and 97 domain tests, with one dependency warning per run and
  no unavailable requested checks after correcting an initial test-file path.
  Keith confirmed review of all four affected files; no human rerun is claimed.
  The exact prompt and final
  response are recorded; original timestamps are unavailable. No redactions or
  header exceptions apply.

- [PATCH validation](supplier-service/ai/usage-log.md#ai-20260930-002):
  Codex (GPT-6) provided Writing implementation code and Refactoring and
  documentation improvements for shared schemas, pure merged-value validation,
  update-service usage guidance, and focused tests. The work was retained and
  all three affected files were reviewed by Keith. Agent checks passed 90 PATCH
  tests and 209 creation/domain tests, with one dependency warning per run and
  no unavailable requested checks. No human test rerun is claimed. The exact
  prompt and final response are recorded; original timestamps are unavailable.
  No redactions or header exceptions apply.

- [HTTP validation integration](supplier-service/ai/usage-log.md#ai-20260930-003):
  Codex (GPT-6) provided Writing implementation code and Refactoring and
  documentation improvements for shared 422 handlers, safe request-error
  conversion, test-only routes, and future API/import guidance. All four affected
  files were retained and reviewed by Keith. Agent checks passed 357 unit/API
  tests, including health and readiness, with one existing dependency warning
  and no unavailable requested checks. Coverage and final syntax/documentation
  checks were reviewed; no human test rerun is claimed. The exact prompt and
  final response are recorded; original timestamps are unavailable. No
  redactions or header exceptions apply.

- [Permanent seed mapping](supplier-service/ai/usage-log.md#ai-20260930-004):
  Codex (GPT-6) provided Requirements work for the reviewed JSON data, authored
  permanent labels and one-time UUIDv4 values, and provided Writing implementation
  code for mapping tests. All three files were retained and reviewed by Keith.
  Agent verification: 12 tests passed with one dependency warning and the source
  CSV SHA-256 remained unchanged. No human test rerun is claimed. The exact prompt
  and final response are recorded; original timestamps are unavailable.
  Header exceptions: `supplier-service/seed/manifest.json` and
  `supplier-service/seed/area_mapping.json` are strict JSON and cannot contain comments.
  See the [Supplier Service summary](supplier-service/README.md#ai-use-summary-supplier-service).

- [CSV source loading](supplier-service/ai/usage-log.md#ai-20260930-005):
  Codex (GPT-6) provided Writing implementation code, Refactoring and documentation
  improvements, and Boilerplate generation for the Supplier command-support package,
  loader, tests, and CP1252 fixture. Retained refinements count malformed duplicate
  rows and report syntax-error line numbers after blank lines correctly. Agent
  verification: 55 tests passed with one dependency warning, including stability
  of all 21 real associations after reordering. Keith confirmed review of all four
  affected files, including the final refinements. No human test rerun is claimed.
  The original exact prompt and response excerpts are recorded as one task;
  original timestamps are unavailable. Header exception:
  `supplier-service/tests/fixtures/seed_source.csv` is CP1252 CSV data that cannot
  safely contain attribution comments. See the
  [Supplier Service summary](supplier-service/README.md#ai-use-summary-supplier-service).

- [Shared seed scalar validation](supplier-service/ai/usage-log.md#ai-20260930-006):
  Codex (GPT-6) provided Writing implementation code and Refactoring and
  documentation improvements for shared supplier schemas, pure seed scalar
  validation, and 61 new tests. The changes were retained and all three files
  were reviewed by Keith. Agent verification: 473 unit/API tests passed with one
  dependency warning; `git diff --check` passed. No human test rerun is claimed.
  The exact prompt and final response are recorded; original timestamps are
  unavailable. No redactions or header exceptions apply to this entry. See the
  [Supplier Service summary](supplier-service/README.md#ai-use-summary-supplier-service).

- [Seed normalization](supplier-service/ai/usage-log.md#ai-20260930-007):
  Codex (GPT-6) provided Writing implementation code and Refactoring and
  documentation improvements for typed seed normalization and its tests. Retained
  behavior includes controlled category names, reviewed schedule corrections,
  exact image references, and whole-batch rejection. Keith reviewed both files.
  Agent verification: 163 focused tests passed with one dependency warning;
  real-data checks and `git diff --check` passed, and source CSV bytes were unchanged.
  No human test rerun is claimed. The exact prompt and final response are recorded;
  original timestamps are unavailable. No redactions or header exceptions apply.
  See the [Supplier Service summary](supplier-service/README.md#ai-use-summary-supplier-service).

- [Seed dry-run command](supplier-service/ai/usage-log.md#ai-20260930-008):
  Codex (GPT-6) provided Writing implementation code for the CLI and subprocess
  tests, and Refactoring and documentation improvements for usage guidance.
  All three affected files were retained and reviewed by Keith. Agent verification:
  the real CSV produced 21 suppliers, 26 assignments, five corrections, and no
  issues; 528 unit/API tests passed with one dependency warning. Checks covered
  inert import, absent database access, stable identities/counts, unchanged data,
  and final syntax/whitespace. No requested checks were unavailable; no human test
  rerun is claimed. The exact prompt and final response are recorded; original
  timestamps are unavailable. No redactions or header exceptions apply. See the
  [Supplier Service summary](supplier-service/README.md#ai-use-summary-supplier-service).

- [Database seed classification](supplier-service/ai/usage-log.md#ai-20260930-009):
  Codex (GPT-6) provided Boilerplate generation, Writing implementation code, and
  Refactoring and documentation improvements for repository/service packages,
  read-only classification, integration tests, and the confirmed identity policy.
  All six files were retained and reviewed by Keith. Agent verification: 545 tests
  passed, including 17 isolated migrated PostgreSQL/PostGIS tests, with one existing
  dependency warning. Classification preserved database values and pending caller
  state. The scoped whitespace check passed; the repository-wide check reported
  pre-existing usage-log whitespace. No human test rerun is claimed. The exact
  prompt and final response are recorded; original timestamps are unavailable.
  No redactions or header exceptions apply. See the
  [Supplier Service summary](supplier-service/README.md#ai-use-summary-supplier-service).

- [Atomic supplier import](supplier-service/ai/usage-log.md#ai-20260930-010):
  Codex (GPT-6) provided Writing implementation code and Refactoring and
  documentation improvements for service-owned transactions, repository insertion
  helpers, and rollback/concurrency tests. All three files were retained and
  reviewed by Keith. Agent verification: 558 tests passed, including 30 seed
  integration cases against isolated migrated PostgreSQL/PostGIS, with one
  existing dependency warning. Tests verified repeatability, preserved edits and
  deletion, assignment/pre-commit rollback, and explicitly synchronized importer
  and API races. Test databases and the container were removed; syntax and
  whitespace checks passed. No human test rerun is claimed. The exact prompt and
  final response are recorded; original timestamps are unavailable. No redactions
  or header exceptions apply. See the
  [Supplier Service summary](supplier-service/README.md#ai-use-summary-supplier-service).

- Recent Supplier seed command work: Codex (GPT-6) provided Writing
  implementation code, Refactoring and documentation improvements, and Debugging
  assistance for the CLI, parser snapshot, importer outcome reporting, and tests.
  Retained work and exact exchanges are consolidated as Prompts 1–3 for the
  [database-aware CLI](supplier-service/ai/usage-log.md#ai-20260930-011),
  [snapshot/passwordless fixes](supplier-service/ai/usage-log.md#ai-20260930-011),
  and [uncertain commits](supplier-service/ai/usage-log.md#ai-20260930-011).
  Agent verification passed 591, 596, and 599 tests respectively, each with one
  existing dependency warning. Tests included passwordless PostGIS and a real
  commit followed by simulated lost acknowledgement; test resources were removed.
  Keith confirmed review of all five affected files across these exchanges.
  No human test rerun is claimed.
  Exact prompts and final responses are recorded; original timestamps are
  unavailable. No redactions or header exceptions apply. See the
  [Supplier Service summary](supplier-service/README.md#ai-use-summary-supplier-service).

- [Explicit Supplier seed packaging](supplier-service/ai/usage-log.md#ai-20260930-012):
  Codex (GPT-6) provided Boilerplate generation for the service Dockerfile and
  root Compose tools service, and Refactoring and documentation improvements
  for the service README and seed mapping guide. All four changes were retained
  and reviewed by Keith. During this exchange, Compose validation, image builds,
  bootstrap, migrations, and grants passed on Linux/ARM64; Docker startup stalled
  before seed execution checks, and cleanup timed out. No successful container
  import or human test rerun is claimed for this entry. The exact prompt and
  final response are recorded; original timestamp unavailable, with no redactions
  or header exceptions. See the
  [Supplier Service summary](supplier-service/README.md#ai-use-summary-supplier-service).

- [Active Supplier detail reads](supplier-service/ai/usage-log.md#ai-20260930-013):
  Codex (GPT-6) provided Writing implementation code and Refactoring and
  documentation improvements for the repository, new read service, and PostGIS
  integration tests. All three files were retained and reviewed by Keith.
  Agent verification passed 612 read/seed integration and unit/API tests, with
  one existing dependency warning; syntax and scoped whitespace checks passed.
  The disposable database was removed. The full schema/runtime-role integration
  suite was not run; no human test rerun is claimed. The exact prompt and final
  response are recorded; original timestamp unavailable, with no redactions or
  header exceptions. See the
  [Supplier Service summary](supplier-service/README.md#ai-use-summary-supplier-service).

- [Active Supplier listing and pagination](supplier-service/ai/usage-log.md#ai-20260930-014):
  Codex (GPT-6) provided Writing implementation code and Refactoring and
  documentation improvements for the repository, service, and PostGIS tests.
  All three files were retained and reviewed by Keith. Agent checks passed
  639 read/seed integration and unit/API tests, with one existing dependency
  warning, plus syntax and scoped whitespace checks. Fresh-session tests verified
  bounded query growth and unchanged stored data. The disposable database was
  removed; the full schema/runtime-role integration suite was not run. No human
  test rerun is claimed. The exact prompt and final response are recorded;
  original timestamp unavailable, with no redactions or header exceptions. See the
  [Supplier Service summary](supplier-service/README.md#ai-use-summary-supplier-service).

- [Controlled Supplier category and area readers](supplier-service/ai/usage-log.md#ai-20260930-015):
  Codex (GPT-6) provided Writing implementation code and Refactoring and
  documentation improvements for the repository, service, and read integration
  tests. All three files were retained and reviewed by Keith. Agent checks passed
  653 read/seed integration and unit/API tests and a separate database-independent
  area test, with an existing dependency warning. Syntax and scoped whitespace
  checks passed; the disposable database was removed. Full schema/runtime-role
  integration coverage was not run; no human test rerun is claimed. The exact
  prompt and final response are recorded; original timestamp unavailable, with
  no redactions or header exceptions. See the
  [Supplier Service summary](supplier-service/README.md#ai-use-summary-supplier-service).

- [Supplier read response models](supplier-service/ai/usage-log.md#ai-20260930-016):
  Codex (GPT-6) provided Writing implementation code for response schemas and
  detached-value serialization tests. Both files were retained and reviewed by
  Keith. Agent checks passed 11 new tests and all 552 unit/API tests with one
  dependency warning; scoped whitespace checks passed. Database integration
  tests were not run; no human test rerun is claimed. The exact prompt and final
  response are recorded; original timestamp unavailable, with no redactions or
  header exceptions. See the
  [Supplier Service summary](supplier-service/README.md#ai-use-summary-supplier-service).

- [Unregistered Supplier GET adapters](supplier-service/ai/usage-log.md#ai-20260930-017):
  Codex (GPT-6) provided Writing implementation code for the supplier router and
  isolated HTTP tests. Retained handlers use existing services and response models
  and remain unregistered pending authentication. During this exchange, 37 read
  HTTP/serialization tests and all 578 unit/API tests passed with one dependency
  warning; scoped whitespace checks passed. Database integration tests were not
  run. Keith confirmed review of both affected files; no human test rerun is claimed. The exact
  prompt and final response are recorded; original timestamp unavailable, with
  no redactions or header exceptions. See the
  [Supplier Service summary](supplier-service/README.md#ai-use-summary-supplier-service).

- [Controlled reference-data GET adapters](supplier-service/ai/usage-log.md#ai-20260930-018):
  Codex (GPT-6) provided Writing implementation code for the reference-data router
  and isolated HTTP tests. Retained handlers preserve ordered choices and
  database-free areas; all four read adapters remain unregistered in production.
  Agent checks passed 43 read HTTP/serialization tests and all 584 unit/API tests,
  with one dependency warning. Combined read collection passed with 97 tests;
  scoped whitespace checks passed. Database integration tests were not run.
  Keith confirmed review of both files; no human test rerun is claimed. The exact prompt
  and final response are recorded; original timestamp unavailable, with no
  redactions or header exceptions. See the
  [Supplier Service summary](supplier-service/README.md#ai-use-summary-supplier-service).

- [Synchronous Supplier User Service client](supplier-service/ai/usage-log.md#ai-20260930-019):
  Codex (GPT-6) provided Writing implementation code for the client and mock
  tests, and Boilerplate generation for the client package and HTTPX dependency
  relocation. All five files were retained; Keith approved the original
  implementation. During that exchange, 71 focused tests and all 655 unit/API
  tests passed with one existing dependency warning; scoped whitespace checks
  passed. Live-service and database integration checks were not run; no human
  test rerun is claimed. The exact prompt and final response are recorded;
  original timestamp unavailable, with no redactions or header exceptions. See the
  [Supplier Service summary](supplier-service/README.md#ai-use-summary-supplier-service).

- [Supplier User Service client lifecycle](supplier-service/ai/usage-log.md#ai-20260930-020):
  Codex (GPT-6) provided Writing implementation code for the application factory
  and startup tests. Retained changes share one client per lifespan and clean up
  client/database resources on shutdown and startup failures. Agent checks passed
  10 startup tests and all 666 unit/API tests with one existing dependency warning;
  scoped whitespace checks passed. Live-service and database integration checks
  were not run. Keith subsequently confirmed review of both affected files; no
  human test rerun is claimed. The exact prompt and final response are recorded; original timestamp
  unavailable, with no redactions or header exceptions. See the
  [Supplier Service summary](supplier-service/README.md#ai-use-summary-supplier-service).

- [Supplier authentication and administrator dependencies](supplier-service/ai/usage-log.md#ai-20260930-021):
  Codex (GPT-6) provided Writing implementation code for authentication
  dependencies, the dedicated error handler, and isolated API tests. All three
  files were retained and reviewed by Keith for this implementation. Agent checks
  passed 47 combined authentication/validation-error tests and all 695 unit/API
  tests, including 29 new tests, with one existing dependency warning; scoped
  whitespace checks passed. An initial test-file path error was corrected.
  Live-service and database integration checks were not run; no human test rerun
  is claimed. The exact prompt and final response are recorded; original timestamp
  unavailable, with no redactions or header exceptions. See the
  [Supplier Service summary](supplier-service/README.md#ai-use-summary-supplier-service).

- [Public Supplier and reference-data reads](supplier-service/ai/usage-log.md#ai-20260930-022):
  Codex (GPT-6) provided Writing implementation code for router registration and
  read/probe regression tests, plus Refactoring and documentation improvements
  for router descriptions and verification guidance. All eight affected files
  were retained and reviewed by Keith, including the additional validation-test
  correction. Agent checks passed 121 focused tests and all 723 unit/API tests
  after correcting the stale route-exclusion assertion, with one dependency
  warning; syntax and scoped whitespace checks passed. No Compose services were
  running, so live login/logout checks were not performed; database integration
  tests were not run. No human test rerun is claimed. The exact prompt and final
  response are recorded; original timestamp unavailable, with no redactions or
  header exceptions. See the
  [Supplier Service summary](supplier-service/README.md#ai-use-summary-supplier-service).

- [Shared supplier seed/create insertion](supplier-service/ai/usage-log.md#ai-20261001-001):
  Codex (GPT-6) provided Writing implementation code for the repository helper
  and direct integration coverage, plus Refactoring and documentation improvements
  for the docstring. Retained work excludes category IDs from supplier inserts and
  preserves separate assignments and caller-owned transactions. Historical agent
  checks passed 62 seed integration tests, 723 unit/API tests, two focused SQL
  cases, and scoped whitespace checks, with one existing dependency warning.
  Subsequent test edits have unestablished authorship/timing and are not covered
  by those historical results. Keith confirmed review of both affected files; Keith also confirmed a test rerun, with commands and results unspecified. The exact prompt and
  final response are recorded; original timestamp unavailable, with no redactions
  or header exceptions. See the
  [Supplier Service summary](supplier-service/README.md#ai-use-summary-supplier-service).

- [Atomic supplier creation service](supplier-service/ai/usage-log.md#ai-20261001-002):
  Codex (GPT-6) provided Writing implementation code and Refactoring and
  documentation improvements for the creation service, plus Writing implementation
  code and Boilerplate generation for isolated PostGIS coverage. Retained changes
  validate and persist atomically, return detached values after commit, translate
  only the exact duplicate constraint, and never retry uncertain writes. Agent
  checks passed 878 creation/read/seed/unit/API tests, including 39 new creation
  cases, with one dependency warning; syntax and scoped whitespace checks passed.
  Keith confirmed review of both files; no human test rerun is claimed for this
  increment. The exact prompt and final response are recorded; original timestamp
  unavailable, with no redactions or header exceptions. See the
  [Supplier Service summary](supplier-service/README.md#ai-use-summary-supplier-service).

- [Administrator supplier POST adapter](supplier-service/ai/usage-log.md#ai-20261001-003):
  Codex (GPT-6) provided Writing implementation code for the POST adapter and
  API regressions, plus Refactoring and documentation improvements for the router
  docstring. All four files were retained and reviewed by Keith, including the
  additional GET-registration assertion correction. Agent checks passed 148
  focused API tests and all 765 unit/API tests, including 42 new POST cases,
  with one dependency warning; syntax and scoped whitespace checks passed.
  Controlled User Service responses exercised real authentication dependencies.
  Live-service and PostGIS checks were not run for this increment; no human test
  rerun is claimed. The exact prompt and verbatim relevant response excerpt are
  recorded; original timestamp unavailable, with no redactions or header exceptions.
  See the [Supplier Service summary](supplier-service/README.md#ai-use-summary-supplier-service).

- [Supplier POST duplicate-policy and concurrency verification](supplier-service/ai/usage-log.md#ai-20261001-004):
  Codex (GPT-6) provided Writing implementation code and Boilerplate generation
  for 12 additional PostGIS-backed cases in the creation integration test file.
  Retained tests cover exact duplicate rules, deleted-history preservation,
  canonical public reads, rollback, and synchronized independent commit/rollback
  races using mounted routes and controlled administrator authentication. Agent
  checks passed 199 tests, including 51 creation integration and 148 API cases,
  with one dependency warning; syntax and scoped whitespace checks passed.
  Disposable migrated databases were cleaned up. Keith confirmed review of the
  test file; no human test rerun is claimed for this increment. No requested checks
  were blocked. The exact prompt and final response are recorded; original timestamp
  unavailable, with no redactions or header exceptions. See the
  [Supplier Service summary](supplier-service/README.md#ai-use-summary-supplier-service).

- [Supplier creation documentation](supplier-service/ai/usage-log.md#ai-20261001-005):
  Codex (GPT-6) provided Refactoring and documentation improvements for the service
  README and Writing implementation code for its live HTTP smoke procedure.
  Retained content documents implemented POST, canonical examples, safe errors,
  atomic persistence, seed/API reuse, and planned feature boundaries. Schema and
  canonical-example checks, script syntax, paths, anchors, and whitespace checks
  passed. No application suite was rerun; live smoke was not executed without an
  approved administrator account and agreed provisioning process. Keith confirmed
  review of the README and procedure; no human test rerun is claimed for this
  increment. Exact prompt and final response are recorded; original timestamp
  unavailable, with no redactions or header exceptions. See the
  [Supplier Service summary](supplier-service/README.md#ai-use-summary-supplier-service).

- [Atomic versioned supplier updates](supplier-service/ai/usage-log.md#ai-20261001-006):
  Codex (GPT-6) provided Writing implementation code and Refactoring and
  documentation improvements for the service/repository layers, plus Writing
  implementation code and Boilerplate generation for update tests. Retained work
  adds merged validation, atomic version checks and category replacement, fresh
  conflict classification, and detached post-commit responses. Agent checks passed
  44 update cases, 51 creation integration cases, and 765 unit/API tests, with one
  dependency warning; syntax and whitespace checks passed. Temporary PostGIS
  resources were removed. Broader read/seed/schema suites were not run; no checks
  remained blocked. Keith reviewed all three files; no human test rerun is claimed.
  Exact prompt and final response are recorded; original timestamp unavailable,
  with no redactions or header exceptions. See the
  [Supplier Service summary](supplier-service/README.md#ai-use-summary-supplier-service).

- [Administrator supplier PATCH adapter](supplier-service/ai/usage-log.md#ai-20261001-007):
  Codex (GPT-6) provided Writing implementation code and Refactoring and
  documentation improvements for the route, Writing implementation code and
  Boilerplate generation for API tests, and Writing implementation code and
  Debugging assistance for the stale registration assertion. Retained work adds
  administrator-only PATCH, aggregate validation, positive expected versions,
  canonical saved output, and safe errors through the existing atomic service.
  Agent checks passed 55 new PATCH cases and all 820 unit/API tests after the
  assertion correction, with one dependency warning; syntax and whitespace checks
  passed. Live-service and PostGIS checks were not rerun. Keith reviewed all three
  files; no human test rerun is claimed. Exact prompt and final response are
  recorded; original timestamp unavailable, with no redactions or header exceptions.
  See the [Supplier Service summary](supplier-service/README.md#ai-use-summary-supplier-service).

- [PATCH concurrency and rollback verification](supplier-service/ai/usage-log.md#ai-20261001-008):
  Codex (GPT-6) provided Writing implementation code and Boilerplate generation
  for 13 additional update integration cases. Retained tests exercise mounted
  routes and real PostGIS with controlled authentication, synchronized independent
  writes, complete rollback snapshots, stale/no-op behavior, canonical public
  reads, and deletion-race classification. Agent checks passed 57 update integration
  cases and 174 selected API cases, with one dependency warning; syntax and
  whitespace checks passed. Disposable resources were removed. No requested checks
  were blocked; broader suites and live authentication were not run. Keith reviewed
  the retained changes; no human test rerun is claimed. The exact prompt and verbatim
  relevant response excerpt are recorded; original timestamp unavailable, with no
  redactions or header exceptions. See the
  [Supplier Service summary](supplier-service/README.md#ai-use-summary-supplier-service).

- [Implemented PATCH documentation](supplier-service/ai/usage-log.md#ai-20261001-009):
  Codex (GPT-6) provided Refactoring and documentation improvements for the
  Supplier Service README. Retained changes document mounted administrator PATCH,
  version checks, complete saved/conflict examples, atomic failure behavior, and
  test coverage/prerequisites while preserving planned DELETE and administrative
  reads. Merged example validation, exact canonical response comparison, conflict
  body, test paths, summary placement, and whitespace checks passed. No application
  suite or live smoke check was rerun; prior results remain historical. Keith
  reviewed the retained README changes; no human test rerun is claimed. Exact
  prompt and final response are recorded; original timestamp unavailable, with
  no redactions or header exceptions. See the
  [Supplier Service summary](supplier-service/README.md#ai-use-summary-supplier-service).

- [Atomic supplier soft deletion](supplier-service/ai/usage-log.md#ai-20261001-010):
  Codex (GPT-6) provided Writing implementation code and Refactoring and
  documentation improvements for the supplier repository/service, and Writing
  implementation code and Boilerplate generation for 31 new integration cases.
  Retained work adds refreshed row locking, version checks, write-free repeated
  deletion, preserved columns/assignments, and safe transaction failures without
  retries. Agent checks passed 88 update/deletion integration cases and 820 unit/API
  tests, with one dependency warning per suite; scoped whitespace checks passed.
  Disposable PostGIS resources were removed; broader integration suites were not
  run. Keith reviewed all three files; no human test rerun is claimed. Exact prompt
  and final response are recorded; original timestamp unavailable, with no
  redactions or header exceptions. See the
  [Supplier Service summary](supplier-service/README.md#ai-use-summary-supplier-service).

- [Administrator supplier DELETE adapter](supplier-service/ai/usage-log.md#ai-20261001-011):
  Codex (GPT-6) provided Writing implementation code, Refactoring and documentation
  improvements, Boilerplate generation, and Debugging assistance across the new
  administrator router, app registration, API tests, and route assertion correction.
  Retained work adds positive-version validation, empty 204 after service completion,
  safe errors, and 31 DELETE cases covering authentication, repeat deletion,
  transaction failure, cleanup, no retries, and OpenAPI. Agent checks passed
  86 focused adapter cases and all 851 unit/API tests, with one dependency warning
  per suite; whitespace checks passed. Controlled dependencies required no external
  services; PostGIS integration was not rerun for this adapter. Keith reviewed all
  four files; no human test rerun is claimed. Exact prompt and final response are
  recorded; original timestamp unavailable, with no redactions or header exceptions.
  See the [Supplier Service summary](supplier-service/README.md#ai-use-summary-supplier-service).

- [Protected administrator supplier reads](supplier-service/ai/usage-log.md#ai-20261001-012):
  Codex (GPT-6) provided Writing implementation code, Refactoring and documentation
  improvements, and Debugging assistance across the supplier repository/service,
  administrator router, and API/integration read tests. Retained work adds protected
  status-filtered listing and complete active/deleted detail reads while preserving
  anonymous active-only public reads. Agent checks passed 883 unit/API tests
  (including 91 focused read API cases) and 85 read integration tests against
  disposable PostGIS, with one dependency warning per suite; scoped whitespace
  checks passed. Initial route and working-directory errors were corrected and
  the test container removed. Broader integration suites and live authentication
  were not run. Keith reviewed all five files; no human test rerun is claimed.
  Exact prompt and final response are recorded; original timestamp unavailable,
  with no redactions or header exceptions. See the
  [Supplier Service summary](supplier-service/README.md#ai-use-summary-supplier-service).

- [Deletion lifecycle verification](supplier-service/ai/usage-log.md#ai-20261001-013):
  Codex (GPT-6) provided Writing implementation code and Boilerplate generation
  for five integration cases across supplier updates, reads, and seed imports.
  Retained tests verify mounted deletion visibility, stable repeat deletion,
  real DELETE/PATCH contention, complete retained state, cleanup, and seed
  reimport preservation. All 240 integration cases passed against disposable
  PostGIS, with one dependency warning; collection and whitespace checks passed.
  Test resources were removed; no requested checks remained blocked. Authentication
  was controlled, not live. Keith reviewed all three files; no human rerun is
  claimed. Exact prompt and final response are recorded; original timestamp
  unavailable, with no redactions or header exceptions. See the
  [Supplier Service summary](supplier-service/README.md#ai-use-summary-supplier-service).

- [Deletion and administrator-read documentation](supplier-service/ai/usage-log.md#ai-20261001-014):
  Codex (GPT-6) provided Refactoring and documentation improvements for the
  Supplier Service README, covering implemented contracts, retention/concurrency,
  seed preservation, separate service authentication, examples, and verification
  commands. A follow-up fixed a remaining stale claim with an internal link.
  Canonical examples, OpenAPI declarations, test links, summary placement, and
  whitespace checks passed; application suites and live authentication were not
  rerun. Historical results remain historical. Keith reviewed the retained work
  and correction; no human rerun is claimed. Exact prompts and relevant responses
  are recorded; original timestamps unavailable, with no redactions or header
  exceptions. See the
  [Supplier Service summary](supplier-service/README.md#ai-use-summary-supplier-service).

Disclosure-only updates do not establish submission readiness.
