"""User schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, EmailStr, Field


class UserBase(BaseModel):
    email: EmailStr
    username: str = Field(min_length=3, max_length=50, pattern=r"^[a-zA-Z0-9_.-]+$")
    full_name: Optional[str] = Field(default=None, max_length=100)


class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=128)


class UserUpdate(BaseModel):
    full_name: Optional[str] = Field(default=None, max_length=100)
    password: Optional[str] = Field(default=None, min_length=8, max_length=128)
    is_verified: Optional[bool] = Field(
        default=None, description="Email verification status"
    )
    failed_login_attempts: Optional[int] = Field(
        default=None, description="Failed login attempts counter"
    )
    lock_until: Optional[datetime] = Field(
        default=None, description="Lockout expiration datetime"
    )
    password_reset_token: Optional[str] = Field(
        default=None, description="Password reset token"
    )
    password_reset_expires: Optional[datetime] = Field(
        default=None, description="Password reset token expiration"
    )


class UserRead(UserBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    is_active: bool
    is_superuser: bool
    created_at: datetime
    updated_at: Optional[datetime] = None
