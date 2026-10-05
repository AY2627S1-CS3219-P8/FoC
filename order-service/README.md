# Order Service

Errand requests for Friend on Campus: create an order, hold it until credit is reserved, then run it through accept, pickup, completion, cancellation, and one-hour expiry.

The API never talks to RabbitMQ. Each state change and its event are committed together. `order-worker` publishes those events and applies credit and expiry messages. A broker outage cannot fail an API call, and a committed event is not lost.

## Run with Compose

`docker compose up` now requires four more values in `.env`. Copy them from `.env.example` if they are missing:

- `ORDER_DB_USER`
- `ORDER_DB_PASSWORD`
- `RABBITMQ_USER`
- `RABBITMQ_PASSWORD`

Passwords are not put in database URLs. Postgres reads `PGPASSWORD`, and the worker passes the RabbitMQ password to the client.

```bash
docker compose up --build order-db order-migrate order-service order-worker rabbitmq
curl -sS http://127.0.0.1:8082/ready
```

The worker log line `worker_started` means the exchange and queues exist. The RabbitMQ management UI is at `http://127.0.0.1:15672` (the `.env` user and password). Dead-lettered messages sit in `order-service.credit-events.dlq` and `order-service.expiry-due.dlq`; inspect or replay them from that UI.

Creating an order through this stack still needs Supplier Service's `GET /suppliers/{id}` and a Credit Service. Neither is available from `main` yet, so this smoke check stops at readiness, the worker log, and the queues.

## API

Every route except `/health` and `/ready` requires `Authorization: Bearer <session>`. The token is forwarded to User Service `GET /users/me`. A 401 from User Service stays a 401. A timeout or any other failure is a 503.

| Method | Path | Who | Result |
| --- | --- | --- | --- |
| `POST` | `/orders` | requester | `201`, or `200` when the same `Idempotency-Key` and body are retried |
| `GET` | `/orders/open?limit&offset` | any active user | open errands except the caller's, newest first |
| `GET` | `/orders?role=requester\|courier&limit&offset` | caller | that caller's own orders |
| `GET` | `/orders/{id}` | requester, assigned courier, or admin | one order; anyone else gets `404` |
| `PATCH` | `/orders/{id}/delivery` | requester, before pickup | replaces the destination |
| `POST` | `/orders/{id}/accept` | anyone except the requester | first committed accept wins; the others get `409` |
| `POST` | `/orders/{id}/pickup` | assigned courier | |
| `POST` | `/orders/{id}/complete` | requester | does not touch credit balances |
| `POST` | `/orders/{id}/cancel` | requester before pickup, or an admin until the order is closed | |

`POST /orders` requires `Idempotency-Key` (max 128 characters). `X-Correlation-ID` is optional and must be a UUID. Pages are `{items, total, limit, offset}`. Errors are `{"detail": ...}`. A database outage is `503`.

Repeating an action that the same person already completed returns `200` and does not write another event. An illegal transition returns `409`, leaves the row unchanged, and logs `illegal_order_transition`.

Pickup must be an active supplier (`GET {SUPPLIER_SERVICE_URL}/suppliers/{id}`). `404` with code `SUPPLIER_NOT_FOUND` is `422`. Any other response, including a `404` from an unmounted route, is `503`. Delivery coordinates must fall inside latitude 1.288–1.310 and longitude 103.750–103.788, which covers the seeded stores and University Town.

## States

`PENDING_CREDIT` → `OPEN` when Credit publishes `credit.reserved`, or → `REJECTED` when it publishes `credit.reservation_failed`. `OPEN` → `ACCEPTED` → `PICKED_UP` → `COMPLETED`. The requester can cancel before pickup. An admin can cancel until the order is closed, including after pickup. `PENDING_CREDIT` and `OPEN` expire one hour after creation. `COMPLETED`, `CANCELLED`, `EXPIRED`, and `REJECTED` do not change again.

## Event contract (v1)

Durable topic exchange: `foc.events`. The routing key is the event type. The AMQP `message_id` is `event_id`, and the headers include `order_id`.

```json
{"event_id": "uuid", "event_type": "order.accepted", "schema_version": 1,
 "occurred_at": "2026-10-05T07:12:03.000000Z", "correlation_id": "uuid",
 "payload": {"order_id": "uuid", "requester_id": "uuid", "courier_id": "uuid", "credit_amount": 8}}
```

Published events, in the life of an order: `order.created` (adds `expires_at`), `order.opened`, `order.rejected` (adds `reason`), `order.accepted`, `order.picked_up`, `order.completed`, `order.cancelled` (adds `cancelled_by` and `previous_status`), `order.expired`. Payloads carry identifiers and the credit amount, not names or contact details. `order.cancelled` with `previous_status` of `PICKED_UP` is the signal for Credit to compensate the courier.

Consumed events, which Credit Service must publish to `foc.events`: `credit.reserved` and `credit.reservation_failed` (payload `reason`). A repeated `event_id`, or a message for an order that has already moved on, changes nothing. Credit should release a reservation when it sees `order.cancelled` or `order.expired`, including when that event arrives before `credit.reserved` is published.

Queues this service declares:

| Queue | Binding | Notes |
| --- | --- | --- |
| `order-service.expiry-delay` | `order.created` | holds each message for 1 hour, then dead-letters it |
| `order-service.expiry-due` | dead-letter target of the delay queue | the worker expires `PENDING_CREDIT` and `OPEN` orders |
| `order-service.credit-events` | `credit.reserved`, `credit.reservation_failed` | |
| `credit-service.order-events` | `order.#` | buffer so order events are not dropped before Credit Service runs |
| `notification-service.order-events` | `order.#` | same, for Notification Service |

Do not redeclare those two downstream queues with different arguments. Consume them, or the broker will reject the declaration. Each is capped at 100,000 messages; past that the broker refuses the publish and the event stays in the outbox until the queue drains, which also holds up every event behind it. A handler that still fails after retries at 0.5s, 1s, 2s, and 4s is dead-lettered to `<queue>.dlq`. There is one worker replica, so events for an order stay in outbox id order.

## Tests

From `order-service/`, with the dev requirements installed:

```bash
python -m pytest -q
```

That is level 1: SQLite, FastAPI's test client, and fakes. A bearer token `user:<uuid>` or `admin:<uuid>` stands in for User Service. No Docker.

Level 2 uses a real Postgres database whose name ends in `_test`, and RabbitMQ. It checks that the Alembic migration matches the models, that ten concurrent accepts produce one winner, that a fake Credit reply completes an ordered round trip, that the one-hour queue expires an order exactly once, that a bad message lands in the dead-letter queue, and that a feed page and a transition of 22,500 open orders stay inside the latency limits.

```bash
docker run -d --name foc-order-test-db \
  -e POSTGRES_USER=foc -e POSTGRES_PASSWORD=foc_ci -e POSTGRES_DB=foc_orders_test \
  -p 54329:5432 postgres:16-alpine
docker run -d --name foc-order-test-mq \
  -e RABBITMQ_DEFAULT_USER=foc -e RABBITMQ_DEFAULT_PASS=foc_ci \
  -p 5672:5672 rabbitmq:4.1.8-management-alpine
export TEST_DATABASE_URL=postgresql+psycopg://foc@127.0.0.1:54329/foc_orders_test
export PGPASSWORD=foc_ci
export RABBITMQ_HOST=127.0.0.1 RABBITMQ_USER=foc RABBITMQ_PASSWORD=foc_ci
python -m pytest -q
```

Without those variables the integration file is skipped. CI sets them and also runs `alembic upgrade head`, `alembic check`, and `docker build`.

## Develop

Python 3.12. Schema changes go in `alembic/versions/` as `YYYYMMDD_NNNN_snake.py`. Do not call `create_all` at startup. Tunables such as the one-hour TTL, the HTTP timeout, the relay batch, and the retry delays are constants in `app/messaging.py`, not environment variables.
