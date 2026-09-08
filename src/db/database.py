"""
Database configuration for KRYVARACODE AI System Stack.

SQLAlchemy 2.0 style: ``DeclarativeBase``-derived ``Base``, typed sessions,
and an ``init_db()`` helper for local/dev bootstrap (production uses Alembic
migrations).
"""

from __future__ import annotations

from typing import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker
from sqlalchemy.pool import StaticPool

from src.core.config import settings


class Base(DeclarativeBase):
    """Declarative base for all ORM models."""


# SQLite needs check_same_thread disabled for FastAPI's threadpool.
_is_sqlite = settings.DATABASE_URL.startswith("sqlite")
_engine_args: dict = (
    {"connect_args": {"check_same_thread": False}} if _is_sqlite else {}
)
# In-memory sqlite gives every new connection a fresh empty database; a
# StaticPool keeps a single shared connection so tables survive cross-thread.
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


def init_db() -> None:
    """Create all tables. Intended for local dev / tests only.

    Production deployments must use Alembic migrations instead.
    """
    # Import models so they register on Base.metadata before create_all.
    from src.db import models  # noqa: F401

    Base.metadata.create_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency: yields a DB session, always closes it."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
