"""
Authentication utilities for KRYVARACODE AI System Stack.

Backwards-compatible facade: re-exports the canonical implementations from
``src.core.security`` (password hashing, JWT) and ``src.api.deps`` (auth
dependencies) so existing imports keep working. New code should import from
those modules directly.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Optional

from sqlalchemy.orm import Session

from src.api.deps import (  # noqa: F401  (re-exported)
    get_current_active_user,
    get_current_user,
    get_db,
    oauth2_scheme,
)
from src.core.security import (  # noqa: F401  (re-exported)
    create_access_token,
    decode_access_token,
    get_password_hash,
    verify_password,
)
from src.db import crud, models


def authenticate_user(
    db: Session, username: str, password: str
) -> Optional[models.User]:
    """Authenticate a user by username + password.

    Returns the user on success, ``None`` on invalid credentials.
    """
    return crud.authenticate_user(db, username, password)
