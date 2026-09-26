"""Profile response composition."""

from app.models import User
from app.schemas import OwnProfileResponse
from app.services.order_history import get_order_history


def own_profile_response(user: User) -> OwnProfileResponse:
    """Build an owner profile while keeping order data outside User storage."""

    order_history = get_order_history(user.id)
    response = OwnProfileResponse.model_validate(user)
    return response.model_copy(
        update={
            "order_history": order_history.items,
            "order_history_status": order_history.status,
        }
    )
