"""KRYVARACODE API application entry point."""

from __future__ import annotations

import logging
import time
import uuid
from contextlib import asynccontextmanager
from typing import Any, Awaitable, Callable, cast

import uvicorn
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from sqlalchemy import text

from src.api.routes import api_router
from src.core.config import settings
from src.core.exceptions import AppError
from src.core.logging import setup_logging
from src.core.metrics import CONTENT_TYPE_LATEST, register_request, render_metrics
from src.core.rate_limit import RateLimitMiddleware, rate_limiter
from src.db.database import engine, init_db

logger = logging.getLogger(__name__)


class RequestIDMiddleware:
    """Assign a request ID, inject it into the response, and log the request."""

    def __init__(self, app: Callable[..., Awaitable[Any]]) -> None:
        self.app = app

    async def __call__(self, scope: Any, receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request_id = uuid.uuid4().hex
        scope["request_id"] = request_id
        start = time.perf_counter()

        async def send_wrapper(message: Any) -> None:
            if message["type"] == "http.response.start":
                headers = list(message.get("headers", []))
                headers.append((b"X-Request-ID", request_id.encode()))
                message["headers"] = headers
                duration_ms = (time.perf_counter() - start) * 1000
                logger.info(
                    "%s %s -> %s (%.1fms) [%s]",
                    scope.get("method"),
                    scope.get("path"),
                    message.get("status"),
                    duration_ms,
                    request_id,
                )
                route = scope.get("route")
                path = getattr(route, "path", None) or str(scope.get("path", ""))
                register_request(
                    str(scope.get("method")),
                    path,
                    int(message.get("status", 0)),
                    duration_ms,
                )
            await send(message)

        await self.app(scope, receive, send_wrapper)


async def app_error_handler(request: Request, exc: Exception) -> JSONResponse:
    _ = request
    app_err = cast(AppError, exc)
    headers = app_err.extra.get("headers") if app_err.extra else None
    return JSONResponse(
        status_code=app_err.status_code,
        content=app_err.to_dict(),
        headers=headers,
    )


async def validation_error_handler(_request: Request, exc: Exception) -> JSONResponse:
    validation_err = cast(RequestValidationError, exc)
    return JSONResponse(
        status_code=422,
        content={
            "detail": validation_err.errors(),
            "error_code": "validation_failed",
            "status_code": 422,
        },
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error",
            "error_code": "internal_error",
            "status_code": 500,
        },
    )


@asynccontextmanager
async def lifespan(_app: FastAPI):
    setup_logging(level=settings.LOG_LEVEL)
    if "sqlite" in settings.DATABASE_URL:
        init_db()
    logger.info("%s v%s starting", settings.APP_NAME, settings.PROJECT_VERSION)
    yield
    logger.info("%s shutting down", settings.APP_NAME)


app = FastAPI(
    title=settings.APP_NAME,
    description="KRYVARACODE AI System Stack API",
    version=settings.PROJECT_VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
    lifespan=lifespan,
)

if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin) for origin in settings.BACKEND_CORS_ORIGINS],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
app.add_middleware(RequestIDMiddleware)
if rate_limiter is not None:
    app.add_middleware(RateLimitMiddleware)

app.add_exception_handler(AppError, app_error_handler)
app.add_exception_handler(RequestValidationError, validation_error_handler)
app.add_exception_handler(Exception, unhandled_exception_handler)

app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/health")
def health_check() -> JSONResponse:
    """Liveness/readiness probe with a real DB round-trip."""
    body: dict[str, Any] = {
        "status": "ok",
        "service": settings.APP_NAME,
        "version": settings.PROJECT_VERSION,
        "database": "ok",
    }
    status_code = 200
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception:
        logger.exception("Health check failed: database unreachable")
        status_code = 503
        body["status"] = "degraded"
        body["database"] = "unavailable"
    return JSONResponse(status_code=status_code, content=body)


@app.get("/")
def root() -> dict[str, str]:
    return {
        "message": f"Welcome to {settings.APP_NAME}",
        "version": settings.PROJECT_VERSION,
        "docs": "/docs",
    }


@app.get(f"{settings.API_V1_STR}/metrics", include_in_schema=False)
def metrics() -> Response:
    """Prometheus exposition endpoint."""
    body = render_metrics()
    if body is None:
        return JSONResponse(
            status_code=503,
            content={
                "detail": "Metrics unavailable: prometheus-client is not installed",
                "error_code": "service_unavailable",
                "status_code": 503,
            },
        )
    return Response(content=body, media_type=CONTENT_TYPE_LATEST)


if __name__ == "__main__":
    uvicorn.run(
        "main:app", host="0.0.0.0", port=settings.PORT, reload=settings.APP_DEBUG
    )
