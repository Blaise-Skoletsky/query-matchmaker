"""Tests for app.services.matching — run_matching_pipeline, reverse matching, run_matching_bg.

CRITICAL: The matching pipeline is the core feature and previously had zero coverage.
"""
import uuid
from unittest.mock import AsyncMock, MagicMock, patch, call

import pytest

from app.services.matching import (
    run_matching_pipeline,
    run_reverse_matching,
    run_matching_bg,
    _build_chatroom_name,
)


def _make_query(**kwargs):
    from tests.conftest import _make_query
    return _make_query(**kwargs)


def _make_candidate(raw_text="Selling item", intent="sell", score=0.85, query_id=None):
    q = _make_query(raw_text=raw_text, intent=intent, embedding=[0.1] * 384,
                    complementary_intents=["buy"])
    if query_id:
        q.id = query_id
    return q


class TestRunMatchingPipeline:

    @pytest.mark.asyncio
    async def test_no_intent_returns_early(self, mock_db):
        query = _make_query(raw_text="test", intent=None)
        await run_matching_pipeline(mock_db, query)
        # Should save trace with metadata fail
        mock_db.get.assert_called()

    @pytest.mark.asyncio
    async def test_no_candidates_returns_early(self, mock_db):
        query = _make_query(intent="buy", complementary_intents=["sell"], embedding=[0.1] * 384)

        with patch("app.services.matching.find_candidates", new=AsyncMock(return_value=[])):
            await run_matching_pipeline(mock_db, query)

    @pytest.mark.asyncio
    async def test_llm_exception_returns_early(self, mock_db):
        query = _make_query(intent="buy", complementary_intents=["sell"], embedding=[0.1] * 384)
        candidate = _make_candidate()

        with patch("app.services.matching.find_candidates", new=AsyncMock(return_value=[candidate])), \
             patch("app.services.matching.evaluate_candidates", new=AsyncMock(side_effect=Exception("LLM down"))):
            await run_matching_pipeline(mock_db, query)

    @pytest.mark.asyncio
    async def test_all_below_threshold(self, mock_db):
        query = _make_query(intent="buy", complementary_intents=["sell"], embedding=[0.1] * 384)
        candidate = _make_candidate()

        scores = [{"id": str(candidate.id), "score": 0.3, "reasoning": "Low match"}]

        with patch("app.services.matching.find_candidates", new=AsyncMock(return_value=[candidate])), \
             patch("app.services.matching.evaluate_candidates", new=AsyncMock(return_value=scores)):
            await run_matching_pipeline(mock_db, query)

        # No Match should be added
        add_calls = [c for c in mock_db.add.call_args_list
                     if hasattr(c[0][0], 'compatibility_score')]
        assert len(add_calls) == 0

    @pytest.mark.asyncio
    async def test_above_threshold_creates_match(self, mock_db):
        query = _make_query(intent="buy", complementary_intents=["sell"], embedding=[0.1] * 384)
        candidate = _make_candidate()

        scores = [{"id": str(candidate.id), "score": 0.85, "reasoning": "Great match"}]

        with patch("app.services.matching.find_candidates", new=AsyncMock(return_value=[candidate])), \
             patch("app.services.matching.evaluate_candidates", new=AsyncMock(return_value=scores)), \
             patch("app.services.matching._match_exists", new=AsyncMock(return_value=False)), \
             patch("app.services.matching.notify_match_found", new=AsyncMock()):
            await run_matching_pipeline(mock_db, query)

        # Match + 2 MatchQuery should be added
        assert mock_db.add.call_count >= 3
        assert mock_db.commit.await_count >= 1

    @pytest.mark.asyncio
    async def test_dedup_skips_existing(self, mock_db):
        query = _make_query(intent="buy", complementary_intents=["sell"], embedding=[0.1] * 384)
        candidate = _make_candidate()

        scores = [{"id": str(candidate.id), "score": 0.85, "reasoning": "Match"}]

        with patch("app.services.matching.find_candidates", new=AsyncMock(return_value=[candidate])), \
             patch("app.services.matching.evaluate_candidates", new=AsyncMock(return_value=scores)), \
             patch("app.services.matching._match_exists", new=AsyncMock(return_value=True)), \
             patch("app.services.matching.notify_match_found", new=AsyncMock()) as mock_notify:
            await run_matching_pipeline(mock_db, query)

        mock_notify.assert_not_called()

    @pytest.mark.asyncio
    async def test_saves_trace(self, mock_db):
        query = _make_query(intent="buy", complementary_intents=["sell"], embedding=[0.1] * 384)

        with patch("app.services.matching.find_candidates", new=AsyncMock(return_value=[])):
            await run_matching_pipeline(mock_db, query)

        # _save_trace calls db.get then sets match_trace
        assert mock_db.get.await_count >= 1

    @pytest.mark.asyncio
    async def test_mixed_scores(self, mock_db):
        """3 candidates: one above threshold, two below → 1 Match."""
        query = _make_query(intent="buy", complementary_intents=["sell"], embedding=[0.1] * 384)
        c1 = _make_candidate(raw_text="Good match")
        c2 = _make_candidate(raw_text="Bad match 1")
        c3 = _make_candidate(raw_text="Bad match 2")

        scores = [
            {"id": str(c1.id), "score": 0.9, "reasoning": "Excellent"},
            {"id": str(c2.id), "score": 0.3, "reasoning": "Poor"},
            {"id": str(c3.id), "score": 0.2, "reasoning": "Terrible"},
        ]

        with patch("app.services.matching.find_candidates", new=AsyncMock(return_value=[c1, c2, c3])), \
             patch("app.services.matching.evaluate_candidates", new=AsyncMock(return_value=scores)), \
             patch("app.services.matching._match_exists", new=AsyncMock(return_value=False)), \
             patch("app.services.matching.notify_match_found", new=AsyncMock()) as mock_notify:
            await run_matching_pipeline(mock_db, query)

        # Only 1 match created (c1), so 2 notify calls (both users)
        assert mock_notify.await_count == 2


class TestReverseMatching:

    @pytest.mark.asyncio
    async def test_no_intent_returns_early(self, mock_db):
        query = _make_query(intent=None)
        await run_reverse_matching(mock_db, query)
        mock_db.execute.assert_not_called()

    @pytest.mark.asyncio
    async def test_finds_complementary_queries(self, mock_db):
        new_query = _make_query(intent="buy", complementary_intents=["sell"])
        existing = _make_query(intent="sell", complementary_intents=["buy"])

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [existing]
        mock_db.execute.return_value = mock_result

        with patch("app.services.matching._match_exists", new=AsyncMock(return_value=False)), \
             patch("app.services.matching.run_matching_pipeline", new=AsyncMock()) as mock_pipeline:
            await run_reverse_matching(mock_db, new_query)

        mock_pipeline.assert_called_once_with(mock_db, existing)

    @pytest.mark.asyncio
    async def test_skips_existing_matches(self, mock_db):
        new_query = _make_query(intent="buy", complementary_intents=["sell"])
        existing = _make_query(intent="sell", complementary_intents=["buy"])

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [existing]
        mock_db.execute.return_value = mock_result

        with patch("app.services.matching._match_exists", new=AsyncMock(return_value=True)), \
             patch("app.services.matching.run_matching_pipeline", new=AsyncMock()) as mock_pipeline:
            await run_reverse_matching(mock_db, new_query)

        mock_pipeline.assert_not_called()


class TestRunMatchingBg:

    @pytest.mark.asyncio
    async def test_orchestrates_both_pipelines(self):
        query = _make_query(intent="buy")

        mock_session = AsyncMock()
        mock_session.get = AsyncMock(return_value=query)

        with patch("app.database.async_session") as mock_factory, \
             patch("app.services.matching.run_matching_pipeline", new=AsyncMock()) as mock_fwd, \
             patch("app.services.matching.run_reverse_matching", new=AsyncMock()) as mock_rev:
            mock_factory.return_value.__aenter__ = AsyncMock(return_value=mock_session)
            mock_factory.return_value.__aexit__ = AsyncMock(return_value=False)
            await run_matching_bg(query.id)

        mock_fwd.assert_called_once()
        mock_rev.assert_called_once()


class TestUuidResolution:

    @pytest.mark.asyncio
    async def test_exact_uuid(self, mock_db):
        """_resolve_candidate finds candidate by exact UUID."""
        query = _make_query(intent="buy", complementary_intents=["sell"], embedding=[0.1] * 384)
        candidate = _make_candidate()
        exact_id = str(candidate.id)

        scores = [{"id": exact_id, "score": 0.9, "reasoning": "Match"}]

        with patch("app.services.matching.find_candidates", new=AsyncMock(return_value=[candidate])), \
             patch("app.services.matching.evaluate_candidates", new=AsyncMock(return_value=scores)), \
             patch("app.services.matching._match_exists", new=AsyncMock(return_value=False)), \
             patch("app.services.matching.notify_match_found", new=AsyncMock()):
            await run_matching_pipeline(mock_db, query)

        assert mock_db.add.call_count >= 3

    @pytest.mark.asyncio
    async def test_stripped_uuid(self, mock_db):
        """_resolve_candidate handles UUIDs with quotes/whitespace."""
        query = _make_query(intent="buy", complementary_intents=["sell"], embedding=[0.1] * 384)
        candidate = _make_candidate()
        mangled_id = f'  "{str(candidate.id)}"  '

        scores = [{"id": mangled_id, "score": 0.9, "reasoning": "Match"}]

        with patch("app.services.matching.find_candidates", new=AsyncMock(return_value=[candidate])), \
             patch("app.services.matching.evaluate_candidates", new=AsyncMock(return_value=scores)), \
             patch("app.services.matching._match_exists", new=AsyncMock(return_value=False)), \
             patch("app.services.matching.notify_match_found", new=AsyncMock()):
            await run_matching_pipeline(mock_db, query)

        assert mock_db.add.call_count >= 3
