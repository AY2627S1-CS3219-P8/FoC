"""Authentication for trusted service-to-service requests."""

import hmac
import os

from fastapi import Header, HTTPException, status


INTERNAL_SERVICE_TOKEN_ENV = "USER_SERVICE_INTERNAL_TOKEN"
INTERNAL_SERVICE_TOKEN_HEADER = "X-Internal-Service-Token"


def require_internal_service(
    service_token: str | None = Header(
        default=None,
        alias=INTERNAL_SERVICE_TOKEN_HEADER,
    ),
) -> None:
    """Require the shared secret used by trusted internal services."""

    expected_token = os.getenv(INTERNAL_SERVICE_TOKEN_ENV)
    if not expected_token:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Internal service authorization is not configured",
        )

    if service_token is None or not hmac.compare_digest(service_token, expected_token):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid internal service credentials",
            headers={"WWW-Authenticate": "Service"},
        )
