"""Tests for auth API endpoints."""
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.auth import hash_password, create_token


class TestAuthEndpoints:

    @pytest.mark.asyncio
    async def test_register_success(self, client, mock_api_db):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None  # email not taken
        mock_api_db.execute.return_value = mock_result

        async def mock_refresh(obj):
            obj.id = uuid.uuid4()

        mock_api_db.refresh = mock_refresh

        response = await client.post("/api/auth/register", json={
            "email": "new@example.com",
            "display_name": "New User",
            "password": "password123",
        })
        assert response.status_code == 201
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    @pytest.mark.asyncio
    async def test_register_duplicate_400(self, client, mock_api_db):
        existing_user = MagicMock()
        existing_user.email = "existing@example.com"
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_user
        mock_api_db.execute.return_value = mock_result

        response = await client.post("/api/auth/register", json={
            "email": "existing@example.com",
            "display_name": "Test",
            "password": "password123",
        })
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_login_success(self, client, mock_api_db):
        user = MagicMock()
        user.id = uuid.uuid4()
        user.password_hash = hash_password("correctpassword")
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = user
        mock_api_db.execute.return_value = mock_result

        response = await client.post("/api/auth/login", json={
            "email": "user@example.com",
            "password": "correctpassword",
        })
        assert response.status_code == 200
        assert "access_token" in response.json()

    @pytest.mark.asyncio
    async def test_login_wrong_password_401(self, client, mock_api_db):
        user = MagicMock()
        user.password_hash = hash_password("correctpassword")
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = user
        mock_api_db.execute.return_value = mock_result

        response = await client.post("/api/auth/login", json={
            "email": "user@example.com",
            "password": "wrongpassword",
        })
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_login_no_user_401(self, client, mock_api_db):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_api_db.execute.return_value = mock_result

        response = await client.post("/api/auth/login", json={
            "email": "nobody@example.com",
            "password": "password",
        })
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_me_authenticated(self, client, mock_user):
        response = await client.get("/api/auth/me")
        assert response.status_code == 200
        data = response.json()
        assert data["email"] == mock_user.email

    @pytest.mark.asyncio
    async def test_me_no_token_401(self, mock_api_db):
        """Without auth override, no token should be rejected."""
        from app.main import app
        from httpx import ASGITransport, AsyncClient

        # Clear overrides so real auth is used
        app.dependency_overrides.clear()

        async def override_get_db():
            yield mock_api_db

        app.dependency_overrides[get_db] = override_get_db

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as c:
            response = await c.get("/api/auth/me")

        app.dependency_overrides.clear()
        assert response.status_code in (401, 403)


from app.database import get_db
