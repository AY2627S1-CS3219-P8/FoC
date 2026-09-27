from typing import Literal
from pydantic import AnyHttpUrl, Field, PostgresDsn
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: PostgresDsn

    user_service_url: AnyHttpUrl

    auth_timeout_seconds: float = Field(
        default=3.0,
        gt=0,
        allow_inf_nan=False,
    )

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
