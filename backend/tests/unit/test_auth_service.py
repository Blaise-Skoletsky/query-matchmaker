"""Tests for app.services.auth."""
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.auth import hash_password, verify_password, create_token, get_current_user


class TestPasswordHashing:

    def test_hash_password_returns_bcrypt(self):
        hashed = hash_password("secret123")
        assert hashed.startswith("$2b$")

    def test_verify_password_correct(self):
        hashed = hash_password("mypassword")
        assert verify_password("mypassword", hashed) is True

    def test_verify_password_incorrect(self):
        hashed = hash_password("mypassword")
        assert verify_password("wrongpassword", hashed) is False


class TestCreateToken:

    def test_create_token_contains_sub(self):
        from jose import jwt
        from app.config import settings
        user_id = uuid.uuid4()
        token = create_token(user_id)
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        assert payload["sub"] == str(user_id)

    def test_create_token_has_expiry(self):
        from jose import jwt
        from app.config import settings
        token = create_token(uuid.uuid4())
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        assert "exp" in payload

    def test_create_token_decodes_correctly(self):
        from jose import jwt
        from app.config import settings
        user_id = uuid.uuid4()
        token = create_token(user_id)
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        assert uuid.UUID(payload["sub"]) == user_id


class TestGetCurrentUser:

    @pytest.mark.asyncio
    async def test_valid_token(self):
        user_id = uuid.uuid4()
        token = create_token(user_id)

        mock_user = MagicMock()
        mock_user.id = user_id

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_db.execute.return_value = mock_result

        credentials = MagicMock()
        credentials.credentials = token

        user = await get_current_user(credentials=credentials, db=mock_db)
        assert user.id == user_id

    @pytest.mark.asyncio
    async def test_invalid_token(self):
        from fastapi import HTTPException

        mock_db = AsyncMock()
        credentials = MagicMock()
        credentials.credentials = "garbage-token"

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(credentials=credentials, db=mock_db)
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_user_not_found(self):
        from fastapi import HTTPException

        user_id = uuid.uuid4()
        token = create_token(user_id)

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute.return_value = mock_result

        credentials = MagicMock()
        credentials.credentials = token

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(credentials=credentials, db=mock_db)
        assert exc_info.value.status_code == 401

    @pytest.mark.asyncio
    async def test_malformed_sub(self):
        from fastapi import HTTPException
        from jose import jwt
        from app.config import settings
        from datetime import datetime, timedelta, timezone

        expire = datetime.now(timezone.utc) + timedelta(minutes=30)
        token = jwt.encode({"sub": "not-a-uuid", "exp": expire}, settings.jwt_secret, algorithm=settings.jwt_algorithm)

        mock_db = AsyncMock()
        credentials = MagicMock()
        credentials.credentials = token

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(credentials=credentials, db=mock_db)
        assert exc_info.value.status_code == 401
