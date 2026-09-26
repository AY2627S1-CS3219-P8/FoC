"""Profile response composition."""

from app.models import User
from app.schemas import OrderHistoryResponse, UserResponse
from app.services.order_history import get_order_history


def own_profile_response(user: User) -> UserResponse:
    """Build a profile response without fetching data from other services."""

    return UserResponse.model_validate(user)


def order_history_response(user: User) -> OrderHistoryResponse:
    """Build the separate order-history response for the authenticated user."""

    order_history = get_order_history(user.id)
    return OrderHistoryResponse(
        order_history=order_history.items,
        order_history_status=order_history.status,
    )
