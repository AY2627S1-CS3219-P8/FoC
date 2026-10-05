"""User Service and Supplier Service clients."""

from uuid import UUID

import httpx
import pytest

from app.clients import (
    AuthenticationUnavailableError,
    InvalidSessionError,
    SupplierServiceClient,
    SupplierUnavailableError,
    UserServiceClient,
)

USER_ID = "11111111-1111-1111-1111-111111111111"
SUPPLIER_ID = UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")


def _user_client(handler):
    return UserServiceClient("http://user-service:8080", transport=httpx.MockTransport(handler))


def _supplier_client(handler):
    return SupplierServiceClient(
        "http://supplier-service:8080", transport=httpx.MockTransport(handler)
    )


def test_user_client_returns_an_active_identity():
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/users/me"
        assert request.headers["authorization"] == "Bearer session-token"
        return httpx.Response(
            200,
            json={
                "id": USER_ID,
                "role": "admin",
                "status": "active",
                "email": "student@u.nus.edu",
            },
        )

    identity = _user_client(handler).resolve_identity("session-token")

    assert identity.id == UUID(USER_ID)
    assert identity.role == "admin"
    assert identity.status == "active"


def test_user_client_turns_401_and_inactive_profiles_into_invalid_sessions():
    unauthorized = _user_client(lambda _request: httpx.Response(401))
    with pytest.raises(InvalidSessionError):
        unauthorized.resolve_identity("nope")

    inactive = _user_client(
        lambda _request: httpx.Response(
            200, json={"id": USER_ID, "role": "user", "status": "suspended"}
        )
    )
    with pytest.raises(InvalidSessionError):
        inactive.resolve_identity("token")


def test_user_client_hides_upstream_failures():
    for response in (
        lambda _request: httpx.Response(503),
        lambda _request: httpx.Response(200, json={"id": "not-a-uuid"}),
        lambda _request: (_ for _ in ()).throw(httpx.ConnectError("down")),
    ):
        client = _user_client(response)
        with pytest.raises(AuthenticationUnavailableError):
            client.resolve_identity("token")


def test_supplier_client_accepts_only_an_explicit_not_found():
    found = _supplier_client(lambda _request: httpx.Response(200, json={"id": str(SUPPLIER_ID)}))
    missing = _supplier_client(
        lambda _request: httpx.Response(
            404, json={"error": {"code": "SUPPLIER_NOT_FOUND", "message": "Supplier not found."}}
        )
    )
    unmounted = _supplier_client(lambda _request: httpx.Response(404, json={"detail": "Not Found"}))
    broken = _supplier_client(lambda _request: httpx.Response(500))

    assert found.is_active(SUPPLIER_ID) is True
    assert missing.is_active(SUPPLIER_ID) is False
    with pytest.raises(SupplierUnavailableError):
        unmounted.is_active(SUPPLIER_ID)
    with pytest.raises(SupplierUnavailableError):
        broken.is_active(SUPPLIER_ID)
