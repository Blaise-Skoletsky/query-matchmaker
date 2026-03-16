"""Tests for the background agents (expiration, notifications, scheduler).

Moderation tests have been moved to unit/test_moderation.py.
"""
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch, MagicMock

import pytest

from app.agents.scheduler import AgentScheduler


# ---------------------------------------------------------------------------
# Expiration Agent
# ---------------------------------------------------------------------------

class TestExpirationAgent:
    """Tests for query expiration logic."""

    @pytest.mark.asyncio
    async def test_expires_queries_past_explicit_deadline(self):
        from app.agents import expiration

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [uuid.uuid4()]

        mock_aged_result = MagicMock()
        mock_aged_result.scalars.return_value.all.return_value = []

        mock_session.execute = AsyncMock(side_effect=[mock_result, mock_aged_result])
        mock_session.commit = AsyncMock()

        with patch("app.agents.expiration.async_session") as mock_factory:
            mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)
            count = await expiration.run()

        assert count == 1

    @pytest.mark.asyncio
    async def test_expires_aged_queries(self):
        from app.agents import expiration

        mock_session = AsyncMock()
        mock_explicit = MagicMock()
        mock_explicit.scalars.return_value.all.return_value = []

        mock_aged = MagicMock()
        mock_aged.scalars.return_value.all.return_value = [uuid.uuid4(), uuid.uuid4()]

        mock_session.execute = AsyncMock(side_effect=[mock_explicit, mock_aged])
        mock_session.commit = AsyncMock()

        with patch("app.agents.expiration.async_session") as mock_factory:
            mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)
            count = await expiration.run(max_age_days=30)

        assert count == 2

    @pytest.mark.asyncio
    async def test_no_expired_queries(self):
        from app.agents import expiration

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []

        mock_session.execute = AsyncMock(return_value=mock_result)
        mock_session.commit = AsyncMock()

        with patch("app.agents.expiration.async_session") as mock_factory:
            mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)
            count = await expiration.run()

        assert count == 0


# ---------------------------------------------------------------------------
# Notification Agent
# ---------------------------------------------------------------------------

class TestNotificationAgent:
    """Tests for notification creation helpers."""

    @pytest.mark.asyncio
    async def test_notify_match_found(self):
        from app.agents.notifications import notify_match_found

        mock_db = AsyncMock()
        user_id = uuid.uuid4()
        match_id = uuid.uuid4()

        await notify_match_found(mock_db, user_id, match_id, "Selling a laptop", 0.85)

        mock_db.add.assert_called_once()
        notification = mock_db.add.call_args[0][0]
        assert notification.user_id == user_id
        assert notification.type == "match_found"
        assert "85%" in notification.body

    @pytest.mark.asyncio
    async def test_notify_match_accepted(self):
        from app.agents.notifications import notify_match_accepted

        mock_db = AsyncMock()
        user_id = uuid.uuid4()
        match_id = uuid.uuid4()
        chatroom_id = uuid.uuid4()

        await notify_match_accepted(mock_db, user_id, match_id, chatroom_id, "Alice")

        notification = mock_db.add.call_args[0][0]
        assert notification.type == "match_accepted"
        assert "Alice" in notification.body

    @pytest.mark.asyncio
    async def test_notify_match_rejected(self):
        from app.agents.notifications import notify_match_rejected

        mock_db = AsyncMock()
        user_id = uuid.uuid4()
        match_id = uuid.uuid4()

        await notify_match_rejected(mock_db, user_id, match_id)

        notification = mock_db.add.call_args[0][0]
        assert notification.type == "match_rejected"

    @pytest.mark.asyncio
    async def test_notify_query_expired(self):
        from app.agents.notifications import notify_query_expired

        mock_db = AsyncMock()
        user_id = uuid.uuid4()
        query_id = uuid.uuid4()

        await notify_query_expired(mock_db, user_id, query_id, "Looking for a roommate")

        notification = mock_db.add.call_args[0][0]
        assert notification.type == "query_expired"
        assert "roommate" in notification.body

    @pytest.mark.asyncio
    async def test_notify_moderation(self):
        from app.agents.notifications import notify_moderation

        mock_db = AsyncMock()
        user_id = uuid.uuid4()
        query_id = uuid.uuid4()

        await notify_moderation(mock_db, user_id, query_id, "Spam detected")

        notification = mock_db.add.call_args[0][0]
        assert notification.type == "moderation"
        assert "Spam" in notification.body


# ---------------------------------------------------------------------------
# Scheduler
# ---------------------------------------------------------------------------

class TestScheduler:
    """Tests for the agent scheduler."""

    def test_register_agent(self):
        scheduler = AgentScheduler()
        scheduler.register("test_agent", AsyncMock(), 60)
        assert len(scheduler._agents) == 1
        assert scheduler._agents[0].name == "test_agent"

    def test_status_before_start(self):
        scheduler = AgentScheduler()
        scheduler.register("test_agent", AsyncMock(), 60)
        status = scheduler.status()
        assert len(status) == 1
        assert status[0]["name"] == "test_agent"
        assert status[0]["running"] is False

    @pytest.mark.asyncio
    async def test_start_and_stop(self):
        scheduler = AgentScheduler()
        mock_fn = AsyncMock()
        scheduler.register("test_agent", mock_fn, 3600)

        await scheduler.start()
        status = scheduler.status()
        assert status[0]["running"] is True

        await scheduler.stop()
        assert scheduler._agents[0].task.cancelled() or scheduler._agents[0].task.done()
