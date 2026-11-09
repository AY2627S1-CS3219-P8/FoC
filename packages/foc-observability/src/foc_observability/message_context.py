"""Safe correlation fields extracted from domain-event payloads."""

from __future__ import annotations

import json
from typing import Any

from .context import normalize_identifier


def context_from_event_body(body: bytes | None) -> dict[str, str]:
    """Extract bounded identifiers from an event without raising on bad input."""

    if not body:
        return {}
    try:
        envelope: Any = json.loads(body)
    except (TypeError, ValueError, json.JSONDecodeError):
        return {}
    if not isinstance(envelope, dict):
        return {}

    fields: dict[str, str] = {}
    for name in ("event_id", "correlation_id"):
        identifier = normalize_identifier(envelope.get(name))
        if identifier is not None:
            fields[name] = identifier

    event_type = envelope.get("event_type")
    if (
        isinstance(event_type, str)
        and 0 < len(event_type) <= 64
        and event_type.isprintable()
    ):
        fields["event_type"] = event_type

    payload = envelope.get("payload")
    if isinstance(payload, dict):
        order_id = normalize_identifier(payload.get("order_id"))
        if order_id is not None:
            fields["order_id"] = order_id
    return fields
