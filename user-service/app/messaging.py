"""RabbitMQ contract and relay settings for User Service domain events."""

EXCHANGE = "foc.events"
USER_CREATED_EVENT = "user.created"

RELAY_BATCH_SIZE = 100
RELAY_POLL_SECONDS = 0.5
RABBITMQ_PORT = 5672
