"""HTTP routes for user account and profile operations."""

from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy.orm import Session

from app.auth import AuthContext, get_current_session, revoke_session
from app.db import get_db
from app.schemas import (
    BasicProfileResponse,
    LoginResponse,
    OrderHistoryResponse,
    UserCreate,
    UserLogin,
    UserResponse,
    UserUpdate,
)
from app.services.users import (
    deactivate_user,
    get_user_profile,
    login_user,
    reactivate_user,
    register_user,
    update_user_profile,
)
from app.services.profiles import order_history_response, own_profile_response


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
    """Return the authenticated user's profile without order data."""

    return own_profile_response(auth.user)


@router.get("/users/me/order-history", response_model=OrderHistoryResponse)
def get_current_user_order_history(auth: AuthContext = Depends(get_current_session)):
    """Return the authenticated user's order history through its own boundary."""

    return order_history_response(auth.user)


@router.get("/users/{user_id}", response_model=BasicProfileResponse)
def get_user(user_id: UUID, auth: AuthContext = Depends(get_current_session), db: Session = Depends(get_db)):
    """Return only the display name of another active user."""

    user = get_user_profile(user_id, db)
    if user.id == auth.user.id:
        # The owner should use /users/me to receive their complete profile.
        return BasicProfileResponse(display_name=user.display_name)
    return user


@router.patch("/users/me", response_model=UserResponse)
@router.put("/users/me", response_model=UserResponse)
def update_current_user(
    payload: UserUpdate,
    auth: AuthContext = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """Update mutable fields on the authenticated user's profile."""

    user = update_user_profile(auth.user, payload, db)
    return own_profile_response(user)


@router.patch("/users/{user_id}", response_model=UserResponse)
@router.put("/users/{user_id}", response_model=UserResponse)
def update_user(
    user_id: UUID,
    payload: UserUpdate,
    auth: AuthContext = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """Reject updates addressed to another user's profile."""

    if user_id != auth.user.id:
        raise HTTPException(status_code=403, detail="Cannot modify another user's profile")
    user = update_user_profile(auth.user, payload, db)
    return own_profile_response(user)


@router.delete("/users/me", response_model=UserResponse)
@router.post("/users/me/deactivate", response_model=UserResponse)
def deactivate_current_user(
    auth: AuthContext = Depends(get_current_session),
    db: Session = Depends(get_db),
):
    """Deactivate the current account without deleting its profile record."""

    user = deactivate_user(auth.user, db)
    return own_profile_response(user)


@router.post("/users/me/reactivate", response_model=UserResponse)
@router.post("/users/reactivate", response_model=UserResponse)
@router.post("/reactivate", response_model=UserResponse)
def reactivate_current_user(payload: UserLogin, db: Session = Depends(get_db)):
    """Reactivate an account by verifying its existing login credentials."""

    user = reactivate_user(payload, db)
    return own_profile_response(user)


@router.post("/users", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def create_user(payload: UserCreate, db: Session = Depends(get_db)):
    """Create and return a newly registered user account."""

    return register_user(payload, db)
