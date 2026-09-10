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

import pytest
from fastapi.testclient import TestClient

from src.api.main import app


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
        "password": "hunter22",
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
    from src.db import models
    from src.db.database import SessionLocal, engine

    # Create tables
    models.Base.metadata.create_all(bind=engine)
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
        # Drop tables after test
        models.Base.metadata.drop_all(bind=engine)


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
