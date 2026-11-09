# FoC Observability

This package provides the shared logging contract for FoC Python services.

## Contract

- Emit one JSON object per line to stdout.
- Keep `logging.getLogger(__name__)` in application modules.
- Use stable, whitespace-free event names.
- Put application values in `fields`, not directly in `LogRecord.extra`.
- Carry request and message identifiers with `log_context`.
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

Configure the process once at its entry point:

```python
from foc_observability import configure_logging

configure_logging("order-service")
```
