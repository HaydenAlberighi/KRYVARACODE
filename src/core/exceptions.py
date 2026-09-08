"""
Application exception hierarchy for KRYVARACODE.

All domain errors derive from :class:`AppError` so the global exception
handlers in ``src.api.main`` can translate them into a consistent JSON
response shape::

    {"detail": "...", "error_code": "not_found", "status_code": 404}

Routers raise these instead of returning ad-hoc HTTPExceptions, keeping
error semantics centralized and testable.
"""

from __future__ import annotations

from typing import Any, Dict, Optional


class AppError(Exception):
    """Base class for all KRYVARACODE application errors."""

    status_code: int = 500
    error_code: str = "internal_error"

    def __init__(
        self,
        detail: Optional[str] = None,
        error_code: Optional[str] = None,
        *,
        extra: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.detail = detail or self.__class__.__doc__ or self.error_code
        if error_code:
            self.error_code = error_code
        self.extra = extra or {}
        super().__init__(self.detail)

    def to_dict(self) -> Dict[str, Any]:
        payload: Dict[str, Any] = {
            "detail": self.detail,
            "error_code": self.error_code,
            "status_code": self.status_code,
        }
        if self.extra:
            payload["extra"] = self.extra
        return payload


class NotFoundError(AppError):
    """The requested resource does not exist."""

    status_code = 404
    error_code = "not_found"


class ConflictError(AppError):
    """The request conflicts with the current state of the resource."""

    status_code = 409
    error_code = "conflict"


class UnauthorizedError(AppError):
    """Authentication is missing or the credentials are invalid."""

    status_code = 401
    error_code = "unauthorized"


class ForbiddenError(AppError):
    """The authenticated user lacks permission for this action."""

    status_code = 403
    error_code = "forbidden"


class ValidationFailedError(AppError):
    """The request payload failed semantic validation."""

    status_code = 422
    error_code = "validation_failed"


class RateLimitError(AppError):
    """The client exceeded its allowed request rate."""

    status_code = 429
    error_code = "rate_limit_exceeded"


class ServiceUnavailableError(AppError):
    """A downstream dependency (DB, MLflow, MinIO) is unavailable."""

    status_code = 503
    error_code = "service_unavailable"
