"""Authenticate Order Service requests by asking the User Service."""

from typing import Annotated

from fastapi import Header, HTTPException, Request, status

from app.clients import AuthenticationUnavailableError, Identity, InvalidSessionError


def _unauthorized() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid authentication credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )


def get_current_identity(
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
) -> Identity:
    """Resolve the bearer token. A User Service outage is a 503, not a logout."""

    scheme, _, token = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise _unauthorized()
    try:
        return request.app.state.user_client.resolve_identity(token.strip())
    except InvalidSessionError:
        raise _unauthorized() from None
    except AuthenticationUnavailableError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication temporarily unavailable",
        ) from None
