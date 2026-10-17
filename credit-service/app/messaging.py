"""RabbitMQ names and reliability tunables shared with Order Service v1."""

EXCHANGE = "foc.events"

# Credit Service owns and declares these inbound queues.
ORDER_EVENTS_QUEUE = "credit-service.order-events"
ORDER_EVENTS_DLQ = "credit-service.order-events.dlq"
USER_EVENTS_QUEUE = "credit-service.user-events"
USER_EVENTS_DLQ = "credit-service.user-events.dlq"

ORDER_EVENT_TYPES = frozenset(
    {"order.created", "order.completed", "order.cancelled", "order.expired"}
)
USER_EVENT_TYPES = frozenset({"user.created"})
INCOMING_EVENT_TYPES = ORDER_EVENT_TYPES | USER_EVENT_TYPES
CREDIT_EVENT_TYPES = frozenset(
    {
        "credit.reserved",
        "credit.reservation_failed",
        "credit.transferred",
        "credit.released",
    }
)
OUTGOING_EVENT_TYPES = CREDIT_EVENT_TYPES
EVENT_STREAM_QUEUES = {
    "order": ORDER_EVENTS_QUEUE,
    "user": USER_EVENTS_QUEUE,
}

QUEUE_MAX_LENGTH = 100_000
RELAY_BATCH_SIZE = 100
RELAY_POLL_SECONDS = 0.5
RABBITMQ_PORT = 5672
HTTP_TIMEOUT_SECONDS = 3.0
