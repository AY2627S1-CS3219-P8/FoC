# AI Assistance Disclosure:
# Tool: Claude Code (model: claude-opus-5-5), date: 2026-11-03
# Scope: Writing implementation code; Debugging assistance — write engine and session construction with bounded PostgreSQL connect and pool timeouts so readiness checks do not block on new connections.
# Author review: Keith confirmed review of all affected changes.
# Details: notification-service/ai/usage-log.md; ai-20261103-001
# Tool: Claude Code (model: claude-opus-5-5), date: 2026-11-04
# Scope: Writing implementation code — pin the PostgreSQL session time zone to UTC through a shared SESSION_OPTIONS connect option so naive timestamps that bypass the models are read as UTC (ai-20261104-001).
# Author review: Keith confirmed that all tests and manual verification were completed and approved, and confirmed rerunning the tests himself, with commands and results unspecified (ai-20261104-001).
# Details: notification-service/ai/usage-log.md; ai-20261104-001

"""SQLAlchemy engine and session construction."""

from collections.abc import Generator

from fastapi import Request
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

# Bound how long a connection attempt may block, so /ready answers quickly
# when the database is unreachable instead of hanging.
CONNECT_TIMEOUT_SECONDS = 3
POOL_TIMEOUT_SECONDS = 3

# Pin the session time zone so that a naive timestamp reaching PostgreSQL
# without going through the models (for example raw SQL) is read as UTC rather
# than the server's local time.
SESSION_TIME_ZONE = "UTC"
# libpq startup options shared by the app engine and Alembic.
SESSION_OPTIONS = f"-c timezone={SESSION_TIME_ZONE}"


class Base(DeclarativeBase):
    """Declarative base for Notification Service tables."""


def make_engine(database_url: str) -> Engine:
    if database_url.startswith("postgresql"):
        return create_engine(
            database_url,
            pool_pre_ping=True,
            pool_timeout=POOL_TIMEOUT_SECONDS,
            connect_args={
                "connect_timeout": CONNECT_TIMEOUT_SECONDS,
                "options": SESSION_OPTIONS,
            },
        )
    return create_engine(database_url, pool_pre_ping=True)


def make_session_factory(engine: Engine) -> sessionmaker[Session]:
    return sessionmaker(bind=engine, expire_on_commit=False)


def get_db(request: Request) -> Generator[Session, None, None]:
    db = request.app.state.session_factory()
    try:
        yield db
    finally:
        db.close()
