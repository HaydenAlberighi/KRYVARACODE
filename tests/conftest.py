import os
import sys
import uuid
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

# Required env vars for Settings (test values)
os.environ.setdefault("DATABASE_URL", "sqlite://")
os.environ.setdefault("SECRET_KEY", "test-secret-key-for-testing-only")
os.environ.setdefault("JWT_SECRET_KEY", "test-jwt-secret-key-for-testing-only")
os.environ.setdefault("MLFLOW_TRACKING_URI", "http://localhost:5000")
os.environ.setdefault("MINIO_ENDPOINT", "localhost:9000")
os.environ.setdefault("MINIO_ACCESS_KEY", "minioadmin")
os.environ.setdefault("MINIO_SECRET_KEY", "minioadmin")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")

# RSA key paths for RS256 JWT testing
_KEYS_DIR = PROJECT_ROOT / "src" / "core" / "keys"
os.environ.setdefault("RSA_PRIVATE_KEY_PATH", str(_KEYS_DIR / "private.pem"))
os.environ.setdefault("RSA_PUBLIC_KEY_PATH", str(_KEYS_DIR / "public.pem"))

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

from src.api.main import app
from src.db import models
from src.db.database import Base


@pytest.fixture(scope="session")
def client():
    with TestClient(app) as c:
        yield c


def _unique_suffix() -> str:
    return uuid.uuid4().hex[:8]


@pytest.fixture()
def user_creds(client):
    suffix = _unique_suffix()
    creds = {
        "email": f"{suffix}@test.dev",
        "username": f"user_{suffix}",
        "password": "Hunter22!",
    }
    r = client.post("/api/v1/auth/users/", json=creds)
    assert r.status_code == 201, r.text
    return creds


@pytest.fixture()
def auth_headers(client, user_creds):
    r = client.post(
        "/api/v1/auth/token",
        data={"username": user_creds["username"], "password": user_creds["password"]},
    )
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture()
def db_session():
    """Provide a database session for tests."""
    from src.db.database import SessionLocal, engine

    models.Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    try:
        yield session
        session.rollback()
    finally:
        session.close()


@pytest.fixture()
def user_factory(db_session):
    """Factory for creating test users."""
    from src.db import crud

    def _create_user(**kwargs):
        defaults = {
            "email": f"{uuid.uuid4().hex[:8]}@test.dev",
            "username": f"user_{uuid.uuid4().hex[:8]}",
            "password": "password123",
        }
        defaults.update(kwargs)
        user = crud.create_user(db_session, **defaults)
        db_session.commit()
        return user

    return _create_user


# =============================================================================
# Async DB Fixtures (SQLAlchemy 2.0 async)
# =============================================================================


@pytest.fixture()
async def async_engine():
    """Create async engine for test session."""
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield engine
    await engine.dispose()


@pytest.fixture()
async def async_db_session(async_engine):
    """Provide an async database session with transaction rollback."""
    async_session = async_sessionmaker(async_engine, expire_on_commit=False)
    async with async_session() as session:
        try:
            yield session
            await session.rollback()
        finally:
            await session.close()


@pytest.fixture()
def async_client(async_db_session):
    """TestClient with async DB session override."""
    from src.api.deps import async_get_db

    async def override_get_db():
        yield async_db_session

    app.dependency_overrides[async_get_db] = override_get_db
    with TestClient(app) as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture()
async def async_user_factory(async_db_session):
    """Factory for creating test users - uses sync CRUD via run_sync."""
    from src.db import crud

    async def _create_user(**kwargs):
        defaults = {
            "email": f"{uuid.uuid4().hex[:8]}@test.dev",
            "username": f"user_{uuid.uuid4().hex[:8]}",
            "password": "password123",
        }
        defaults.update(kwargs)
        # Use run_sync to execute sync CRUD in async context
        return await async_db_session.run_sync(lambda session: crud.create_user(session, **defaults))

    return _create_user
