# FoC asynchronous contracts

`asyncapi.yaml` is the canonical, versioned description of messages published
to the durable `foc.events` RabbitMQ topic exchange. Producers and consumers
must update this file before adding fields or event types.

Version 1 envelopes always carry `event_id`, `event_type`, `schema_version`,
`occurred_at`, `correlation_id`, and a typed `payload`. Consumers must ignore
unknown optional payload fields within version 1, deduplicate by `event_id`,
and treat a breaking change as a new schema version.

Queue ownership:

- Credit Service owns `credit-service.order-events` and
  `credit-service.user-events`.
- Order Service owns `order-service.credit-events`.

Each consumer declares its own queues and bindings. Producers declare the
shared exchange and publish with confirms and mandatory routing; they do not
declare downstream services' queues or decide downstream state transitions.
Credit Service reports credit outcomes, while Order Service owns the resulting
Order state changes.

For `order.cancelled`, Credit Service uses `previous_status` to select the
financial outcome. Before pickup it releases the reservation to the requester.
After `PICKED_UP`, the event must include `courier_id`; Credit Service transfers
the reservation to that courier and publishes `credit.transferred` with reason
`ORDER_CANCELLED_AFTER_PICKUP`.

The routing key is currently the event type. Per-order ordering therefore
depends on a single active consumer for each order queue until the Order Service
publisher adopts an order-keyed partitioning strategy.
