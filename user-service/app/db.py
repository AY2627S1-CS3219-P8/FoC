"""Database engine, ORM base, and request-scoped session helpers."""

import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./user-service.db")

engine_kwargs = {"pool_pre_ping": True}
if DATABASE_URL.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}

engine = create_engine(DATABASE_URL, **engine_kwargs)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


class Base(DeclarativeBase):
    """Base class for SQLAlchemy ORM models."""

    pass


def get_db():
    """Yield a database session and close it after the request completes."""

    db: Session = SessionLocal()
    try:
        yield db
    finally:
        db.close()
