"""Tests for the background agents."""
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
        """Queries with expires_at in the past should be marked expired."""
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
        """Queries older than max_age_days with no explicit expiry should expire."""
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
        """When no queries need expiring, returns 0."""
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
# Moderation Agent
# ---------------------------------------------------------------------------

class TestModerationAgent:
    """Tests for content moderation."""

    @pytest.mark.asyncio
    async def test_moderate_safe_query(self):
        from app.agents.moderation import moderate_query

        mock_db = AsyncMock()
        mock_query = MagicMock()
        mock_query.id = uuid.uuid4()
        mock_query.user_id = uuid.uuid4()
        mock_query.raw_text = "Looking to buy a used bicycle in good condition"
        mock_query.status = "active"

        llm_response = '{"flagged": false, "category": "safe", "confidence": 0.95, "reason": "Normal marketplace query"}'

        with patch("app.agents.moderation._chat", new_callable=AsyncMock, return_value=llm_response):
            log = await moderate_query(mock_db, mock_query)

        assert log.flagged is False
        assert log.category == "safe"
        assert mock_query.status == "active"

    @pytest.mark.asyncio
    async def test_moderate_flagged_query(self):
        from app.agents.moderation import moderate_query

        mock_db = AsyncMock()
        mock_query = MagicMock()
        mock_query.id = uuid.uuid4()
        mock_query.user_id = uuid.uuid4()
        mock_query.raw_text = "Selling illegal substances"
        mock_query.status = "active"

        llm_response = '{"flagged": true, "category": "illegal", "confidence": 0.95, "reason": "References illegal goods"}'

        with patch("app.agents.moderation._chat", new_callable=AsyncMock, return_value=llm_response):
            log = await moderate_query(mock_db, mock_query)

        assert log.flagged is True
        assert log.auto_action == "suspended"
        assert mock_query.status == "suspended"

    @pytest.mark.asyncio
    async def test_moderate_low_confidence_not_suspended(self):
        """Flagged but low confidence should not auto-suspend."""
        from app.agents.moderation import moderate_query

        mock_db = AsyncMock()
        mock_query = MagicMock()
        mock_query.id = uuid.uuid4()
        mock_query.user_id = uuid.uuid4()
        mock_query.raw_text = "Selling kitchen knives"
        mock_query.status = "active"

        llm_response = '{"flagged": true, "category": "illegal", "confidence": 0.4, "reason": "Mentions knives"}'

        with patch("app.agents.moderation._chat", new_callable=AsyncMock, return_value=llm_response):
            log = await moderate_query(mock_db, mock_query)

        assert log.flagged is True
        assert log.auto_action == "none"
        assert mock_query.status == "active"  # Not suspended due to low confidence

    @pytest.mark.asyncio
    async def test_moderate_llm_failure_graceful(self):
        """When LLM call fails, should not flag the query."""
        from app.agents.moderation import moderate_query

        mock_db = AsyncMock()
        mock_query = MagicMock()
        mock_query.id = uuid.uuid4()
        mock_query.user_id = uuid.uuid4()
        mock_query.raw_text = "Buying a laptop"
        mock_query.status = "active"

        with patch("app.agents.moderation._chat", new_callable=AsyncMock, side_effect=Exception("LLM down")):
            log = await moderate_query(mock_db, mock_query)

        assert log.flagged is False
        assert mock_query.status == "active"


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
        # After stop, task should be cancelled
        assert scheduler._agents[0].task.cancelled() or scheduler._agents[0].task.done()


# ---------------------------------------------------------------------------
# Recommendations Agent
# ---------------------------------------------------------------------------

class TestRecommendationsAgent:
    """Tests for recommendation logic."""

    @pytest.mark.asyncio
    async def test_get_trending_categories_empty(self):
        from app.agents.recommendations import get_trending_categories

        mock_db = AsyncMock()
        mock_result = MagicMock()
        mock_result.all.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await get_trending_categories(mock_db, limit=10)
        assert result == []

    @pytest.mark.asyncio
    async def test_get_high_demand_identifies_imbalances(self):
        from app.agents.recommendations import get_high_demand_queries

        mock_db = AsyncMock()
        mock_result = MagicMock()
        # 10 buyers, 2 sellers in electronics
        mock_result.all.return_value = [
            ("electronics", "buy", 10),
            ("electronics", "sell", 2),
        ]
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await get_high_demand_queries(mock_db, limit=5)
        assert len(result) == 1
        assert result[0]["category"] == "electronics"
        assert result[0]["needed_intent"] == "sell"
        assert result[0]["gap"] == 8
