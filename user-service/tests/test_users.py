"""Tests for user registration behavior."""

from argon2 import PasswordHasher

from app.schemas import UserCreate
from app.services.users import register_user


class FakeSession:
    """Minimal session double for testing registration without a database."""

    def __init__(self):
        self.user = None

    def scalar(self, _query):
        """Report that no existing user matches the registration request."""

        return None

    def add(self, user):
        """Capture the user passed for persistence."""

        self.user = user

    def commit(self):
        """Simulate a successful transaction commit."""

    def refresh(self, _user):
        """Simulate refreshing the persisted user."""


def test_register_user_hashes_password_before_persistence():
    """Registration stores an Argon2id hash instead of the plaintext password."""

    password = "Password1!"
    db = FakeSession()
    payload = UserCreate(
        nus_student_number="A0123456X",
        email="student@example.com",
        display_name="Student",
        password=password,
    )

    register_user(payload, db)

    assert db.user.password_hash != password
    assert db.user.password_hash.startswith("$argon2id$")
    assert PasswordHasher().verify(db.user.password_hash, password)
