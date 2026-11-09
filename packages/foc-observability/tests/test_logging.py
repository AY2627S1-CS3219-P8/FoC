import json
import logging

from foc_observability import JsonFormatter, get_context, log_context, log_event


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
