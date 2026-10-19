# FoC asynchronous contracts

`asyncapi.yaml` is the canonical, versioned description of messages published
to the durable Kafka domain topics. Producers and consumers must update this
file before adding fields or event types.

Version 1 envelopes always carry `event_id`, `event_type`, `schema_version`,
`occurred_at`, `correlation_id`, and a typed `payload`. Consumers must ignore
unknown optional payload fields within version 1, deduplicate by `event_id`,
and treat a breaking change as a new schema version.

Topic and consumer ownership:

- Order Service publishes `order.events`; Credit Service consumes it as
  `credit-service-order`.
- User Service publishes `user.events`; Credit Service consumes it as
  `credit-service-user`.
- Credit Service publishes `credit.events`; Order Service consumes it with its
  own stable group.

Topic creation belongs to `event-broker/create-topics.sh`. Producers wait for
Kafka delivery confirmation; consumers disable automatic commits and commit
their offsets only after durable processing or confirmed DLQ publication.
Credit Service reports credit outcomes, while Order Service owns the resulting
Order state changes.

For `order.cancelled`, Credit Service uses `previous_status` to select the
financial outcome. Before pickup it releases the reservation to the requester.
After `PICKED_UP`, the event must include `courier_id`; Credit Service transfers
the reservation to that courier and publishes `credit.transferred` with reason
`ORDER_CANCELLED_AFTER_PICKUP`.

`order.events` and `credit.events` records are keyed by `order_id`;
`user.events` records are keyed by `user_id`. Kafka therefore preserves order
for one aggregate within its partition while allowing different aggregates to
be processed in parallel. Records also carry `event_type` and `event_id`
headers matching the JSON envelope.
