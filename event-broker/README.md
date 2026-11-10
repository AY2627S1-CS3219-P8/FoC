<!--
AI Assistance Disclosure:
Tool: Claude Code (model: claude-opus-5-5), date: 2026-11-06
Scope: Refactoring and documentation improvements — document the Notification Service DLQ topic's max.message.bytes limit (ai-20261106-001).
Author review: Keith confirmed on 2026-11-08: full pytest suite with PostgreSQL 16 and Kafka 4.1.2, 645 passed; code manually read and verified; manual checks in an isolated Compose run (ai-20261106-001).
Details: notification-service/ai/usage-log.md; ai-20261106-001
-->

# Event broker

One Kafka node for the Compose network. It listens at `kafka:9092` and does not publish a host port. Topics are created by the `kafka-topics` job. The broker does not create topics on its own.

## Topics

| Topic | Partitions | Retention | Key | Producer |
| --- | --- | --- | --- | --- |
| `order.events` | 3 | forever | `order_id` | Order Service |
| `credit.events` | 3 | forever | `order_id` | Credit Service |
| `order-service.credit-events.dlq` | 1 | broker default (7 days) | copied from the failed record | Order Service, for credit messages it cannot apply |
| `credit-service.order-events.dlq` | 1 | broker default (7 days) | copied from the failed record | Credit Service, for order messages it cannot apply |
| `notification-service.order-events.dlq` | 1 | broker default (7 days) | copied from the failed record | Notification Service, for order messages it cannot apply |

`notification-service.order-events.dlq` has `max.message.bytes=1100000`, above the broker's default, so that a record `order.events` accepted still fits with the diagnostic headers. `create-topics.sh` also applies this to a topic that already exists.

A record for one order always lands on the same partition, so that order's events stay in order. Different orders can be on different partitions.

## Inspect

From the repo root, after `docker compose up kafka kafka-topics`:

```bash
docker compose exec kafka /opt/kafka/bin/kafka-topics.sh \
  --bootstrap-server kafka:9092 --describe

docker compose exec kafka /opt/kafka/bin/kafka-console-consumer.sh \
  --bootstrap-server kafka:9092 --topic order.events --from-beginning \
  --property print.key=true --property print.headers=true
```

## A new consumer

Subscribe with a new `group.id`. `auto.offset.reset=earliest` reads the topic from offset 0, including events published before the consumer existed. Each group keeps its own offset, so one consumer does not affect another.
