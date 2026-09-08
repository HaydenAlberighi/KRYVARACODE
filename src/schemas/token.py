"""Authentication token schemas."""

from __future__ import annotations

from typing import Optional

from pydantic import BaseModel


class Token(BaseModel):
    """OAuth2 token response body."""

    access_token: str
    token_type: str = "bearer"


class TokenPayload(BaseModel):
    """Decoded JWT payload."""

    sub: Optional[str] = None
    exp: Optional[int] = None
