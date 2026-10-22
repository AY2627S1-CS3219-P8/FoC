# Event broker

One Kafka node serves the Compose network at `kafka:9092`; it has no host
port. The one-shot `kafka-topics` job creates all topics because broker-side
automatic topic creation is disabled.

## Topics

| Topic | Partitions | Retention | Key | Producer |
| --- | ---: | --- | --- | --- |
| `order.events` | 3 | forever | `order_id` | Order Service |
| `credit.events` | 3 | forever | `order_id` | Credit Service |
| `order-service.credit-events.dlq` | 1 | 7 days | copied source key | Order Service |
| `credit-service.order-events.dlq` | 1 | 7 days | copied source key | Credit Service |

Records for one aggregate use the same key and therefore remain ordered within
one partition. Different aggregates can be processed in parallel. Each service
uses its own stable consumer group and explicitly commits offsets only after
database work or confirmed DLQ publication.

## Inspect

From the repository root, after `docker compose up kafka kafka-topics`:

```bash
docker compose exec kafka /opt/kafka/bin/kafka-topics.sh \
  --bootstrap-server kafka:9092 --describe

docker compose exec kafka /opt/kafka/bin/kafka-console-consumer.sh \
  --bootstrap-server kafka:9092 --topic order.events --from-beginning \
  --property print.key=true --property print.headers=true
```

## A new consumer

Subscribe with a new `group.id`. `auto.offset.reset=earliest` reads from offset
0 when that group has no committed offset. One group's commits do not advance
another group's position.
