"""Kafka topic and relay settings for User Service domain events."""

USER_TOPIC = "user.events"
USER_CREATED_EVENT = "user.created"

RELAY_BATCH_SIZE = 100
RELAY_POLL_SECONDS = 0.5
PUBLISH_TIMEOUT_SECONDS = 10
