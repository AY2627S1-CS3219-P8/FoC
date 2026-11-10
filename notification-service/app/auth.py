# AI Assistance Disclosure:
# Tool: Claude Code (model: claude-opus-5-5), date: 2026-11-08
# Scope: Writing implementation code — bearer-token dependency with a case-insensitive scheme, 401 with WWW-Authenticate: Bearer, and 503 when User Service is unavailable, following credit-service/app/auth.py (ai-20261108-001).
# Author review: Keith confirmed on 2026-11-08: full pytest suite with PostgreSQL 16, 790 passed and 5 real-broker tests skipped; code read and verified; manual checks against the full Compose stack with the real User Service (ai-20261108-001).
# Details: notification-service/ai/usage-log.md; ai-20261108-001

"""Bearer-token authentication for Notification Service APIs.

Follows credit-service/app/auth.py.
"""

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
