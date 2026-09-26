"""Order-history integration boundary for the User Service.

The User Service owns identity, not orders. This module keeps that boundary
explicit while Order Service is still being developed. Until
``ORDER_SERVICE_URL`` is configured, profiles report order history as
unavailable instead of presenting an unavailable dependency as an empty
history.
"""

from dataclasses import dataclass
import logging
import os
from typing import Literal, Protocol
from uuid import UUID

import httpx


logger = logging.getLogger(__name__)
OrderHistoryStatus = Literal["available", "unavailable"]


@dataclass(frozen=True)
class OrderHistoryResult:
    """Order history data and whether its source was reachable."""

    status: OrderHistoryStatus
    items: list[dict[str, object]]


class OrderHistoryProvider(Protocol):
    """Contract for retrieving history without coupling user persistence to orders."""

    async def get_for_user(self, user_id: UUID) -> OrderHistoryResult:
        """Return the order history for one authenticated user."""


class UnavailableOrderHistoryProvider:
    """Provider used while Order Service is not configured or not deployed."""

    async def get_for_user(self, user_id: UUID) -> OrderHistoryResult:
        """Report that order history is not currently available."""

        return OrderHistoryResult(status="unavailable", items=[])


class HttpOrderHistoryProvider:
    """Read order history from the configured internal Order Service API.

    The integration contract is ``GET /orders?requester_id=<user UUID>`` with
    a response shaped as ``{"items": [{...}]}``. Order Service remains the
    source of truth for the item shape and lifecycle.
    """

    def __init__(self, base_url: str, service_token: str | None, timeout: float):
        self.base_url = base_url.rstrip("/")
        self.service_token = service_token
        self.timeout = timeout

    async def get_for_user(self, user_id: UUID) -> OrderHistoryResult:
        """Fetch history, degrading to an explicit unavailable result on failure."""

        headers = {"Accept": "application/json"}
        if self.service_token:
            headers["Authorization"] = f"Bearer {self.service_token}"

        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.get(
                    f"{self.base_url}/orders",
                    params={"requester_id": str(user_id)},
                    headers=headers,
                )
                if response.status_code != 200:
                    return self._unavailable(user_id, f"HTTP {response.status_code}")
                payload = response.json()
        except (httpx.HTTPError, OSError, TimeoutError, ValueError) as exc:
            return self._unavailable(user_id, type(exc).__name__)

        items = payload.get("items") if isinstance(payload, dict) else None
        if not isinstance(items, list) or not all(isinstance(item, dict) for item in items):
            return self._unavailable(user_id, "invalid response shape")

        return OrderHistoryResult(status="available", items=items)

    @staticmethod
    def _unavailable(user_id: UUID, reason: str) -> OrderHistoryResult:
        """Log a safe diagnostic without logging response data or credentials."""

        logger.warning(
            "Order history unavailable",
            extra={"user_id": str(user_id), "reason": reason},
        )
        return OrderHistoryResult(status="unavailable", items=[])


def _create_provider() -> OrderHistoryProvider:
    """Build the configured provider, defaulting to an explicit unavailable state."""

    base_url = os.getenv("ORDER_SERVICE_URL", "").strip()
    if not base_url:
        return UnavailableOrderHistoryProvider()

    try:
        timeout = float(os.getenv("ORDER_SERVICE_TIMEOUT_SECONDS", "2"))
    except ValueError:
        timeout = 2.0

    return HttpOrderHistoryProvider(
        base_url=base_url,
        service_token=os.getenv("ORDER_SERVICE_TOKEN") or None,
        timeout=max(timeout, 0.1),
    )


order_history_provider = _create_provider()


async def get_order_history(user_id: UUID) -> OrderHistoryResult:
    """Retrieve order history through the configured provider."""

    return await order_history_provider.get_for_user(user_id)
