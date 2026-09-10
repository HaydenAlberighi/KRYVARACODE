"""User schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserBase(BaseModel):
    email: EmailStr
    username: str = Field(min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_.-]+$")
    full_name: str | None = Field(default=None, max_length=100)


class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=128)


class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, max_length=100)
    password: str | None = Field(default=None, min_length=8, max_length=128)
    is_verified: bool | None = Field(default=None, description="Email verification status")
    failed_login_attempts: int | None = Field(default=None, description="Failed login attempts counter")
    lock_until: datetime | None = Field(default=None, description="Lockout expiration datetime")
    password_reset_token: str | None = Field(default=None, description="Password reset token")
    password_reset_expires: datetime | None = Field(default=None, description="Password reset token expiration")


class UserRead(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    is_active: bool
    is_superuser: bool
    created_at: datetime
    updated_at: datetime | None = None
