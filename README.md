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

## Administrator Bootstrap

The initial administrator is configured through the `BOOTSTRAP_ADMIN_*`
variables in `.env`. See the
[user-service bootstrap documentation](./user-service/README.md#first-administrator-bootstrap)
for setup details and behavior.

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

No file header exceptions apply to these Supplier Service records. Disclosure-only
updates do not establish human review or submission readiness.
