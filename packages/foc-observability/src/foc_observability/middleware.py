"""ASGI middleware for request-scoped logging context."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from .context import (
    CORRELATION_ID_HEADER,
    REQUEST_ID_HEADER,
    log_context,
    normalize_identifier,
)


class RequestContextMiddleware:
    """Attach validated request identifiers to logs and response headers."""

    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope.get("type") != "http":
            await self.app(scope, receive, send)
            return

        request_id = _header_value(scope, REQUEST_ID_HEADER)
        request_id = normalize_identifier(request_id) or str(uuid4())
        correlation_id = (
            normalize_identifier(_header_value(scope, CORRELATION_ID_HEADER))
            or request_id
        )

        async def send_with_context(message: dict[str, Any]) -> None:
            if message.get("type") == "http.response.start":
                response = dict(message)
                headers = [
                    (name, value)
                    for name, value in message.get("headers", [])
                    if name.lower()
                    not in {
                        REQUEST_ID_HEADER.lower().encode("ascii"),
                        CORRELATION_ID_HEADER.lower().encode("ascii"),
                    }
                ]
                headers.extend(
                    [
                        (REQUEST_ID_HEADER.lower().encode("ascii"), request_id.encode()),
                        (
                            CORRELATION_ID_HEADER.lower().encode("ascii"),
                            correlation_id.encode(),
                        ),
                    ]
                )
                response["headers"] = headers
                message = response
            await send(message)

        with log_context(
            request_id=request_id,
            correlation_id=correlation_id,
        ):
            await self.app(scope, receive, send_with_context)


def _header_value(scope: dict[str, Any], name: str) -> str | None:
    wanted = name.lower().encode("ascii")
    values = []
    for header_name, header_value in scope.get("headers", []):
        if header_name.lower() == wanted:
            try:
                values.append(header_value.decode("ascii"))
            except UnicodeDecodeError:
                return None
    return values[0] if len(values) == 1 else None
