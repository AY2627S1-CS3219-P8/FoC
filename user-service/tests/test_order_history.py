"""Tests for the asynchronous Order Service integration boundary."""

import asyncio
from uuid import uuid4

import httpx

from app.services.order_history import HttpOrderHistoryProvider


class FakeResponse:
    """Minimal async-client response double."""

    def __init__(self, status_code, payload):
        self.status_code = status_code
        self.payload = payload

    def json(self):
        """Return the configured JSON payload."""

        return self.payload


def test_http_order_history_provider_uses_async_http_client(monkeypatch):
    """The provider awaits an async request and passes the service contract."""

    calls = {}

    class FakeAsyncClient:
        def __init__(self, **kwargs):
            calls["timeout"] = kwargs["timeout"]

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def get(self, url, **kwargs):
            calls["url"] = url
            calls["kwargs"] = kwargs
            return FakeResponse(200, {"items": [{"order_id": "order-1"}]})

    monkeypatch.setattr(httpx, "AsyncClient", FakeAsyncClient)
    user_id = uuid4()
    provider = HttpOrderHistoryProvider("http://orders/", "service-token", 1.5)

    result = asyncio.run(provider.get_for_user(user_id))

    assert result.status == "available"
    assert result.items == [{"order_id": "order-1"}]
    assert calls["timeout"] == 1.5
    assert calls["url"] == "http://orders/orders"
    assert calls["kwargs"]["params"] == {"requester_id": str(user_id)}
    assert calls["kwargs"]["headers"]["Authorization"] == "Bearer service-token"


def test_http_order_history_provider_degrades_async_transport_errors(monkeypatch):
    """A failed asynchronous request does not fail the profile boundary."""

    class FailingAsyncClient:
        def __init__(self, **_kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def get(self, *_args, **_kwargs):
            raise httpx.HTTPError("Order Service unavailable")

    monkeypatch.setattr(httpx, "AsyncClient", FailingAsyncClient)
    provider = HttpOrderHistoryProvider("http://orders", None, 1.0)

    result = asyncio.run(provider.get_for_user(uuid4()))

    assert result.status == "unavailable"
    assert result.items == []
