# Credit Service

Infrastructure and business rules for FoC's closed credit economy. The service provides the
database schema, migrations, authenticated read APIs, event contracts,
transactional-outbox plumbing, RabbitMQ consumer/relay, health checks,
container image, Compose services, and tests. Transport-independent balance and
reservation rules live in `app/services/credits.py`; event-to-domain and
domain-to-outbox translation lives in `app/services/event_handlers.py`.
Numbered `AUDIT` comments and `BUSINESS_LOGIC_AUDIT.md` provide a review map.

## Run the infrastructure

Copy `.env.example` to `.env`, replace the example secrets, then run:

```bash
docker compose up --build credit-db credit-migrate credit-service rabbitmq
curl http://127.0.0.1:8083/health
curl http://127.0.0.1:8083/ready
```

The `credit-order-worker` and `credit-user-worker` may be started after the
database migration. Order Service must own and bind its credit-result queue for
mandatory `credit.*` publication to succeed.

## HTTP surface

All public routes forward an opaque bearer token to User Service `/users/me`.
User status must be active. Admin routes also require `role=admin`.

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/health` | Process liveness; no dependency checks |
| `GET` | `/ready` | Database connectivity and migration-head check |
| `GET` | `/credits/me` | Own available, reserved, and total balance |
| `GET` | `/credits/me/transactions` | Own paginated audit history |
| `GET` | `/admin/credits/{user_id}` | Administrator investigation view |
| `GET` | `/admin/credits/{user_id}/transactions` | Administrator audit view |
| `POST` | `/admin/credits/{user_id}/adjust` | Auditable administrator correction |
| `PUT` | `/admin/credit-accounts/{user_id}` | Idempotent administrator recovery |

The recovery route requires a valid User Service bearer token for an active
administrator. Normal account creation is exclusively event-driven: User
Service commits a `user.created` outbox event with the new account and Credit
Service consumes it. The administrator route is a manual repair path, not a
second normal registration workflow.

## Event contract

Durable topic exchange: `foc.events`. The Credit worker consumes two queues:

- `credit-service.order-events`, bound exactly to `order.created`,
  `order.completed`, `order.cancelled`, and `order.expired`;
- `credit-service.user-events`, bound exactly to `user.created`.

Every v1 event contains:

```json
{
  "event_id": "uuid",
  "event_type": "order.created",
  "schema_version": 1,
  "occurred_at": "2026-10-16T04:00:00Z",
  "correlation_id": "uuid",
  "payload": {
    "order_id": "uuid",
    "requester_id": "uuid",
    "credit_amount": 8
  }
}
```

Consumed events are `order.created`, `order.completed`, `order.cancelled`, and
`order.expired`, plus `user.created`. A completed event must also carry
`courier_id`. A cancellation whose `previous_status` is `PICKED_UP` must carry
`courier_id` because its reservation is paid to that courier. The outbox
publishes `credit.reserved`,
`credit.reservation_failed`, `credit.transferred`, and `credit.released` to the
exchange. Order Service owns its queue, bindings, and resulting order-state
transitions; Credit Service does not declare or mutate them.

Both incoming queues use bounded retries and explicit durable dead-letter
queues. `credit-user-worker` consumes only account-creation events and
`credit-order-worker` consumes only Order lifecycle events, so a retry in one
stream cannot prevent the other stream from progressing.

The retry schedule is configured through `CREDIT_RETRY_BACKOFF_SECONDS`; the
default `0.5,1,2,4` means five total attempts, a longest individual wait of
four seconds, and 7.5 seconds of total waiting. Malformed messages bypass retry
and go directly to the relevant DLQ. Other exceptions are treated as
transient; business rejections such as insufficient balance must be committed
outcomes, not raised exceptions.

### Order Service integration requirement

Order Service must declare `order-service.credit-events`, bind it to all four
`credit.*` outcomes above, and apply
the corresponding order-state changes. It must also stop adding an `order.#`
binding to `credit-service.order-events`: RabbitMQ bindings accumulate, so that
wildcard would defeat the exact four-event contract declared here.

## Persistence model

- `credit_accounts`: one row per User Service UUID, with non-negative available
  and reserved balances.
- `credit_reservations`: one unique reservation per order and an explicit
  ACTIVE/TRANSFERRED/RELEASED state.
- `credit_transactions`: immutable successful/rejected audit records with
  signed available/reserved deltas, retained independently of account state.
- `processed_events`: durable inbox deduplication by event UUID.
- `outbox_events`: events committed in the same transaction as credit changes.

## Saga participant behavior

- `order.created` reserves available credit and emits `credit.reserved`, or
  commits a rejected audit row and emits `credit.reservation_failed`.
- `order.completed` atomically settles an active reservation to the courier and
  emits `credit.transferred`.
- `order.cancelled` before pickup and `order.expired` return an active
  reservation to the requester and emit `credit.released`.
- `order.cancelled` after pickup settles the reservation to the courier and
  emits `credit.transferred` with reason `ORDER_CANCELLED_AFTER_PICKUP`.
- Duplicate event UUIDs are ignored by the inbox. A second event for the same
  order cannot repeat a balance mutation because the reservation state is also
  checked.
- Contradictory lifecycle events raise without committing, allowing retries and
  eventual DLQ investigation rather than silently changing credit state.

Schema changes must be added as Alembic migrations; the application never runs
`create_all` at startup.

## Tests

```bash
python -m pip install -r requirements-dev.txt
pytest
```
