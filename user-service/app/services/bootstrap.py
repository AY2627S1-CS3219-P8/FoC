"""Database-backed bootstrap operations for the User Service."""

import logging
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.models import ADMIN_STATE_LOCK_NAME, AdminStateLock, User
from app.schemas import UserCreate
from app.services.users import hash_password


logger = logging.getLogger(__name__)


class BootstrapError(RuntimeError):
    """Raised when the administrator bootstrap cannot be completed."""


def bootstrap_admin(payload: UserCreate, db: Session) -> bool:
    """Create the first administrator exactly once.

    The singleton administrator-state row is locked for the entire transaction.
    The completion timestamp is committed with the new account, so concurrent
    bootstrap jobs and later retries both observe the same durable marker.

    Returns ``True`` when this invocation created the administrator and
    ``False`` when bootstrapping had already completed or an administrator was
    already present.
    """

    try:
        lock = db.scalar(
            select(AdminStateLock)
            .where(AdminStateLock.lock_name == ADMIN_STATE_LOCK_NAME)
            .with_for_update()
        )
        if lock is None:
            raise BootstrapError(
                "Administrator state lock is unavailable; run database migrations first"
            )

        if lock.bootstrap_completed_at is not None:
            db.rollback()
            return False

        # A manually-created administrator should also prevent the bootstrap
        # job from creating a second initial administrator. Marking completion
        # makes that protection durable even if the existing admin is later
        # deactivated or has its role revoked.
        existing_admin = db.scalar(
            select(User)
            .where(User.role == "admin")
            .limit(1)
            .with_for_update()
        )
        if existing_admin is not None:
            lock.bootstrap_completed_at = datetime.now(timezone.utc)
            db.commit()
            return False

        existing_identity = db.scalar(
            select(User).where(
                (User.email == str(payload.email).lower())
                | (User.nus_student_number == payload.nus_student_number)
            )
        )
        if existing_identity is not None:
            raise BootstrapError(
                "The bootstrap administrator identity belongs to an existing account"
            )

        user = User(
            nus_student_number=payload.nus_student_number,
            email=str(payload.email).lower(),
            display_name=payload.display_name.strip(),
            password_hash=hash_password(payload.password),
            role="admin",
            status="active",
        )
        db.add(user)
        lock.bootstrap_completed_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(user)
    except BootstrapError:
        db.rollback()
        raise
    except IntegrityError as exc:
        db.rollback()
        raise BootstrapError(
            "The bootstrap administrator identity conflicts with an existing account"
        ) from exc
    except SQLAlchemyError as exc:
        db.rollback()
        raise BootstrapError("The database was unavailable during administrator bootstrap") from exc

    logger.info("administrator_bootstrap_created", extra={"user_id": str(user.id)})
    return True
