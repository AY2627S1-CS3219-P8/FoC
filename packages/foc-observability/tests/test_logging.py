import asyncio
import json
import logging

from foc_observability import (
    CORRELATION_ID_HEADER,
    REQUEST_ID_HEADER,
    JsonFormatter,
    RequestContextMiddleware,
    context_from_event_body,
    context_headers,
    get_context,
    log_context,
    log_event,
)


def _record(message: str = "event") -> logging.LogRecord:
    return logging.LogRecord(
        name="app.example",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg=message,
        args=(),
        exc_info=None,
    )


def test_formatter_emits_context_and_fields_as_json():
    record = _record()
    record.event = "supplier_loaded"
    record.fields = {"supplier_id": "supplier-1"}

    with log_context(request_id="request-1", correlation_id="correlation-1"):
        output = JsonFormatter(
            service="supplier-service", environment="test"
        ).format(record)

    payload = json.loads(output)
    assert payload["service"] == "supplier-service"
    assert payload["environment"] == "test"
    assert payload["event"] == "supplier_loaded"
    assert payload["supplier_id"] == "supplier-1"
    assert payload["request_id"] == "request-1"
    assert payload["correlation_id"] == "correlation-1"


def test_formatter_preserves_legacy_extra_fields():
    record = _record("readiness_failed")
    record.path = "/ready"

    payload = json.loads(
        JsonFormatter(service="supplier-service", environment="test").format(
            record
        )
    )

    assert payload["event"] == "readiness_failed"
    assert payload["path"] == "/ready"


def test_context_is_restored_after_nested_scope():
    with log_context(request_id="outer"):
        with log_context(correlation_id="inner"):
            assert get_context() == {
                "request_id": "outer",
                "correlation_id": "inner",
            }
        assert get_context() == {"request_id": "outer"}

    assert get_context() == {}


def test_log_event_uses_an_explicit_event_and_fields(caplog):
    logger = logging.getLogger("test.events")

    with caplog.at_level(logging.INFO, logger="test.events"):
        log_event(logger, logging.INFO, "worker_started", component="worker")

    record = caplog.records[-1]
    assert record.event == "worker_started"
    assert record.fields == {"component": "worker"}


def test_request_middleware_binds_context_and_returns_headers():
    request_id = "11111111-1111-4111-8111-111111111111"
    correlation_id = "22222222-2222-4222-8222-222222222222"
    observed = {}
    sent = []

    async def app(scope, receive, send):
        observed.update(get_context())
        await send({"type": "http.response.start", "status": 200, "headers": []})
        await send({"type": "http.response.body", "body": b"ok"})

    async def send(message):
        sent.append(message)

    middleware = RequestContextMiddleware(app)
    asyncio.run(
        middleware(
            {
                "type": "http",
                "headers": [
                    (b"x-request-id", request_id.encode()),
                    (b"x-correlation-id", correlation_id.encode()),
                ],
            },
            None,
            send,
        )
    )

    assert observed == {
        "request_id": request_id,
        "correlation_id": correlation_id,
    }
    response_headers = dict(sent[0]["headers"])
    assert response_headers[b"x-request-id"] == request_id.encode()
    assert response_headers[b"x-correlation-id"] == correlation_id.encode()
    assert get_context() == {}


def test_context_headers_and_event_context_are_bounded():
    event_id = "33333333-3333-4333-8333-333333333333"
    correlation_id = "44444444-4444-4444-8444-444444444444"
    order_id = "55555555-5555-4555-8555-555555555555"
    body = json.dumps(
        {
            "event_id": event_id,
            "event_type": "order.created",
            "correlation_id": correlation_id,
            "payload": {"order_id": order_id},
        }
    ).encode()

    with log_context(request_id=event_id, correlation_id=correlation_id):
        assert context_headers() == {
            REQUEST_ID_HEADER: event_id,
            CORRELATION_ID_HEADER: correlation_id,
        }

    assert context_from_event_body(body) == {
        "event_id": event_id,
        "event_type": "order.created",
        "correlation_id": correlation_id,
        "order_id": order_id,
    }
    assert context_from_event_body(b"not-json") == {}
