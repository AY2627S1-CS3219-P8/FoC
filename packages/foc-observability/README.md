# FoC Observability

This package provides the shared logging contract for FoC Python services.

## Contract

- Emit one JSON object per line to stdout.
- Keep `logging.getLogger(__name__)` in application modules.
- Use stable, whitespace-free event names.
- Put application values in `fields`, not directly in `LogRecord.extra`.
- Carry request and message identifiers with `log_context`.
- Add `RequestContextMiddleware` to FastAPI applications.
- Emit one `http_request_completed` event per HTTP request with the method,
  route, status code, duration, and outcome.
- Uvicorn's duplicate text-style access log is suppressed in favor of that
  structured request event.
- Only values supplied through the structured `fields` mapping are emitted;
  unstructured `LogRecord.extra` values are ignored. Sensitive field names,
  bearer credentials, credentialed URLs, and exception text are redacted.
- Never log credentials, bearer tokens, passwords, database URLs, or raw
  request/response bodies.

## Example

```python
import logging

from foc_observability import log_event, log_context

logger = logging.getLogger(__name__)

with log_context(request_id=str(request_id), user_id=str(user_id)):
    log_event(
        logger,
        logging.INFO,
        "order_created",
        order_id=str(order_id),
    )
```

For an ASGI/FastAPI application, add the middleware once during app creation:

```python
app.add_middleware(RequestContextMiddleware)
```

Outbound HTTP clients should use `context_headers()`. Kafka consumers can use
`context_from_event_body()` together with the topic, partition, and offset in
`log_context`; a valid event's `event_id` is also installed as `request_id`,
and bounded UUID actor fields such as `requester_id` and `courier_id` are
carried into the log context.

Configure the process once at its entry point:

```python
from foc_observability import configure_logging

configure_logging("order-service")
```
