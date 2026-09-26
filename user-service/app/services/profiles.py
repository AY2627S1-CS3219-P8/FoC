"""Profile response composition."""

from uuid import UUID

from app.models import User
from app.schemas import OrderHistoryResponse, UserResponse
from app.services.order_history import get_order_history


def own_profile_response(user: User) -> UserResponse:
    """Build a profile response without fetching data from other services."""

    return UserResponse.model_validate(user)


async def order_history_response(user_id: UUID) -> OrderHistoryResponse:
    """Build the separate order-history response for the authenticated user."""

    order_history = await get_order_history(user_id)
    return OrderHistoryResponse(
        order_history=order_history.items,
        order_history_status=order_history.status,
    )
