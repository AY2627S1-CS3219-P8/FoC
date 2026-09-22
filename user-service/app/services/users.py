"""Business logic for registering user accounts."""

from argon2 import PasswordHasher
from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from app.models import User
from app.schemas import UserCreate


password_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    """Return an Argon2id hash for a plaintext password."""

    return password_hasher.hash(password)


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
    except OperationalError as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail="Database temporarily unavailable") from exc

    if existing:
        raise HTTPException(status_code=409, detail="User already exists")

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
        raise HTTPException(status_code=409, detail="User already exists") from exc
    except OperationalError as exc:
        db.rollback()
        raise HTTPException(status_code=503, detail="Database temporarily unavailable") from exc

    return user
