"""Pydantic request and response schemas for user accounts."""

import re
from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator


class UserCreate(BaseModel):
    """Validate the fields required to register a new user."""

    model_config = ConfigDict(extra="forbid")

    nus_student_number: str = Field(min_length=9, max_length=9)
    email: EmailStr
    display_name: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=8, max_length=100)

    @field_validator("nus_student_number", "display_name", mode="before")
    @classmethod
    def non_blank(cls, value: object) -> str:
        """Trim surrounding whitespace and reject blank text values."""

        if not isinstance(value, str):
            raise ValueError("must be a string")
        value = value.strip()
        if not value:
            raise ValueError("must not be blank")
        return value

    @field_validator("nus_student_number")
    @classmethod
    def student_number_format(cls, value: str) -> str:
        """Normalize and validate the NUS student number format."""

        value = value.upper()
        if not re.fullmatch(r"[AU]\d{7}[A-Z]", value):
            raise ValueError("must be a valid NUS student number")
        return value

    @field_validator("password")
    @classmethod
    def password_policy(cls, value: str) -> str:
        """Require a password containing letters, numbers, and symbols."""

        if not re.search(r"[A-Za-z]", value) or not re.search(r"\d", value) or not re.search(
            r"[^A-Za-z0-9]", value
        ):
            raise ValueError("password must contain a letter, number, and special character")
        return value


class UserResponse(BaseModel):
    """Public representation of a user account without authentication data."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    nus_student_number: str
    email: EmailStr
    display_name: str
    role: str
    status: str
    created_at: datetime
    updated_at: datetime
