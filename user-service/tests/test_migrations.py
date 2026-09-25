"""Regression tests for fresh and pre-Alembic database migrations."""

import os
import sqlite3
import subprocess
import sys
from pathlib import Path


SERVICE_DIR = Path(__file__).resolve().parents[1]


def run_alembic_upgrade(database_url: str) -> subprocess.CompletedProcess[str]:
    """Run the same Alembic command used by the deployment migration job."""

    environment = os.environ.copy()
    environment["DATABASE_URL"] = database_url
    return subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=SERVICE_DIR,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )


def test_fresh_database_reaches_migration_head(tmp_path):
    """A new database receives both application tables and the version row."""

    database_path = tmp_path / "fresh.db"
    result = run_alembic_upgrade(f"sqlite:///{database_path}")

    assert result.returncode == 0, result.stderr
    with sqlite3.connect(database_path) as database:
        tables = {
            row[0]
            for row in database.execute(
                "SELECT name FROM sqlite_master WHERE type = 'table'"
            )
        }
        version = database.execute("SELECT version_num FROM alembic_version").fetchone()[0]

    assert {"users", "user_sessions", "alembic_version"} <= tables
    assert version == "20260924_0002"


def test_legacy_create_all_database_is_adopted_without_data_loss(tmp_path):
    """A database created by the previous startup path can be upgraded safely."""

    database_path = tmp_path / "legacy.db"
    database_url = f"sqlite:///{database_path}"
    environment = os.environ.copy()
    environment["DATABASE_URL"] = database_url
    setup = subprocess.run(
        [
            sys.executable,
            "-c",
            """
from app.db import Base, engine
from app.models import User
from sqlalchemy.orm import Session

Base.metadata.create_all(engine)
with Session(engine) as database:
    database.add(User(
        nus_student_number="A0123456X",
        email="student@example.com",
        display_name="Student",
        password_hash="legacy-hash",
    ))
    database.commit()
""",
        ],
        cwd=SERVICE_DIR,
        env=environment,
        capture_output=True,
        text=True,
        check=False,
    )
    assert setup.returncode == 0, setup.stderr

    result = run_alembic_upgrade(database_url)

    assert result.returncode == 0, result.stderr
    with sqlite3.connect(database_path) as database:
        version = database.execute("SELECT version_num FROM alembic_version").fetchone()[0]
        user_count = database.execute("SELECT COUNT(*) FROM users").fetchone()[0]

    assert version == "20260924_0002"
    assert user_count == 1
