"""Versioned User Service event construction and serialization."""

import json
from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.messaging import USER_CREATED_EVENT
from app.models import User, UserOutboxEvent, utc_now

SCHEMA_VERSION = 1


def isoformat_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def enqueue_user_created(
    db: Session, user: User, *, correlation_id: UUID | None = None
) -> UserOutboxEvent:
    """Stage `user.created` in the caller's account-creation transaction."""

    if user.id is None:
        raise ValueError("The user must have an identifier before staging its event")
    event = UserOutboxEvent(
        event_id=uuid4(),
        event_type=USER_CREATED_EVENT,
        schema_version=SCHEMA_VERSION,
        occurred_at=utc_now(),
        correlation_id=correlation_id or uuid4(),
        user_id=user.id,
        payload={
            "user_id": str(user.id),
            "nus_student_number": user.nus_student_number,
        },
    )
    db.add(event)
    return event


def dump_event(event: UserOutboxEvent) -> bytes:
    body = {
        "event_id": str(event.event_id),
        "event_type": event.event_type,
        "schema_version": event.schema_version,
        "occurred_at": isoformat_utc(event.occurred_at),
        "correlation_id": str(event.correlation_id),
        "payload": event.payload,
    }
    return json.dumps(body, separators=(",", ":"), sort_keys=True).encode("utf-8")
