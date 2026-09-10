"""
Security primitives for KRYVARACODE: password hashing and JWT handling.

Centralizes cryptography so neither the DB layer nor the auth routers
import from each other (breaking the former crud <-> auth cycle).

Backwards compatible re-exports live in ``src.api.auth.auth``.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import bcrypt
from jose import JWTError, jwt

from src.core.config import settings

_BCRYPT_MAX_BYTES = 72  # bcrypt truncates passwords beyond this length

# Password policy requirements
PASSWORD_POLICY: Dict[str, Any] = {
    "min_length": 8,
    "max_length": 128,
    "require_digit": True,
    "require_lowercase": True,
    "require_uppercase": True,
    "require_special": True,
    "special_chars": r"""!@#$%^&*()-_=+[]{}|;:'\",.<>?/`~""",
}


def validate_password_policy(password: str) -> List[str]:
    """Validate a password against the configured policy.

    Returns a list of error messages for each violated requirement.
    An empty list means the password is valid.
    """
    errors: List[str] = []

    if len(password) < PASSWORD_POLICY["min_length"]:
        errors.append(
            f"Password must be at least {PASSWORD_POLICY['min_length']} characters"
        )
    if len(password) > PASSWORD_POLICY["max_length"]:
        errors.append(
            f"Password must be at most {PASSWORD_POLICY['max_length']} characters"
        )

    if PASSWORD_POLICY["require_digit"] and not any(c.isdigit() for c in password):
        errors.append("Password must contain at least one digit")

    if PASSWORD_POLICY["require_lowercase"] and not any(c.islower() for c in password):
        errors.append("Password must contain at least one lowercase letter")

    if PASSWORD_POLICY["require_uppercase"] and not any(c.isupper() for c in password):
        errors.append("Password must contain at least one uppercase letter")

    if PASSWORD_POLICY["require_special"] and not any(
        c in PASSWORD_POLICY["special_chars"] for c in password
    ):
        errors.append(
            f"Password must contain at least one special character: "
            f"{PASSWORD_POLICY['special_chars']}"
        )

    return errors


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against its bcrypt hash."""
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8")[:_BCRYPT_MAX_BYTES],
            hashed_password.encode("utf-8"),
        )
    except (ValueError, TypeError):
        return False


def get_password_hash(password: str) -> str:
    """Hash a plaintext password with bcrypt."""
    return bcrypt.hashpw(
        password.encode("utf-8")[:_BCRYPT_MAX_BYTES], bcrypt.gensalt()
    ).decode("utf-8")


def create_access_token(
    subject: str,
    expires_delta: Optional[timedelta] = None,
) -> str:
    """Create a signed JWT whose ``sub`` claim identifies the user.

    Uses ``settings.jwt_secret`` (falls back to SECRET_KEY) and
    ``settings.JWT_ALGORITHM``.
    """
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode: Dict[str, Any] = {"sub": subject, "exp": expire}
    return jwt.encode(to_encode, settings.jwt_secret, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> Optional[Dict[str, Any]]:
    """Decode and validate a JWT. Returns the payload, or None if invalid."""
    try:
        return jwt.decode(
            token, settings.jwt_secret, algorithms=[settings.JWT_ALGORITHM]
        )
    except JWTError:
        return None


def refresh_access_token(
    old_token: str,
) -> Optional[str]:
    """Refresh an access token if the refresh is valid.

    Returns a new access token with a fresh expiry, or None if the
    refresh token is invalid or expired.
    """
    payload = decode_access_token(old_token)
    if payload is None:
        return None
    subject: str = payload.get("sub") or ""
    if not subject:
        return None
    # Issue a new access token
    return create_access_token(subject=subject)
