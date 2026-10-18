"""Create the first User Service administrator from environment variables."""

import logging
import os
from pathlib import Path
import sys

from pydantic import ValidationError

# Support both ``python -m scripts.bootstrap_admin`` (used by Compose) and
# ``python scripts/bootstrap_admin.py`` from the service directory.
if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.db import SessionLocal
from app.schemas import UserCreate
from app.services.bootstrap import BootstrapError, bootstrap_admin


ENVIRONMENT_FIELDS = {
    "nus_student_number": "BOOTSTRAP_ADMIN_NUS_STUDENT_NUMBER",
    "email": "BOOTSTRAP_ADMIN_EMAIL",
    "display_name": "BOOTSTRAP_ADMIN_DISPLAY_NAME",
    "password": "BOOTSTRAP_ADMIN_PASSWORD",
}


class BootstrapConfigurationError(RuntimeError):
    """Raised when bootstrap environment variables are incomplete or invalid."""


def payload_from_environment() -> UserCreate | None:
    """Build the validated administrator payload from process environment.

    All four variables being empty disables the optional bootstrap job. A
    partially configured job fails loudly so a deployment cannot appear to be
    initialized when the administrator was not created.
    """

    raw_values = {
        field: os.getenv(environment_name, "")
        for field, environment_name in ENVIRONMENT_FIELDS.items()
    }
    if not any(value.strip() for value in raw_values.values()):
        return None

    missing = [
        environment_name
        for field, environment_name in ENVIRONMENT_FIELDS.items()
        if not raw_values[field].strip()
    ]
    if missing:
        raise BootstrapConfigurationError(
            "Missing required administrator bootstrap variables: " + ", ".join(missing)
        )

    try:
        # Preserve the password exactly as supplied. The other fields are
        # normalized by UserCreate, including surrounding whitespace.
        values = {
            field: value if field == "password" else value.strip()
            for field, value in raw_values.items()
        }
        return UserCreate(**values)
    except ValidationError as exc:
        raise BootstrapConfigurationError(
            "Administrator bootstrap variables do not satisfy the user account policy"
        ) from exc


def main() -> int:
    """Run the one-shot bootstrap command and return a process exit code."""

    logging.basicConfig(
        level=os.getenv("LOG_LEVEL", "INFO").upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    logger = logging.getLogger(__name__)

    try:
        payload = payload_from_environment()
        if payload is None:
            logger.info("Administrator bootstrap is disabled; no credentials configured")
            return 0

        with SessionLocal() as db:
            created = bootstrap_admin(payload, db)
    except (BootstrapConfigurationError, BootstrapError) as exc:
        logger.error("Administrator bootstrap failed: %s", exc)
        return 1

    if created:
        logger.info("Administrator bootstrap completed")
    else:
        logger.info("Administrator bootstrap already completed; no changes made")
    return 0


if __name__ == "__main__":
    sys.exit(main())
