"""RabbitMQ names and tunables. These are constants, not environment variables."""

from datetime import timedelta

EXCHANGE = "foc.events"

# Queues this service consumes.
CREDIT_QUEUE = "order-service.credit-events"
CREDIT_DLQ = "order-service.credit-events.dlq"
EXPIRY_DELAY_QUEUE = "order-service.expiry-delay"
EXPIRY_DUE_QUEUE = "order-service.expiry-due"
EXPIRY_DUE_DLQ = "order-service.expiry-due.dlq"

# Durable buffers so order events survive until the owning service consumes them.
# A topic exchange drops publishes that match no queue.
CREDIT_SERVICE_QUEUE = "credit-service.order-events"
NOTIFICATION_QUEUE = "notification-service.order-events"

INCOMING_EVENT_TYPES = frozenset(
    {"credit.reserved", "credit.reservation_failed", "order.created"}
)

ORDER_TTL = timedelta(hours=1)
EXPIRY_TTL_MS = 3_600_000
QUEUE_MAX_LENGTH = 100_000
MAX_ATTEMPTS = 5
RETRY_BACKOFF_SECONDS = (0.5, 1.0, 2.0, 4.0)
RELAY_BATCH_SIZE = 100
RELAY_POLL_SECONDS = 0.5
RABBITMQ_PORT = 5672
HTTP_TIMEOUT_SECONDS = 3.0

CONSUMED_QUEUES = (CREDIT_QUEUE, EXPIRY_DUE_QUEUE)
PURGEABLE_QUEUES = (
    CREDIT_QUEUE,
    CREDIT_DLQ,
    EXPIRY_DELAY_QUEUE,
    EXPIRY_DUE_QUEUE,
    EXPIRY_DUE_DLQ,
    CREDIT_SERVICE_QUEUE,
    NOTIFICATION_QUEUE,
)
