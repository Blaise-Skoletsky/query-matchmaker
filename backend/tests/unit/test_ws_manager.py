"""Tests for app.ws.manager.ConnectionManager."""
import uuid
import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.ws.manager import ConnectionManager


@pytest.fixture
def manager():
    mgr = ConnectionManager()
    mgr._redis = AsyncMock()
    mgr._pubsub = AsyncMock()
    return mgr


class TestConnectionManager:

    @pytest.mark.asyncio
    async def test_connect_accepts_and_subscribes(self, manager):
        room_id = uuid.uuid4()
        user_id = uuid.uuid4()
        ws = AsyncMock()

        await manager.connect(room_id, user_id, ws)

        ws.accept.assert_called_once()
        manager._pubsub.subscribe.assert_called_once_with(f"chat:{room_id}")
        assert len(manager._local[room_id]) == 1

    @pytest.mark.asyncio
    async def test_connect_second_no_resubscribe(self, manager):
        room_id = uuid.uuid4()
        ws1 = AsyncMock()
        ws2 = AsyncMock()

        await manager.connect(room_id, uuid.uuid4(), ws1)
        await manager.connect(room_id, uuid.uuid4(), ws2)

        # Only subscribed once (on first connect)
        assert manager._pubsub.subscribe.call_count == 1
        assert len(manager._local[room_id]) == 2

    @pytest.mark.asyncio
    async def test_disconnect_removes(self, manager):
        room_id = uuid.uuid4()
        user_id = uuid.uuid4()
        ws = AsyncMock()

        await manager.connect(room_id, user_id, ws)
        await manager.disconnect(room_id, user_id)

        assert room_id not in manager._local

    @pytest.mark.asyncio
    async def test_disconnect_last_unsubscribes(self, manager):
        room_id = uuid.uuid4()
        user_id = uuid.uuid4()
        ws = AsyncMock()

        await manager.connect(room_id, user_id, ws)
        await manager.disconnect(room_id, user_id)

        manager._pubsub.unsubscribe.assert_called_once_with(f"chat:{room_id}")

    @pytest.mark.asyncio
    async def test_publish_sends_to_redis(self, manager):
        room_id = uuid.uuid4()
        message = {"text": "hello"}

        await manager.publish(room_id, message)

        manager._redis.publish.assert_called_once_with(
            f"chat:{room_id}",
            json.dumps(message),
        )
