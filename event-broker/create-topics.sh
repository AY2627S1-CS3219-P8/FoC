#!/bin/bash
# Create the topics Order Service and Credit Service share. Safe to run again.

set -euo pipefail

bootstrap="${KAFKA_BOOTSTRAP_SERVERS:-kafka:9092}"
topics=/opt/kafka/bin/kafka-topics.sh

create_topic() {
  local name="$1"
  local partitions="$2"
  shift 2
  "$topics" --bootstrap-server "$bootstrap" --create --if-not-exists \
    --topic "$name" --partitions "$partitions" --replication-factor 1 "$@"
}

create_topic order.events 3 --config retention.ms=-1
create_topic credit.events 3 --config retention.ms=-1
create_topic order-service.credit-events.dlq 1
create_topic credit-service.order-events.dlq 1
