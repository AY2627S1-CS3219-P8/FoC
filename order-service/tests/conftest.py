"""Shared fixtures and fakes for Order Service tests."""

import os

os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("USER_SERVICE_URL", "http://user-service:8080")
os.environ.setdefault("SUPPLIER_SERVICE_URL", "http://supplier-service:8080")

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.db import Base, get_db
from app.main import app
from tests.helpers import SUPPLIER_ID, FakeSupplierClient, FakeUserClient


@pytest.fixture()
def api():
    """HTTP client with an isolated SQLite database and fake upstream services."""

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    factory = sessionmaker(bind=engine, autocommit=False, autoflush=False)
    Base.metadata.create_all(bind=engine)
    supplier = FakeSupplierClient({SUPPLIER_ID})

    def override_get_db():
        db = factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as client:
        app.state.user_client = FakeUserClient()
        app.state.supplier_client = supplier
        yield {
            "client": client,
            "session_factory": factory,
            "supplier": supplier,
        }
    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)
    engine.dispose()
