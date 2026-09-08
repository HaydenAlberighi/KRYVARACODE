"""
Authentication routes for KRYVARACODE AI System Stack.

Served under ``/auth`` by ``src.api.routes``; the version prefix
(``/api/v1``) is attached by ``src.api.main``.
"""

from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from src.api.deps import get_current_active_user, get_db
from src.api.auth.auth import authenticate_user, create_access_token
from src.core.config import settings
from src.core.exceptions import ConflictError, UnauthorizedError
from src.db import crud, models
from src.schemas import Token, UserCreate, UserRead

router = APIRouter()


@router.post("/token", response_model=Token)
def login_for_access_token(
    form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)
) -> Token:
    """OAuth2-compatible token login. Exchanges credentials for a JWT."""
    user = authenticate_user(db, form_data.username, form_data.password)
    if not user:
        raise UnauthorizedError("Incorrect username or password")
    access_token_expires = timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        subject=str(user.id), expires_delta=access_token_expires
    )
    return Token(access_token=access_token, token_type="bearer")


@router.get("/users/me", response_model=UserRead)
def read_users_me(
    current_user: models.User = Depends(get_current_active_user),
) -> models.User:
    """Get the currently authenticated user."""
    return current_user


@router.post("/users/", response_model=UserRead, status_code=status.HTTP_201_CREATED)
def create_user(user: UserCreate, db: Session = Depends(get_db)) -> models.User:
    """Register a new user."""
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
