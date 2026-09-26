"""Integration tests for profile access and lifecycle operations."""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import app
from app.models import User
from app.schemas import UserCreate
from app.services import order_history
from app.services.order_history import OrderHistoryResult
from app.services.users import register_user


@pytest.fixture
def database():
    """Provide an isolated database for profile tests."""

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    with Session(engine) as db:
        yield db
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture
def client(database):
    """Use the isolated database for profile HTTP requests."""

    def override_database():
        yield database

    app.dependency_overrides[get_db] = override_database
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def create_user(database, **overrides) -> User:
    """Create a valid active user for a profile scenario."""

    values = {
        "nus_student_number": "A0123456X",
        "email": "student@example.com",
        "display_name": "Student",
        "password": "Password1!",
    }
    values.update(overrides)
    return register_user(UserCreate(**values), database)


def login(client, student_number="A0123456X", password="Password1!") -> str:
    """Log in and return the bearer token."""

    response = client.post(
        "/login",
        json={"nus_student_number": student_number, "password": password},
    )
    assert response.status_code == 200
    return response.json()["access_token"]


def test_owner_can_view_profile_without_authentication_data(client, database):
    """The owner receives protected profile fields but no credentials."""

    user = create_user(database)
    response = client.get("/users/me", headers={"Authorization": f"Bearer {login(client)}"})

    assert response.status_code == 200
    assert response.json()["nus_student_number"] == user.nus_student_number
    assert response.json()["display_name"] == "Student"
    assert response.json()["order_history"] == []
    assert response.json()["order_history_status"] == "unavailable"
    assert "password_hash" not in response.json()
    assert "access_token" not in response.json()


def test_owner_profile_uses_order_history_provider(client, database, monkeypatch):
    """A configured provider can contribute real history without User storage."""

    class FakeOrderHistoryProvider:
        def get_for_user(self, user_id):
            return OrderHistoryResult(
                status="available",
                items=[{"order_id": "order-1", "status": "delivered"}],
            )

    create_user(database)
    monkeypatch.setattr(order_history, "order_history_provider", FakeOrderHistoryProvider())

    response = client.get("/users/me", headers={"Authorization": f"Bearer {login(client)}"})

    assert response.status_code == 200
    assert response.json()["order_history_status"] == "available"
    assert response.json()["order_history"] == [
        {"order_id": "order-1", "status": "delivered"}
    ]


def test_other_profile_exposes_only_display_name(client, database):
    """A profile lookup for another user returns only the basic profile."""

    create_user(database)
    other = create_user(
        database,
        nus_student_number="A0123457X",
        email="other@example.com",
        display_name="Other Student",
    )
    response = client.get(
        f"/users/{other.id}",
        headers={"Authorization": f"Bearer {login(client)}"},
    )

    assert response.status_code == 200
    assert response.json() == {"display_name": "Other Student"}


def test_owner_can_partially_update_mutable_profile_fields(client, database):
    """Profile updates preserve omitted fields and replace the password hash."""

    user = create_user(database)
    token = login(client)
    response = client.patch(
        "/users/me",
        headers={"Authorization": f"Bearer {token}"},
        json={"display_name": "  Updated Student  ", "email": "NEW@example.com"},
    )

    assert response.status_code == 200
    assert response.json()["display_name"] == "Updated Student"
    assert response.json()["email"] == "new@example.com"
    assert response.json()["nus_student_number"] == user.nus_student_number
    assert user.password_hash

    database.refresh(user)
    assert user.display_name == "Updated Student"
    assert user.email == "new@example.com"
    assert user.nus_student_number == "A0123456X"


def test_empty_profile_update_is_a_no_op(client, database):
    """An empty update returns the current profile without changing it."""

    user = create_user(database)
    response = client.patch(
        "/users/me",
        headers={"Authorization": f"Bearer {login(client)}"},
        json={},
    )

    assert response.status_code == 200
    assert response.json()["id"] == str(user.id)
    assert response.json()["email"] == "student@example.com"
    assert response.json()["display_name"] == "Student"
    database.refresh(user)
    assert user.email == "student@example.com"
    assert user.display_name == "Student"


@pytest.mark.parametrize(
    ("field", "value"),
    [("email", "not-an-email"), ("password", "weak")],
)
def test_profile_update_rejects_invalid_mutable_values(client, database, field, value):
    """Invalid email and password updates do not reach persistence."""

    user = create_user(database)
    original_password_hash = user.password_hash
    response = client.patch(
        "/users/me",
        headers={"Authorization": f"Bearer {login(client)}"},
        json={field: value},
    )

    assert response.status_code == 422
    database.refresh(user)
    assert user.email == "student@example.com"
    assert user.password_hash == original_password_hash


def test_profile_update_supports_put_compatibility_alias(client, database):
    """The PUT compatibility route applies the same profile update contract."""

    user = create_user(database)
    response = client.put(
        "/users/me",
        headers={"Authorization": f"Bearer {login(client)}"},
        json={"display_name": "Updated Student"},
    )

    assert response.status_code == 200
    assert response.json()["display_name"] == "Updated Student"
    database.refresh(user)
    assert user.display_name == "Updated Student"


@pytest.mark.parametrize(
    "display_name",
    ["Updated!", "Alice@NUS", "Alice\\NUS", "Student123", "Student\nName"],
)
def test_profile_update_rejects_display_names_with_unsupported_characters(
    client, database, display_name
):
    """Profile updates reject display names outside the supported English format."""

    create_user(database)
    response = client.patch(
        "/users/me",
        headers={"Authorization": f"Bearer {login(client)}"},
        json={"display_name": display_name},
    )

    assert response.status_code == 422
    assert "display_name contains unsupported" in response.json()["detail"][0]["msg"]


def test_password_update_revokes_existing_session(client, database):
    """Changing a password invalidates the bearer session that made the change."""

    create_user(database)
    token = login(client)
    second_token = login(client)
    response = client.patch(
        "/users/me",
        headers={"Authorization": f"Bearer {token}"},
        json={"password": "NewPassword1!"},
    )

    assert response.status_code == 200
    for revoked_token in (token, second_token):
        assert client.get(
            "/users/me", headers={"Authorization": f"Bearer {revoked_token}"}
        ).status_code == 401
    assert client.post(
        "/login",
        json={"nus_student_number": "A0123456X", "password": "Password1!"},
    ).status_code == 401
    assert client.post(
        "/login",
        json={"nus_student_number": "A0123456X", "password": "NewPassword1!"},
    ).status_code == 200


@pytest.mark.parametrize("field", ["nus_student_number", "role", "status", "created_at"])
def test_profile_update_rejects_protected_fields(client, database, field):
    """UID, account state, role, and timestamps cannot be client-edited."""

    create_user(database)
    response = client.patch(
        "/users/me",
        headers={"Authorization": f"Bearer {login(client)}"},
        json={field: str(uuid4())},
    )

    assert response.status_code == 422


def test_profile_update_rejects_another_user(client, database):
    """A user cannot address a profile update to another account."""

    create_user(database)
    other = create_user(
        database,
        nus_student_number="A0123457X",
        email="other@example.com",
        display_name="Other Student",
    )
    response = client.patch(
        f"/users/{other.id}",
        headers={"Authorization": f"Bearer {login(client)}"},
        json={"display_name": "Should Not Change"},
    )

    assert response.status_code == 403
    database.refresh(other)
    assert other.display_name == "Other Student"


def test_profile_lookup_returns_not_found_for_unknown_user(client, database):
    """Unknown user IDs do not disclose profile data."""

    create_user(database)
    response = client.get(
        f"/users/{uuid4()}",
        headers={"Authorization": f"Bearer {login(client)}"},
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "User not found"}


def test_profile_lookup_hides_deactivated_user(client, database):
    """Deactivated users are not available through basic profile lookup."""

    create_user(database)
    other = create_user(
        database,
        nus_student_number="A0123457X",
        email="other@example.com",
        display_name="Other Student",
    )
    other_token = login(client, student_number="A0123457X")
    deactivated = client.post(
        "/users/me/deactivate",
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert deactivated.status_code == 200

    response = client.get(
        f"/users/{other.id}",
        headers={"Authorization": f"Bearer {login(client)}"},
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "User not found"}


def test_deactivation_preserves_record_and_reactivation_restores_it(client, database):
    """Deactivation is reversible on the same user row."""

    user = create_user(database)
    token = login(client)
    second_token = login(client)
    deactivated = client.post(
        "/users/me/deactivate",
        headers={"Authorization": f"Bearer {token}"},
    )

    assert deactivated.status_code == 200
    assert deactivated.json()["status"] == "deactivated"
    database.expire_all()
    stored = database.scalar(select(User).where(User.id == user.id))
    assert stored is not None
    assert stored.status == "deactivated"

    for revoked_token in (token, second_token):
        blocked = client.get(
            "/users/me", headers={"Authorization": f"Bearer {revoked_token}"}
        )
        assert blocked.status_code == 401

    invalid_reactivation = client.post(
        "/users/reactivate",
        json={"nus_student_number": "A0123456X", "password": "WrongPassword1!"},
    )
    assert invalid_reactivation.status_code == 401
    database.refresh(user)
    assert user.status == "deactivated"

    reactivated = client.post(
        "/users/me/reactivate",
        json={"nus_student_number": "A0123456X", "password": "Password1!"},
    )
    assert reactivated.status_code == 200
    assert reactivated.json()["id"] == str(user.id)
    assert reactivated.json()["status"] == "active"
    assert client.get(
        "/users/me", headers={"Authorization": f"Bearer {token}"}
    ).status_code == 401

    database.expire_all()
    assert database.scalar(select(User).where(User.id == user.id)).status == "active"
