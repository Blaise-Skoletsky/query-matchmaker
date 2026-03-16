"""Tests for app.agents.reprocessing."""
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.reprocessing import run, MAX_RETRIES, RETRY_MIN_AGE_MINUTES


def _make_reprocess_query(match_trace=None, retry_count=0, minutes_old=10):
    q = MagicMock()
    q.id = uuid.uuid4()
    q.status = "active"
    q.embedding = [0.1] * 384
    q.created_at = datetime.now(timezone.utc) - timedelta(minutes=minutes_old)
    trace = match_trace or {}
    if retry_count:
        trace["retry_count"] = retry_count
    q.match_trace = trace if trace else None
    return q


class TestReprocessing:

    @pytest.mark.asyncio
    async def test_finds_queries_without_trace(self):
        query = _make_reprocess_query(match_trace=None)

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [query]
        mock_session.execute.return_value = mock_result
        mock_session.commit = AsyncMock()

        with patch("app.agents.reprocessing.async_session") as mock_factory, \
             patch("app.services.matching.run_matching_pipeline", new=AsyncMock()):
            mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)
            count = await run()

        assert count == 1

    @pytest.mark.asyncio
    async def test_finds_incomplete_trace(self):
        query = _make_reprocess_query(match_trace={"status": "error"})

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [query]
        mock_session.execute.return_value = mock_result
        mock_session.commit = AsyncMock()

        with patch("app.agents.reprocessing.async_session") as mock_factory, \
             patch("app.services.matching.run_matching_pipeline", new=AsyncMock()):
            mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)
            count = await run()

        assert count == 1

    @pytest.mark.asyncio
    async def test_skips_max_retries(self):
        query = _make_reprocess_query(retry_count=MAX_RETRIES)

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [query]
        mock_session.execute.return_value = mock_result
        mock_session.commit = AsyncMock()

        with patch("app.agents.reprocessing.async_session") as mock_factory, \
             patch("app.services.matching.run_matching_pipeline", new=AsyncMock()) as mock_pipeline:
            mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)
            count = await run()

        assert count == 0
        mock_pipeline.assert_not_called()

    @pytest.mark.asyncio
    async def test_increments_retry_count(self):
        query = _make_reprocess_query(match_trace={"status": "error"}, retry_count=1)

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [query]
        mock_session.execute.return_value = mock_result
        mock_session.commit = AsyncMock()

        with patch("app.agents.reprocessing.async_session") as mock_factory, \
             patch("app.services.matching.run_matching_pipeline", new=AsyncMock()):
            mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)
            await run()

        assert query.match_trace["retry_count"] == 2

    @pytest.mark.asyncio
    async def test_handles_pipeline_exception(self):
        query = _make_reprocess_query()

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [query]
        mock_session.execute.return_value = mock_result
        mock_session.commit = AsyncMock()

        with patch("app.agents.reprocessing.async_session") as mock_factory, \
             patch("app.services.matching.run_matching_pipeline", new=AsyncMock(side_effect=Exception("boom"))):
            mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)
            count = await run()

        assert count == 0
        assert "last_error" in query.match_trace

    @pytest.mark.asyncio
    async def test_returns_count(self):
        q1 = _make_reprocess_query()
        q2 = _make_reprocess_query()

        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [q1, q2]
        mock_session.execute.return_value = mock_result
        mock_session.commit = AsyncMock()

        with patch("app.agents.reprocessing.async_session") as mock_factory, \
             patch("app.services.matching.run_matching_pipeline", new=AsyncMock()):
            mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)
            count = await run()

        assert count == 2
