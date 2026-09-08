import os
import sys
import uuid
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

os.environ.setdefault("DATABASE_URL", "sqlite://")

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
