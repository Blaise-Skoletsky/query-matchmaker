"""Tests for content moderation agent (moved from test_agents.py + extended)."""
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.moderation import moderate_query, sweep_unmoderated


class TestModerateQuery:

    @pytest.mark.asyncio
    async def test_safe_query(self):
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
    async def test_flagged_high_confidence_suspended(self):
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
    async def test_low_confidence_not_suspended(self):
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
        assert mock_query.status == "active"

    @pytest.mark.asyncio
    async def test_llm_failure_graceful(self):
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

    @pytest.mark.asyncio
    async def test_boundary_079_not_suspended(self):
        """Flagged with confidence=0.79 should NOT auto-suspend (threshold is 0.8)."""
        mock_db = AsyncMock()
        mock_query = MagicMock()
        mock_query.id = uuid.uuid4()
        mock_query.user_id = uuid.uuid4()
        mock_query.raw_text = "Selling something borderline"
        mock_query.status = "active"

        llm_response = '{"flagged": true, "category": "illegal", "confidence": 0.79, "reason": "Borderline"}'

        with patch("app.agents.moderation._chat", new_callable=AsyncMock, return_value=llm_response):
            log = await moderate_query(mock_db, mock_query)

        assert log.flagged is True
        assert log.auto_action == "none"
        assert mock_query.status == "active"

    @pytest.mark.asyncio
    async def test_boundary_080_suspended(self):
        """Flagged with confidence=0.80 should auto-suspend."""
        mock_db = AsyncMock()
        mock_query = MagicMock()
        mock_query.id = uuid.uuid4()
        mock_query.user_id = uuid.uuid4()
        mock_query.raw_text = "Selling something bad"
        mock_query.status = "active"

        llm_response = '{"flagged": true, "category": "abuse", "confidence": 0.80, "reason": "Abusive content"}'

        with patch("app.agents.moderation._chat", new_callable=AsyncMock, return_value=llm_response):
            log = await moderate_query(mock_db, mock_query)

        assert log.flagged is True
        assert log.auto_action == "suspended"
        assert mock_query.status == "suspended"

    @pytest.mark.asyncio
    async def test_creates_moderation_log(self):
        mock_db = AsyncMock()
        mock_query = MagicMock()
        mock_query.id = uuid.uuid4()
        mock_query.user_id = uuid.uuid4()
        mock_query.raw_text = "Normal query"
        mock_query.status = "active"

        llm_response = '{"flagged": false, "category": "safe", "confidence": 0.9, "reason": "OK"}'

        with patch("app.agents.moderation._chat", new_callable=AsyncMock, return_value=llm_response):
            log = await moderate_query(mock_db, mock_query)

        assert log.query_id == mock_query.id
        assert log.confidence == 0.9
        mock_db.add.assert_called_once()

    @pytest.mark.asyncio
    async def test_notifies_on_suspend(self):
        mock_db = AsyncMock()
        mock_query = MagicMock()
        mock_query.id = uuid.uuid4()
        mock_query.user_id = uuid.uuid4()
        mock_query.raw_text = "Illegal stuff"
        mock_query.status = "active"

        llm_response = '{"flagged": true, "category": "illegal", "confidence": 0.95, "reason": "Illegal"}'

        with patch("app.agents.moderation._chat", new_callable=AsyncMock, return_value=llm_response), \
             patch("app.agents.moderation.notify_moderation", new=AsyncMock()) as mock_notify:
            await moderate_query(mock_db, mock_query)

        mock_notify.assert_called_once()


class TestSweepUnmoderated:

    @pytest.mark.asyncio
    async def test_sweep_processes_batch(self):
        queries = [MagicMock() for _ in range(3)]
        for q in queries:
            q.id = uuid.uuid4()
            q.user_id = uuid.uuid4()
            q.raw_text = "test"
            q.status = "active"

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = queries
        mock_session.execute.return_value = mock_result
        mock_session.commit = AsyncMock()

        llm_response = '{"flagged": false, "category": "safe", "confidence": 0.9, "reason": "OK"}'

        with patch("app.agents.moderation.async_session") as mock_factory, \
             patch("app.agents.moderation._chat", new_callable=AsyncMock, return_value=llm_response):
            mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)
            count = await sweep_unmoderated()

        assert count == 3

    @pytest.mark.asyncio
    async def test_sweep_no_queries(self):
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result
        mock_session.commit = AsyncMock()

        with patch("app.agents.moderation.async_session") as mock_factory:
            mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)
            count = await sweep_unmoderated()

        assert count == 0
