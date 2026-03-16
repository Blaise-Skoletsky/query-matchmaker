"""Fixtures for API endpoint tests."""
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.database import get_db
from app.services.auth import get_current_user


@pytest.fixture
def mock_user():
    user = MagicMock()
    user.id = uuid.uuid4()
    user.email = "test@example.com"
    user.display_name = "Test User"
    user.password_hash = "$2b$12$fakehashfakehashfakehashfakehashfakehashfakehas"
    user.created_at = "2024-01-01T00:00:00+00:00"
    return user


@pytest.fixture
def mock_api_db():
    db = AsyncMock()
    db.commit = AsyncMock()
    db.flush = AsyncMock()
    db.add = MagicMock()
    db.refresh = AsyncMock()
    db.get = AsyncMock(return_value=None)
    return db


@pytest.fixture
async def client(mock_api_db, mock_user):
    from app.main import app

    async def override_get_db():
        yield mock_api_db

    async def override_get_current_user():
        return mock_user

    app.dependency_overrides[get_db] = override_get_db
    app.dependency_overrides[get_current_user] = override_get_current_user

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

    app.dependency_overrides.clear()
