from __future__ import annotations

import hashlib
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import bcrypt
from jose import JWTError, jwt

from src.core.config import settings

_BCRYPT_MAX_BYTES = 72

PASSWORD_POLICY: dict[str, Any] = {
    "min_length": 8,
    "max_length": 128,
    "require_digit": True,
    "require_lowercase": True,
    "require_uppercase": True,
    "require_special": True,
    "special_chars": r"""!@#$%^&*()-_=+[]{}|;:'\",.<>?/`~""",
}


def validate_password_policy(password: str) -> list[str]:
    errors: list[str] = []

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
    try:
        return bcrypt.checkpw(
            plain_password.encode("utf-8")[:_BCRYPT_MAX_BYTES],
            hashed_password.encode("utf-8"),
        )
    except (ValueError, TypeError):
        return False


def get_password_hash(password: str) -> str:
    return bcrypt.hashpw(
        password.encode("utf-8")[:_BCRYPT_MAX_BYTES], bcrypt.gensalt()
    ).decode("utf-8")


def hash_reset_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_access_token(
    subject: str,
    expires_delta: timedelta | None = None,
) -> str:
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode: dict[str, Any] = {"sub": subject, "exp": expire, "type": "access"}
    return jwt.encode(
        to_encode, settings.rsa_private_key, algorithm=settings.JWT_ALGORITHM
    )


def decode_access_token(token: str) -> dict[str, Any] | None:
    try:
        payload = jwt.decode(
            token,
            settings.rsa_public_key,
            algorithms=[settings.JWT_ALGORITHM],
        )
        if payload.get("type") != "access":
            return None
        return payload
    except JWTError:
        return None


def create_refresh_token_payload(
    subject: str,
    expires_delta: timedelta | None = None,
) -> dict[str, Any]:
    expire = datetime.now(timezone.utc) + (
        expires_delta or timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    )
    return {
        "sub": subject,
        "exp": expire,
        "type": "refresh",
        "jti": secrets.token_urlsafe(16),
    }


def create_refresh_token(
    subject: str,
    expires_delta: timedelta | None = None,
) -> str:
    payload = create_refresh_token_payload(subject, expires_delta)
    return jwt.encode(
        payload, settings.rsa_private_key, algorithm=settings.JWT_ALGORITHM
    )


def decode_refresh_token(token: str) -> dict[str, Any] | None:
    try:
        payload = jwt.decode(
            token,
            settings.rsa_public_key,
            algorithms=[settings.JWT_ALGORITHM],
        )
        if payload.get("type") != "refresh":
            return None
        return payload
    except JWTError:
        return None
