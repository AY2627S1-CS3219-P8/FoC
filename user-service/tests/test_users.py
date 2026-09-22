"""Tests for user registration behavior."""

import pytest
from fastapi import HTTPException
from sqlalchemy.exc import IntegrityError, OperationalError

from argon2 import PasswordHasher
from pydantic import ValidationError

from app.schemas import UserCreate
from app.services.users import register_user


class FakeSession:
    """Minimal session double for testing registration without a database."""

    def __init__(self, existing=None, commit_error=None):
        self.existing = existing
        self.commit_error = commit_error
        self.user = None
        self.rollback_called = False

    def scalar(self, _query):
        """Return the configured result for the duplicate lookup."""

        return self.existing

    def add(self, user):
        """Capture the user passed for persistence."""

        self.user = user

    def commit(self):
        """Simulate a successful commit or raise the configured database error."""

        if self.commit_error:
            raise self.commit_error

    def refresh(self, _user):
        """Simulate refreshing the persisted user, including ORM defaults."""

        self.user.role = self.user.role or "user"
        self.user.status = self.user.status or "active"

    def rollback(self):
        """Record that the failed transaction was rolled back."""

        self.rollback_called = True


def make_payload(**overrides):
    """Build a valid registration payload, allowing individual fields to vary."""

    values = {
        "nus_student_number": "A0123456X",
        "email": "student@example.com",
        "display_name": "Student",
        "password": "Password1!",
    }
    values.update(overrides)
    return UserCreate(**values)


def test_register_user_hashes_password_before_persistence():
    """Registration stores an Argon2id hash instead of the plaintext password."""

    password = "Password1!"
    db = FakeSession()
    payload = make_payload(password=password)

    register_user(payload, db)

    assert db.user.password_hash != password
    assert db.user.password_hash.startswith("$argon2id$")
    assert PasswordHasher().verify(db.user.password_hash, password)


def test_register_user_normalizes_fields_and_applies_defaults():
    """Registration stores normalized identity fields and safe account defaults."""

    db = FakeSession()
    payload = make_payload(
        email="STUDENT@EXAMPLE.COM",
        display_name="  Student  ",
        nus_student_number="  A0123456X  ",
    )

    user = register_user(payload, db)

    assert user is db.user
    assert user.email == "student@example.com"
    assert user.nus_student_number == "A0123456X"
    assert user.display_name == "Student"
    assert user.role == "user"
    assert user.status == "active"


@pytest.mark.parametrize(
    "student_number",
    ["123456789", "A12345678", "A1234567", "A1234567!", "B1234567X", "!!!!!!!!!"],
)
def test_user_create_rejects_invalid_student_number_formats(student_number):
    """Registration accepts only the expected NUS student number shape."""

    with pytest.raises(ValidationError):
        make_payload(nus_student_number=student_number)


def test_user_create_normalizes_student_number_case():
    """Student numbers are stored in uppercase for consistent identity matching."""

    payload = make_payload(nus_student_number="a0123456x")

    assert payload.nus_student_number == "A0123456X"


@pytest.mark.parametrize(
    "password",
    ["password", "Password1", "Password!", "12345678!"],
)
def test_user_create_rejects_passwords_that_do_not_meet_policy(password):
    """Passwords must contain letters, numbers, and special characters."""

    with pytest.raises(ValidationError, match="password must contain"):
        make_payload(password=password)


@pytest.mark.parametrize("email", ["not-an-email", "student@", "@example.com"])
def test_user_create_rejects_malformed_email_addresses(email):
    """Registration rejects malformed email addresses."""

    with pytest.raises(ValidationError):
        make_payload(email=email)


def test_register_user_trims_trailing_whitespace_from_identity_fields():
    """Registration does not persist trailing whitespace in identity fields."""

    db = FakeSession()
    payload = make_payload(
        nus_student_number="A0123456X   ",
        email="student@example.com   ",
        display_name="Student   ",
    )

    register_user(payload, db)

    assert db.user.nus_student_number == "A0123456X"
    assert db.user.email == "student@example.com"
    assert db.user.display_name == "Student"


def test_register_user_rejects_an_existing_user_before_writing():
    """A duplicate identity returns 409 without adding another user."""

    db = FakeSession(existing=object())

    with pytest.raises(HTTPException) as error:
        register_user(make_payload(), db)

    assert error.value.status_code == 409
    assert error.value.detail == "User already exists"
    assert db.user is None


@pytest.mark.parametrize(
    ("database_error", "status_code", "detail"),
    [
        (
            IntegrityError("INSERT", {}, Exception("duplicate")),
            409,
            "User already exists",
        ),
        (
            OperationalError("INSERT", {}, Exception("database unavailable")),
            503,
            "Database temporarily unavailable",
        ),
    ],
)
def test_register_user_rolls_back_and_maps_database_errors(
    database_error, status_code, detail
):
    """Database failures roll back the transaction and expose safe API errors."""

    db = FakeSession(commit_error=database_error)

    with pytest.raises(HTTPException) as error:
        register_user(make_payload(), db)

    assert db.rollback_called
    assert error.value.status_code == status_code
    assert error.value.detail == detail
