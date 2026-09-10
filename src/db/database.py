"""
Database configuration for KRYVARACODE AI System Stack.

SQLAlchemy 2.0 style: ``DeclarativeBase``-derived ``Base``, typed sessions,
and an ``init_db()`` helper for local/dev bootstrap (production uses Alembic
migrations).

Both sync and async engines/sessions are provided. FastAPI endpoints can use
either ``get_db`` (sync) or ``async_get_db`` (async) depending on whether they
perform blocking I/O.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator, Generator

from sqlalchemy import create_engine
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool

from src.core.config import settings


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


# ---------------------------------------------------------------------------
# Sync engine (existing behavior, kept for compatibility)
# ---------------------------------------------------------------------------
_is_sqlite = settings.DATABASE_URL.startswith("sqlite")
_engine_args: dict = (
    {"connect_args": {"check_same_thread": False}} if _is_sqlite else {}
)
_is_in_memory_sqlite = _is_sqlite and (
    ":memory:" in settings.DATABASE_URL or settings.DATABASE_URL == "sqlite://"
)
if _is_in_memory_sqlite:
    _engine_args["poolclass"] = StaticPool

engine = create_engine(settings.DATABASE_URL, pool_pre_ping=True, **_engine_args)

SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine,
    class_=Session,
    expire_on_commit=False,
)


# ---------------------------------------------------------------------------
# Async engine (new - for FastAPI concurrency) - lazy creation
# ---------------------------------------------------------------------------
# Convert postgres:// to postgresql+asyncpg:// for async driver
_async_database_url: str | None = None
_async_engine = None
_AsyncSessionLocal = None


def _get_async_database_url() -> str:
    """Convert sync DATABASE_URL to async variant."""
    url = settings.DATABASE_URL
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+asyncpg://", 1)
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+asyncpg://", 1)
    return url  # sqlite+aiosqlite etc.


def _get_async_engine():
    """Lazily create async engine on first access."""
    global _async_engine, _async_database_url, _AsyncSessionLocal
    if _async_engine is None:
        _async_database_url = _get_async_database_url()
        _async_engine = create_async_engine(
            _async_database_url,
            pool_pre_ping=True,
            **_engine_args,
        )
        _AsyncSessionLocal = async_sessionmaker(
            autocommit=False,
            autoflush=False,
            bind=_async_engine,
            class_=AsyncSession,
            expire_on_commit=False,
        )
    return _async_engine


def _get_async_session_local():
    """Lazily get async session factory."""
    _get_async_engine()
    return _AsyncSessionLocal


# Exported async engine/session (lazy property)
class _AsyncEngineProxy:
    """Proxy that lazily initializes the async engine on first attribute access."""

    def __getattr__(self, name):
        return getattr(_get_async_engine(), name)


class _AsyncSessionLocalProxy:
    """Proxy that lazily initializes the async session factory."""

    def __call__(self, *args, **kwargs):
        return _get_async_session_local()(*args, **kwargs)

    def __getattr__(self, name):
        return getattr(_get_async_session_local(), name)


async_engine = _AsyncEngineProxy()  # type: ignore[assignment]
AsyncSessionLocal = _AsyncSessionLocalProxy()  # type: ignore[assignment]


def init_db() -> None:
    """Create all tables. Intended for local dev / tests only.

    Production deployments must use Alembic migrations instead.
    """
    # Import models so they register on Base.metadata before create_all.
    from src.db import models  # noqa: F401

    Base.metadata.create_all(bind=engine)


async def async_init_db() -> None:
    """Async version of init_db for async contexts."""
    from src.db import models  # noqa: F401

    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency: yields a SYNC DB session, always closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


async def async_get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency: yields an ASYNC DB session, always closes it."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()


@asynccontextmanager
async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """Context manager for async sessions outside FastAPI dependencies."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
