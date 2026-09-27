"""Tests for trusted service-to-service authorization checks."""

import pytest
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import app
from app.models import ADMIN_STATE_LOCK_NAME, AdminStateLock, User
from app.schemas import UserCreate
from app.services.users import register_user


INTERNAL_TOKEN = "test-internal-service-token"


@pytest.fixture
def database():
    """Provide an isolated database for authorization-check tests."""

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=engine)
    with Session(engine) as db:
        db.add(AdminStateLock(lock_name=ADMIN_STATE_LOCK_NAME))
        db.commit()
        yield db
    Base.metadata.drop_all(bind=engine)
    engine.dispose()


@pytest.fixture
def client(database, monkeypatch):
    """Use the isolated database and internal-service secret."""

    monkeypatch.setenv("USER_SERVICE_INTERNAL_TOKEN", INTERNAL_TOKEN)

    def override_database():
        yield database

    app.dependency_overrides[get_db] = override_database
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def create_user(database, **overrides) -> User:
    """Create a valid account for an authorization-check scenario."""

    values = {
        "nus_student_number": "A0123456X",
        "email": "student@example.com",
        "display_name": "Student",
        "password": "Password1!",
    }
    values.update(overrides)
    return register_user(UserCreate(**values), database)


def test_internal_check_returns_true_only_for_an_active_admin(client, database):
    """Trusted services can check an active admin without receiving a profile."""

    user = create_user(database)
    user.role = "admin"
    database.commit()

    response = client.get(
        f"/internal/users/{user.id}/admin",
        headers={"X-Internal-Service-Token": INTERNAL_TOKEN},
    )

    assert response.status_code == 200
    assert response.json() == {"is_admin": True}


@pytest.mark.parametrize("status", ["deactivated", "suspended"])
def test_internal_check_rejects_inactive_admin(client, database, status):
    """Deactivated and suspended admins cannot authorize other services."""

    user = create_user(database)
    user.role = "admin"
    user.status = status
    database.commit()

    response = client.get(
        f"/internal/users/{user.id}/admin",
        headers={"X-Internal-Service-Token": INTERNAL_TOKEN},
    )

    assert response.status_code == 200
    assert response.json() == {"is_admin": False}


def test_internal_check_returns_false_for_regular_or_unknown_users(client, database):
    """The minimal boolean response does not disclose account existence."""

    user = create_user(database)
    headers = {"X-Internal-Service-Token": INTERNAL_TOKEN}

    regular_response = client.get(f"/internal/users/{user.id}/admin", headers=headers)
    unknown_response = client.get(f"/internal/users/{uuid4()}/admin", headers=headers)

    assert regular_response.status_code == 200
    assert regular_response.json() == {"is_admin": False}
    assert unknown_response.status_code == 200
    assert unknown_response.json() == {"is_admin": False}


@pytest.mark.parametrize(
    "headers",
    [{}, {"X-Internal-Service-Token": "wrong-token"}],
)
def test_internal_check_requires_the_service_token(client, database, headers):
    """User bearer sessions and unauthenticated requests cannot use the endpoint."""

    user = create_user(database)
    response = client.get(f"/internal/users/{user.id}/admin", headers=headers)

    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid internal service credentials"
