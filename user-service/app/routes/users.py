"""HTTP routes for user account operations."""

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.auth import AuthContext, get_current_session, revoke_session
from app.db import get_db
from app.schemas import LoginResponse, UserCreate, UserLogin, UserResponse
from app.services.users import login_user, register_user


router = APIRouter()


@router.post("/login", response_model=LoginResponse)
def login(payload: UserLogin, db: Session = Depends(get_db)):
    """Authenticate a user and return a bearer session token."""

    return login_user(payload, db)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    response: Response,
    auth: AuthContext = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """Revoke the current bearer session."""

    revoke_session(auth, db)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.get("/users/me", response_model=UserResponse)
def get_current_user(auth: AuthContext = Depends(get_current_session)):
    """Return the authenticated user's non-sensitive profile fields."""

    return auth.user


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(payload: UserCreate, db: Session = Depends(get_db)):
    """Create and return a newly registered user account."""

    return register_user(payload, db)
