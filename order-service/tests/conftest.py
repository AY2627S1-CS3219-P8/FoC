"""SQLite API fixtures. Identity and the supplier directory are stubs."""

from contextlib import asynccontextmanager
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

import app.models  # noqa: F401 - register tables on Base.metadata
from app.clients import Identity, InvalidSessionError
from app.db import Base, make_engine, make_session_factory
from app.main import app


@asynccontextmanager
async def _no_lifespan(_app):
    yield


class Directory:
    """Tokens map to identities. An unknown token is an invalid session."""

    def __init__(self) -> None:
        self._tokens: dict[str, Identity] = {}

    def add(self, role: str = "user") -> tuple[str, Identity]:
        person = Identity(id=uuid4(), role=role, status="active")
        token = str(person.id)
        self._tokens[token] = person
        return token, person

    def resolve_identity(self, token: str) -> Identity:
        try:
            return self._tokens[token]
        except KeyError:
            raise InvalidSessionError from None


class ActiveSuppliers:
    def is_active(self, supplier_id: UUID) -> bool:
        return True


@pytest.fixture
def session_factory():
    engine = make_engine("sqlite://")
    Base.metadata.create_all(engine)
    factory = make_session_factory(engine)
    yield factory
    engine.dispose()


@pytest.fixture
def directory():
    return Directory()


@pytest.fixture
def client(session_factory, directory, monkeypatch):
    monkeypatch.setattr(app.router, "lifespan_context", _no_lifespan)
    app.state.session_factory = session_factory
    app.state.user_client = directory
    app.state.supplier_client = ActiveSuppliers()
    with TestClient(app) as test_client:
        yield test_client
