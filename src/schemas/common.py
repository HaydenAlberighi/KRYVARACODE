"""Common request/response schemas shared across API modules."""

from __future__ import annotations

from typing import Any, Generic, List, Optional, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


class Message(BaseModel):
    """Generic message response."""

    detail: str


class ErrorDetail(BaseModel):
    """Uniform error body produced by global exception handlers."""

    detail: str
    error_code: str
    status_code: int
    extra: Optional[dict[str, Any]] = None


class PaginationParams(BaseModel):
    """Query params for list endpoints."""

    skip: int = Field(default=0, ge=0)
    limit: int = Field(default=100, ge=1, le=1000)


class Paginated(BaseModel, Generic[T]):
    """Generic paginated list wrapper."""

    items: List[T]
    total: int
    skip: int
    limit: int
