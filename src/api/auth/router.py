"""
Authentication routes for KRYVARACODE AI System Stack.

Served under ``/auth`` by ``src.api.routes``; the version prefix
(``/api/v1``) is attached by ``src.api.main``.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import APIRouter, Body, Depends, HTTPException, Request, Response, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from src.api.auth.auth import (
    authenticate_user,
    create_access_token,
    create_refresh_token,
    decode_refresh_token,
)
from src.api.deps import get_current_active_user, get_db
from src.core.config import settings
from src.core.exceptions import ConflictError, UnauthorizedError
from src.core.rate_limit import rate_limiter
from src.core.security import hash_reset_token
from src.db import crud, models
from src.schemas import Token, UserCreate, UserRead

router = APIRouter()


def _client_ip(request: Request) -> str:
    """Extract the client IP for per-IP rate limiting."""
    return request.client.host if request.client else "unknown"


def _enforce_auth_rate_limit(client_ip: str) -> None:
    """Reject the request when the per-IP auth budget is exhausted.

    No-op when rate limiting is disabled (``rate_limiter is None``).
    """
    if rate_limiter is not None and not rate_limiter.allow(f"auth:{client_ip}"):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests. Try again shortly.",
            headers={"Retry-After": str(int(rate_limiter.window))},
        )


@router.post("/token", response_model=Token)
def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db),
    request_ip: str = Depends(_client_ip),
) -> Token:
    _enforce_auth_rate_limit(request_ip)
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise UnauthorizedError("Incorrect username or password")

    access_token = create_access_token(subject=str(user.id))

    raw_refresh = create_refresh_token(subject=str(user.id))
    db.add(
        models.RefreshToken(
            token=raw_refresh,
            user_id=user.id,
            expires_at=datetime.now(UTC) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        )
    )
    db.commit()

    return Token(
        access_token=access_token,
        refresh_token=raw_refresh,
        token_type="bearer",
    )


@router.get("/users/me", response_model=UserRead)
def read_users_me(
    current_user: models.User = Depends(get_current_active_user),
) -> models.User:
    """Get the currently authenticated user."""
    return current_user


@router.post("/users/", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(
    user: UserCreate,
    db: Session = Depends(get_db),
    request_ip: str = Depends(_client_ip),
) -> models.User:
    """Register a new user."""
    _enforce_auth_rate_limit(request_ip)
    if crud.get_user_by_email(db, email=user.email):
        raise ConflictError("Email already registered")
    if crud.get_user_by_username(db, username=user.username):
        raise ConflictError("Username already taken")
    return crud.create_user(
        db,
        email=user.email,
        username=user.username,
        password=user.password,
        full_name=user.full_name,
    )


@router.post("/request-reset", status_code=status.HTTP_202_ACCEPTED)
def request_password_reset(
    email: str = Body(...),
    db: Session = Depends(get_db),
    request_ip: str = Depends(_client_ip),
) -> dict[str, Any]:
    """Request a password reset link.

    In a production system, this would send an email with a reset token.
    The token is stored on the user record and is NEVER returned in the
    response; it is delivered out-of-band (email/SMS) only.
    """
    _enforce_auth_rate_limit(request_ip)
    user = crud.get_user_by_email(db, email=email)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User with this email not found",
        )
    # Generate a reset token
    import secrets

    token = secrets.token_urlsafe(32)
    expires = datetime.now(UTC) + timedelta(hours=24)
    crud.update_user(
        db,
        user_id=user.id,
        password_reset_token=token,
        password_reset_expires=expires,
    )
    # Deliberately generic message: no indication of whether the account exists
    return {"message": "If the email exists, a reset link has been sent"}


@router.post("/reset-password", status_code=status.HTTP_200_OK)
def reset_password(
    token: str = Body(...),
    new_password: str = Body(...),
    db: Session = Depends(get_db),
    request_ip: str = Depends(_client_ip),
) -> dict[str, Any]:
    """Reset password with a reset token."""
    _enforce_auth_rate_limit(request_ip)
    # Tokens are stored as SHA-256 digests: compare digests, never plaintext.
    token_hash = hash_reset_token(token)
    user = (
        db.query(models.User)
        .filter(
            models.User.hashed_reset_token == token_hash,
            models.User.password_reset_expires > datetime.now(UTC),
        )
        .first()
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired reset token",
        )
    # Set the new password (rejects reuse of the current password) and
    # invalidate the reset token.
    updated_user = crud.change_password(db, user_id=user.id, new_password=new_password)
    if updated_user is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )
    return {"message": "Password successfully reset"}


@router.get("/me/verify", response_model=dict[str, Any])
def check_verification_status(
    current_user: models.User = Depends(get_current_active_user),
) -> dict[str, Any]:
    """Check the current user's email verification status."""
    return {
        "is_verified": current_user.is_verified,
        "email": current_user.email,
    }


@router.post("/verify-email", status_code=status.HTTP_200_OK)
def verify_email(
    current_user: models.User = Depends(get_current_active_user),
    db: Session = Depends(get_db),
) -> dict[str, Any]:
    """Mark the current user's email as verified."""
    crud.update_user(
        db,
        user_id=current_user.id,
        is_verified=True,
    )
    return {"message": "Email verified successfully", "is_verified": True}


@router.post("/refresh", response_model=Token)
def refresh_tokens(
    refresh_token: str = Body(..., embed=True),
    db: Session = Depends(get_db),
    request_ip: str = Depends(_client_ip),
) -> Token:
    _enforce_auth_rate_limit(request_ip)

    db_token = (
        db.query(models.RefreshToken)
        .filter(
            models.RefreshToken.token == refresh_token,
            ~models.RefreshToken.revoked,
            models.RefreshToken.expires_at > datetime.now(UTC),
        )
        .first()
    )
    if not db_token:
        raise UnauthorizedError("Invalid or expired refresh token")

    payload = decode_refresh_token(refresh_token)
    if not payload or payload.get("sub") != str(db_token.user_id):
        raise UnauthorizedError("Invalid refresh token")

    db_token.revoked = True

    new_access = create_access_token(subject=str(db_token.user_id))
    new_raw_refresh = create_refresh_token(subject=str(db_token.user_id))
    db.add(
        models.RefreshToken(
            token=new_raw_refresh,
            user_id=db_token.user_id,
            expires_at=datetime.now(UTC) + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
        )
    )
    db.commit()

    return Token(
        access_token=new_access,
        refresh_token=new_raw_refresh,
        token_type="bearer",
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def logout(
    refresh_token: str = Body(..., embed=True),
    db: Session = Depends(get_db),
) -> Response:
    db_token = db.query(models.RefreshToken).filter(models.RefreshToken.token == refresh_token).first()
    if db_token:
        db_token.revoked = True
        db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
