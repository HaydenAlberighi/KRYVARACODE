import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from src.db import models


@pytest.mark.asyncio
async def test_async_db_session(async_db_session: AsyncSession):
    """Test that async_db_session fixture works."""
    # Create a test user
    user = models.User(
        email="test@async.dev",
        username="async_user",
        hashed_password="hashed",
    )
    async_db_session.add(user)
    await async_db_session.commit()
    await async_db_session.refresh(user)

    assert user.id is not None
    assert user.email == "test@async.dev"

    # Query it back
    result = await async_db_session.execute(
        select(models.User).where(models.User.username == "async_user")
    )
    found = result.scalar_one_or_none()
    assert found is not None
    assert found.id == user.id

    # Rollback to clean up
    await async_db_session.rollback()


@pytest.mark.asyncio
async def test_async_client(async_client):
    """Test that async_client fixture works with async DB override."""
    response = async_client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_async_user_factory(async_user_factory):
    """Test that async_user_factory fixture works."""
    user = await async_user_factory()
    assert user.id is not None
    assert user.email.endswith("@test.dev")
    assert user.username.startswith("user_")
