from typing import Optional

import re

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator
from backend.app.schemas.user import UserResponse

USERNAME_PATTERN = re.compile(r"^[a-z0-9](?:[a-z0-9._-]{1,22}[a-z0-9])$")
RESERVED_USERNAMES = {"admin", "support", "root"}
PASSWORD_PATTERN = re.compile(r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[^A-Za-z0-9]).+$")


class RegisterRequest(BaseModel):
    email: EmailStr
    username: str = Field(min_length=3, max_length=24)
    # bcrypt operates on at most 72 bytes, hence the upper bound.
    password: str = Field(min_length=12, max_length=72)
    full_name: Optional[str] = Field(default=None, max_length=255)

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        normalized = value.lower()
        if not USERNAME_PATTERN.fullmatch(normalized):
            raise ValueError("Use 3-24 lowercase letters, numbers, dots, underscores, or hyphens; punctuation must be internal.")
        if normalized in RESERVED_USERNAMES:
            raise ValueError("This username is reserved.")
        return normalized

    @field_validator("password")
    @classmethod
    def validate_new_password(cls, value: str) -> str:
        if len(value.encode("utf-8")) > 72:
            raise ValueError("Password must be at most 72 UTF-8 bytes.")
        if not PASSWORD_PATTERN.fullmatch(value):
            raise ValueError("Password must include an uppercase letter, lowercase letter, number, and special character.")
        return value


class LoginRequest(BaseModel):
    identifier: str
    password: str

    @model_validator(mode="before")
    @classmethod
    def accept_legacy_email_field(cls, value):
        if isinstance(value, dict) and "identifier" not in value and "email" in value:
            return {**value, "identifier": value["email"]}
        return value


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str


class LocalSessionRequest(BaseModel):
    request_key: Optional[str] = None


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class LoginResponse(TokenResponse):
    user: UserResponse
