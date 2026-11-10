# Operational logging

FoC services emit one JSON object per application log event. The event name is
in the `event` field; identifiers and measurements are top-level fields. Worker
logs are the operational source of truth for Kafka processing, while `/ready`
failures are the operational source of truth for API database readiness.

## Centralized logging scope

The centralized logger covers backend application processes only. The initial
collector must include these Compose services:

| Service | Process type |
| --- | --- |
| `user-service` | API |
| `user-migrate` | Migration job |
| `user-bootstrap` | Bootstrap job |
| `supplier-service` | API |
| `supplier-migrate` | Migration job |
| `supplier-seed` | Seed job |
| `credit-service` | API |
| `credit-migrate` | Migration job |
| `credit-order-worker` | Kafka worker |
| `order-service` | API |
| `order-migrate` | Migration job |
| `order-worker` | Kafka worker |

The initial collector must exclude `frontend-service`, all PostgreSQL services,
`kafka`, `kafka-topics`, `supplier-bootstrap`, and `supplier-grants`. Those
streams may be integrated later as separate infrastructure logging sources.

The collector should select services using the Docker Compose service label,
`com.docker.compose.service`, rather than container names. Several backend
services do not define an explicit `container_name`, and container names are
not a stable application identity across deployment environments.

This scope applies to centralized application-log collection. It does not
change the existing stdout behavior: backend processes continue to write
structured JSON to stdout, and the collector remains responsible for shipping
those records to the central logging backend.

## Log envelope

Every structured backend application record uses log schema version `1` and
contains these fields:

| Field | Type | Meaning |
| --- | --- | --- |
| `schema_version` | integer | Version of the logging envelope; currently `1`. |
| `timestamp` | ISO-8601 UTC string | Time the process created the record. |
| `level` | string | `DEBUG`, `INFO`, `WARNING`, `ERROR`, or `CRITICAL`. |
| `service` | string | Stable backend service identity. |
| `component` | string | Process role, such as `api`, `worker`, `migration`, `bootstrap`, or `seed`. |
| `service_version` | string | Build identifier from `APP_VERSION`, or `unknown`. |
| `environment` | string | Deployment environment, such as `development`, `test`, or `production`. |
| `logger` | string | Python logger name. |
| `event` | string | Lower-snake-case event name. |

Request, message, and domain identifiers such as `request_id`,
`correlation_id`, `event_id`, and `order_id` are optional top-level fields when
available. Application fields must not override envelope fields. Sensitive
values remain subject to the shared redaction rules.

## Worker signals

Both Kafka workers emit the following events with `worker`, `topic`, and
`consumer_group` where applicable:

| Event | Meaning |
| --- | --- |
| `worker_started` | The worker has created its Kafka and database clients and entered its loop. |
| `worker_heartbeat` | The loop is alive; emitted every 60 seconds. |
| `worker_shutdown` | Shutdown cleanup has started. |
| `worker_relay_completed` | At least one outbox or parked record was published; `count` is the batch size. |
| `*_relay_failed` | An outbox relay attempt failed and its transaction was rolled back. |
| `message_processing_completed` / `credit_event_processing_completed` | One delivery finished; includes `duration_ms`, `outcome`, and `attempts` where available. |
| `message_retry_exhausted` / `credit_event_retry_exhausted` | A delivery used all permitted processing attempts. |
| `message_sent_to_dlq` / `credit_event_sent_to_dlq` | Kafka confirmed quarantine publication. |
| `message_parked_for_dlq` | The Order worker stored a record locally because its DLQ was unavailable. |

The Credit worker's `credit_event_sent_to_dlq` event is emitted only after the
DLQ publish is confirmed and before the source offset is committed. A failed
publish therefore does not look like a successful quarantine.

## Alert guidance

These are collector rules, not application-side timers:

| Condition | Suggested alert |
| --- | --- |
| No `worker_heartbeat` from an expected worker for 120 seconds | Page: worker stopped, wedged, or unable to emit logs. |
| Any `*_retry_exhausted`, `*_dead_lettered`, or `*_parked_for_dlq` event | Page or create a high-priority incident; inspect the event IDs, source offsets, and exception category. |
| DLQ events or parked records continue increasing for 5 minutes | Page: quarantine backlog is growing faster than it is being investigated or relayed. |
| Any `*_relay_failed` event, especially repeated failures | Warn on the first event; page when repeated for 5 minutes because the transactional outbox may be accumulating. |
| `readiness_check_failed` for 3 consecutive checks or 2 minutes | Page: the API is unavailable or its database/migration state is unhealthy. |
| `duration_ms` exceeds the service's normal processing SLO | Warn and investigate database, broker, or downstream latency. |

Alert rules should group by `service`, `worker`, `topic`, and `consumer_group`
and should retain `event_id`, `correlation_id`, `order_id`, and source partition
and offset when present. Alert payloads should never be used as a substitute
for these safe identifiers; credentials, bearer tokens, login input, and
database URLs remain excluded from structured logs.
