"""
Shared FastAPI dependencies for KRYVARACODE.

Single source of truth for:

- ``get_db`` — DB session dependency
- ``get_current_user`` — JWT-authenticated user
- ``get_current_active_user`` — authenticated + active
- ``get_current_superuser`` — authenticated + active + superuser

All auth flows (doc UI, bearer tokens) point at ``/api/v1/auth/token``.
```

Backwards-compatible re-exports live in ``src.api.auth.auth``.
"""

from __future__ import annotations

from collections.abc import Generator

from fastapi import Depends
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from src.core.config import settings
from src.core.exceptions import ForbiddenError, UnauthorizedError
from src.core.security import decode_access_token
from src.db import models
from src.db.crud import get_user
from src.db.database import SessionLocal, async_get_db

oauth2_scheme = OAuth2PasswordBearer(tokenUrl=f"{settings.API_V1_STR}/auth/token")


def get_db() -> Generator[Session, None, None]:
    """Yield a DB session; always closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: Session = Depends(get_db),
) -> models.User:
    """Resolve the JWT ``sub`` claim to a User, or raise 401."""
    credentials_exc = UnauthorizedError(
        "Could not validate credentials",
        extra={"headers": {"WWW-Authenticate": "Bearer"}},
    )
    payload = decode_access_token(token)
    if payload is None or payload.get("sub") is None:
        raise credentials_exc

    user = get_user(db, user_id=int(payload["sub"]))
    if user is None:
        raise credentials_exc
    return user


async def get_current_user_async(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(async_get_db),
) -> models.User:
    """Async version: resolve the JWT ``sub`` claim to a User."""
    credentials_exc = UnauthorizedError(
        "Could not validate credentials",
        extra={"headers": {"WWW-Authenticate": "Bearer"}},
    )
    payload = decode_access_token(token)
    if payload is None or payload.get("sub") is None:
        raise credentials_exc

    from sqlalchemy import select

    result = await db.execute(select(models.User).where(models.User.id == int(payload["sub"])))
    user = result.scalar_one_or_none()
    if user is None:
        raise credentials_exc
    return user


def get_current_active_user(
    current_user: models.User = Depends(get_current_user),
) -> models.User:
    """Require the authenticated user to be active."""
    if not current_user.is_active:
        raise ForbiddenError("Inactive user")
    return current_user


def get_current_superuser(
    current_user: models.User = Depends(get_current_active_user),
) -> models.User:
    """Require superuser privileges."""
    if not current_user.is_superuser:
        raise ForbiddenError("The user doesn't have enough privileges")
    return current_user
