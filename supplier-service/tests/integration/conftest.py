import os
from collections.abc import Iterator

import pytest
from sqlalchemy import Engine, create_engine
from sqlalchemy.engine import URL, make_url
from sqlalchemy.exc import ArgumentError

@pytest.fixture(scope="session")
def test_database_url() -> URL:
    raw_url = os.environ.get("TEST_DATABASE_URL")

    if not raw_url or not raw_url.strip():
        pytest.fail("TEST_DATABASE_URL must be explicitly configured", pytrace=False)

    try:
        url = make_url(raw_url)
    except ArgumentError:
        pytest.fail("TEST_DATABASE_URL is not a valid database URL", pytrace=False)

    if url.drivername != "postgresql+psycopg":
        pytest.fail("TEST_DATABASE_URL must use postgresql+psycopg", pytrace=False)

    if not url.database or not url.database.endswith("_test"):
        pytest.fail("url.database should exist and end in '_test'")

    development_url = os.environ.get("DATABASE_URL")
    if development_url:
        try:
            development_database = make_url(development_url).database
        except ArgumentError:
            pytest.fail(
                "Cannot validate database isolation: DATABASE_URL is invalid",
                pytrace=False,
            )

        if url.database == development_database:
            pytest.fail("url.database should not be the same as development_database")

    return url

@pytest.fixture(scope="session")
def test_engine(test_database_url: URL) -> Iterator[Engine]:
    engine = create_engine(test_database_url, pool_pre_ping=True) 

    try:
        yield engine 
    finally:
        engine.dispose() 

