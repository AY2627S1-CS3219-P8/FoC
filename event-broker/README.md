# Event broker

One Kafka node for the Compose network. It listens at `kafka:9092` and does not publish a host port. Topics are created by the `kafka-topics` job. The broker does not create topics on its own.

## Topics

| Topic | Partitions | Retention | Key | Producer |
| --- | --- | --- | --- | --- |
| `order.events` | 3 | forever | `order_id` | Order Service |
| `credit.events` | 3 | forever | `order_id` | Credit Service |
| `order-service.credit-events.dlq` | 1 | broker default (7 days) | copied from the failed record | Order Service, for credit messages it cannot apply |

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
