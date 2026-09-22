"""HTTP routes for user account operations."""

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.db import get_db
from app.schemas import UserCreate, UserResponse
from app.services.users import register_user


router = APIRouter()


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(payload: UserCreate, db: Session = Depends(get_db)):
    """Create and return a newly registered user account."""

    return register_user(payload, db)
