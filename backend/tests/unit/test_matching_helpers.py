"""Tests for matching helper functions: _match_exists, find_candidates, accept_match, _build_chatroom_name."""
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.matching import _build_chatroom_name, accept_match


class TestMatchExists:

    @pytest.mark.asyncio
    async def test_match_exists_true(self, mock_db):
        from app.services.matching import _match_exists

        mock_result = MagicMock()
        mock_result.first.return_value = (uuid.uuid4(),)
        mock_db.execute.return_value = mock_result

        assert await _match_exists(mock_db, uuid.uuid4(), uuid.uuid4()) is True

    @pytest.mark.asyncio
    async def test_match_exists_false(self, mock_db):
        from app.services.matching import _match_exists

        mock_result = MagicMock()
        mock_result.first.return_value = None
        mock_db.execute.return_value = mock_result

        assert await _match_exists(mock_db, uuid.uuid4(), uuid.uuid4()) is False


class TestFindCandidates:

    @pytest.mark.asyncio
    async def test_no_complementary_intents(self, mock_db):
        from app.services.matching import find_candidates
        from tests.conftest import _make_query

        query = _make_query(complementary_intents=None, embedding=[0.1] * 384)
        result = await find_candidates(mock_db, query)
        assert result == []

    @pytest.mark.asyncio
    async def test_no_embedding(self, mock_db):
        from app.services.matching import find_candidates
        from tests.conftest import _make_query

        query = _make_query(complementary_intents=["sell"], embedding=None)
        result = await find_candidates(mock_db, query)
        assert result == []

    @pytest.mark.asyncio
    async def test_returns_results(self, mock_db):
        from app.services.matching import find_candidates
        from tests.conftest import _make_query

        query = _make_query(complementary_intents=["sell"], embedding=[0.1] * 384)
        candidate = _make_query(intent="sell")

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [candidate]
        mock_db.execute.return_value = mock_result

        result = await find_candidates(mock_db, query)
        assert len(result) == 1


class TestAcceptMatch:

    @pytest.mark.asyncio
    async def test_creates_chatroom(self, mock_db):
        match = MagicMock()
        match.id = uuid.uuid4()
        match.status = "pending"
        match.chatroom_id = None
        match.match_queries = []

        with patch("app.services.matching._create_chatroom_for_match", new=AsyncMock(return_value=MagicMock())) as mock_create:
            result = await accept_match(mock_db, match)

        assert match.status == "accepted"
        mock_create.assert_called_once()
        mock_db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_already_has_chatroom(self, mock_db):
        match = MagicMock()
        match.id = uuid.uuid4()
        match.status = "pending"
        match.chatroom_id = uuid.uuid4()

        result = await accept_match(mock_db, match)

        assert match.status == "accepted"
        assert result is None
        mock_db.commit.assert_called_once()


class TestBuildChatroomName:

    def test_empty_list(self):
        assert _build_chatroom_name([]) == "Chat"

    def test_short_text(self):
        assert _build_chatroom_name(["Buy a laptop"]) == "Buy a laptop"

    def test_truncates_long_text(self):
        long_text = "A" * 100
        name = _build_chatroom_name([long_text])
        assert len(name) <= 60
        assert name.endswith("...")

    def test_uses_first_query_only(self):
        result = _build_chatroom_name(["First query", "Second query"])
        assert result == "First query"
