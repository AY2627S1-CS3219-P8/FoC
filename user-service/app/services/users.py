"""Business logic for user registration, authentication, and profiles."""

import secrets
from datetime import datetime, timezone

from argon2 import PasswordHasher
from fastapi import HTTPException
from sqlalchemy import select
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.auth import (
    cleanup_sessions,
    revoke_user_sessions,
    SESSION_ABSOLUTE_LIFETIME,
    SESSION_INACTIVITY,
    hash_session_token,
)
from app.models import User, UserSession
from app.schemas import LoginResponse, UserCreate, UserLogin, UserUpdate


password_hasher = PasswordHasher()

# A valid Argon2id hash makes unknown-user attempts take the same verification
# path as known-user attempts without storing or comparing a plaintext secret.
DUMMY_PASSWORD_HASH = (
    "$argon2id$v=19$m=65536,t=3,p=4$mUztqNYD/jws5nZquc6jLw$"
    "Tm7egvuOlE/k+0RImshXBGISk81vSE39bBUf6Lw837U"
)


def hash_password(password: str) -> str:
    """Return an Argon2id hash for a plaintext password."""

    return password_hasher.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Verify a password while treating malformed hashes as a failed login."""

    try:
        return password_hasher.verify(password_hash, password)
    except (InvalidHashError, VerificationError, VerifyMismatchError):
        return False


def login_user(payload: UserLogin, db: Session) -> LoginResponse:
    """Authenticate a user and create a bounded-lived opaque session token."""

    student_number = payload.nus_student_number.strip().upper()

    try:
        user = db.scalar(select(User).where(User.nus_student_number == student_number))
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail="Database temporarily unavailable") from exc

    password_hash = user.password_hash if user else DUMMY_PASSWORD_HASH
    password_matches = verify_password(payload.password, password_hash)

    if not user or not password_matches or user.status != "active":
        raise HTTPException(status_code=401, detail="Invalid credentials")

    now = datetime.now(timezone.utc)
    raw_token = secrets.token_urlsafe(32)
    session = UserSession(
        user_id=user.id,
        token_hash=hash_session_token(raw_token),
        created_at=now,
        last_activity_at=now,
        expires_at=now + SESSION_INACTIVITY,
        absolute_expires_at=now + SESSION_ABSOLUTE_LIFETIME,
    )

    try:
        cleanup_sessions(db, now=now)
        db.add(session)
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail="Authentication temporarily unavailable") from exc
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail="Database temporarily unavailable") from exc

    return LoginResponse(
        access_token=raw_token,
        expires_in=int(SESSION_INACTIVITY.total_seconds()),
        user=user,
    )


def register_user(payload: UserCreate, db: Session) -> User:
    """Register a user, enforcing uniqueness and securely hashing the password."""

    email = str(payload.email).lower()
    student_number = payload.nus_student_number.strip()

    try:
        existing = db.scalar(
            select(User).where(
                (User.email == email) | (User.nus_student_number == student_number)
            )
        )
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail="Database temporarily unavailable") from exc

    if existing:
        raise HTTPException(status_code=409, detail="Unable to create account")

    user = User(
        nus_student_number=student_number,
        email=email,
        display_name=payload.display_name.strip(),
        password_hash=hash_password(payload.password),
    )

    try:
        db.add(user)
        db.commit()
        db.refresh(user)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Unable to create account") from exc
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail="Database temporarily unavailable") from exc

    return user


def update_user_profile(user: User, payload: UserUpdate, db: Session) -> User:
    """Update only mutable fields on the authenticated user's profile."""

    if payload.email is not None:
        user.email = str(payload.email).strip().lower()
    if payload.display_name is not None:
        user.display_name = payload.display_name.strip()
    if payload.password is not None:
        user.password_hash = hash_password(payload.password)

    # An empty PATCH is a valid no-op and should still return the current
    # profile.  This also avoids an unnecessary write transaction.
    if not payload.model_fields_set:
        return user

    try:
        if payload.password is not None:
            revoke_user_sessions(db, user.id)
        db.commit()
        db.refresh(user)
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="Unable to update profile") from exc
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail="Database temporarily unavailable") from exc

    return user


def get_user_profile(user_id, db: Session) -> User:
    """Return an active user for a basic profile lookup."""

    try:
        user = db.get(User, user_id)
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail="Database temporarily unavailable") from exc

    if user is None or user.status != "active":
        raise HTTPException(status_code=404, detail="User not found")
    return user


def deactivate_user(user: User, db: Session) -> User:
    """Deactivate an account while retaining its persisted profile record."""

    user.status = "deactivated"
    try:
        revoke_user_sessions(db, user.id)
        db.commit()
        db.refresh(user)
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail="Database temporarily unavailable") from exc
    return user


def reactivate_user(payload: UserLogin, db: Session) -> User:
    """Reactivate a deactivated account after verifying its credentials.

    Reactivation is intentionally credential-based because a deactivated
    account cannot use ordinary authenticated operations.  It updates the
    existing row and never creates a second account.
    """

    student_number = payload.nus_student_number.strip().upper()
    try:
        user = db.scalar(select(User).where(User.nus_student_number == student_number))
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail="Database temporarily unavailable") from exc

    password_hash = user.password_hash if user else DUMMY_PASSWORD_HASH
    password_matches = verify_password(payload.password, password_hash)
    if not user or not password_matches or user.status == "suspended":
        raise HTTPException(status_code=401, detail="Invalid credentials")

    user.status = "active"
    try:
        db.commit()
        db.refresh(user)
    except SQLAlchemyError as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail="Database temporarily unavailable") from exc
    return user
