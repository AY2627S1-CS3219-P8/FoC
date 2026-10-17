"""User Service outbox event contract tests."""

import json
from datetime import datetime, timezone
from uuid import uuid4

from app.events import dump_event, enqueue_user_created
from app.models import User, UserOutboxEvent


class FakeSession:
    def __init__(self):
        self.added = []

    def add(self, value):
        self.added.append(value)


def test_user_created_contains_only_credit_allocation_identity_fields() -> None:
    now = datetime.now(timezone.utc)
    user = User(
        id=uuid4(),
        nus_student_number="A0123456X",
        email="private@example.com",
        display_name="Private Name",
        password_hash="private-hash",
        role="user",
        status="active",
        created_at=now,
        updated_at=now,
    )
    db = FakeSession()

    event = enqueue_user_created(db, user)
    body = json.loads(dump_event(event))

    assert db.added == [event]
    assert isinstance(event, UserOutboxEvent)
    assert body["event_type"] == "user.created"
    assert body["schema_version"] == 1
    assert body["payload"] == {
        "user_id": str(user.id),
        "nus_student_number": "A0123456X",
    }
    assert "email" not in body["payload"]
    assert "password_hash" not in body["payload"]


