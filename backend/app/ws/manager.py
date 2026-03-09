import asyncio
import json
import uuid
from collections import defaultdict

import redis.asyncio as aioredis
from fastapi import WebSocket

from app.config import settings


class ConnectionManager:
    """
    Event-driven WebSocket manager backed by Redis Pub/Sub.

    Each server process subscribes to `chat:<room_id>` channels for rooms that
    have at least one locally-connected user.  When a message is published (via
    `publish`), Redis fans it out to every server in the cluster; each server
    then delivers it to its own local WebSocket connections for that room.
    """

    def __init__(self):
        # room_id -> [(user_id, WebSocket)]  — local connections only
        self._local: dict[uuid.UUID, list[tuple[uuid.UUID, WebSocket]]] = defaultdict(list)
        self._redis: aioredis.Redis | None = None
        self._pubsub: aioredis.client.PubSub | None = None
        self._listener_task: asyncio.Task | None = None

    async def startup(self):
        self._redis = aioredis.from_url(settings.redis_url, decode_responses=True)
        self._pubsub = self._redis.pubsub()
        self._listener_task = asyncio.create_task(self._listen())
        print("✓ WebSocket manager started (Redis Pub/Sub listener running)")

    async def shutdown(self):
        if self._listener_task:
            self._listener_task.cancel()
            try:
                await self._listener_task
            except asyncio.CancelledError:
                pass
        if self._pubsub:
            await self._pubsub.aclose()
        if self._redis:
            await self._redis.aclose()

    def _channel(self, room_id: uuid.UUID) -> str:
        return f"chat:{room_id}"

    async def connect(self, room_id: uuid.UUID, user_id: uuid.UUID, ws: WebSocket):
        await ws.accept()
        is_first = not self._local[room_id]
        self._local[room_id].append((user_id, ws))
        if is_first:
            await self._pubsub.subscribe(self._channel(room_id))

    async def disconnect(self, room_id: uuid.UUID, user_id: uuid.UUID):
        self._local[room_id] = [
            (uid, ws) for uid, ws in self._local[room_id] if uid != user_id
        ]
        if not self._local[room_id]:
            del self._local[room_id]
            await self._pubsub.unsubscribe(self._channel(room_id))

    async def publish(self, room_id: uuid.UUID, message: dict):
        """Publish a message to all servers via Redis."""
        await self._redis.publish(self._channel(room_id), json.dumps(message))

    async def _listen(self):
        """Background task: poll Redis for messages and deliver to local WS connections."""
        while True:
            try:
                # No subscriptions yet — wait until a room is connected
                if not self._local:
                    await asyncio.sleep(0.5)
                    continue
                msg = await self._pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=0.5
                )
                if msg is None:
                    await asyncio.sleep(0.05)
                    continue
                if msg["type"] != "message":
                    continue
                try:
                    room_id = uuid.UUID(msg["channel"].split(":", 1)[1])
                    data = json.loads(msg["data"])
                    for _, ws in list(self._local.get(room_id, [])):
                        try:
                            await ws.send_json(data)
                        except Exception:
                            pass
                except (ValueError, json.JSONDecodeError, IndexError) as e:
                    print(f"Error processing Redis message: {e}")
            except asyncio.CancelledError:
                return
            except Exception as e:
                print(f"Redis listener error, reconnecting in 1s: {e}")
                await asyncio.sleep(1)


manager = ConnectionManager()
