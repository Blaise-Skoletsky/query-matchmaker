"""Tests for chat API endpoints."""
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestChatEndpoints:

    @pytest.mark.asyncio
    async def test_list_chatrooms(self, client, mock_api_db, mock_user):
        room = MagicMock()
        room.id = uuid.uuid4()
        room.name = "Test chat"
        room.created_at = datetime.now(timezone.utc)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [room]
        mock_api_db.execute.return_value = mock_result

        response = await client.get("/api/chatrooms")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    @pytest.mark.asyncio
    async def test_get_chatroom(self, client, mock_api_db, mock_user):
        chatroom_id = uuid.uuid4()

        # Mock membership check
        member = MagicMock()
        member_result = MagicMock()
        member_result.scalar_one_or_none.return_value = member

        # Mock chatroom
        chatroom = MagicMock()
        chatroom.id = chatroom_id
        chatroom.name = "Test room"
        chatroom.created_at = datetime.now(timezone.utc)

        member_info = MagicMock()
        member_info.user_id = mock_user.id
        chatroom.members = [member_info]

        mock_user_obj = MagicMock()
        mock_user_obj.id = mock_user.id
        mock_user_obj.display_name = "Test User"

        mock_api_db.execute.return_value = member_result
        mock_api_db.get.side_effect = lambda model, id: chatroom if id == chatroom_id else mock_user_obj
        mock_api_db.refresh = AsyncMock()

        response = await client.get(f"/api/chatrooms/{chatroom_id}")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_get_chatroom_not_member_403(self, client, mock_api_db, mock_user):
        chatroom_id = uuid.uuid4()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None  # Not a member
        mock_api_db.execute.return_value = mock_result

        response = await client.get(f"/api/chatrooms/{chatroom_id}")
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_get_messages(self, client, mock_api_db, mock_user):
        chatroom_id = uuid.uuid4()

        # Mock membership check
        member = MagicMock()
        member_result = MagicMock()
        member_result.scalar_one_or_none.return_value = member

        # Mock messages
        msg = MagicMock()
        msg.id = uuid.uuid4()
        msg.chatroom_id = chatroom_id
        msg.user_id = mock_user.id
        msg.content = "Hello"
        msg.created_at = datetime.now(timezone.utc)
        msg.user = MagicMock()
        msg.user.display_name = "Test User"

        msg_result = MagicMock()
        msg_result.scalars.return_value.all.return_value = [msg]

        mock_api_db.execute.side_effect = [member_result, msg_result]

        response = await client.get(f"/api/chatrooms/{chatroom_id}/messages")
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)

    @pytest.mark.asyncio
    async def test_get_messages_not_member_403(self, client, mock_api_db, mock_user):
        chatroom_id = uuid.uuid4()

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_api_db.execute.return_value = mock_result

        response = await client.get(f"/api/chatrooms/{chatroom_id}/messages")
        assert response.status_code == 403
