"""Tests for match API endpoints."""
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


def _make_match_response(mock_user, status="pending", chatroom_id=None):
    """Create a Match mock with match_queries for serialization."""
    match = MagicMock()
    match.id = uuid.uuid4()
    match.status = status
    match.compatibility_score = 0.85
    match.reasoning = "Good match"
    match.chatroom_id = chatroom_id
    match.created_at = datetime.now(timezone.utc)

    # Build match_queries
    mq1 = MagicMock()
    mq1.query = MagicMock()
    mq1.query.id = uuid.uuid4()
    mq1.query.user_id = mock_user.id
    mq1.query.raw_text = "Buy laptop"
    mq1.query.intent = "buy"
    mq1.query.category = "electronics"
    mq1.query.attributes = {}
    mq1.query.complementary_intents = ["sell"]
    mq1.query.location = None
    mq1.query.status = "active"
    mq1.query.created_at = datetime.now(timezone.utc)

    match.match_queries = [mq1]
    return match


class TestMatchEndpoints:

    @pytest.mark.asyncio
    async def test_list_matches(self, client, mock_api_db, mock_user):
        match = _make_match_response(mock_user)

        with patch("app.routers.matches._get_user_matches", new=AsyncMock(return_value=[match])):
            response = await client.get("/api/matches")

        assert response.status_code == 200
        assert isinstance(response.json(), list)

    @pytest.mark.asyncio
    async def test_accept_match(self, client, mock_api_db, mock_user):
        match = _make_match_response(mock_user)
        chatroom = MagicMock()
        chatroom.id = uuid.uuid4()

        with patch("app.routers.matches._load_match_for_user", new=AsyncMock(return_value=match)), \
             patch("app.routers.matches.accept_match", new=AsyncMock(return_value=chatroom)), \
             patch("app.routers.matches.notify_match_accepted", new=AsyncMock()):
            mock_api_db.refresh = AsyncMock()
            response = await client.post(f"/api/matches/{match.id}/accept")

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_accept_not_yours_403(self, client, mock_api_db, mock_user):
        from fastapi import HTTPException

        async def raise_403(*args, **kwargs):
            raise HTTPException(status_code=403, detail="Not your match")

        with patch("app.routers.matches._load_match_for_user", side_effect=raise_403):
            response = await client.post(f"/api/matches/{uuid.uuid4()}/accept")

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_reject_match(self, client, mock_api_db, mock_user):
        match = _make_match_response(mock_user)

        with patch("app.routers.matches._load_match_for_user", new=AsyncMock(return_value=match)), \
             patch("app.routers.matches.notify_match_rejected", new=AsyncMock()):
            response = await client.post(f"/api/matches/{match.id}/reject")

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_match_not_found_404(self, client, mock_api_db, mock_user):
        from fastapi import HTTPException

        async def raise_404(*args, **kwargs):
            raise HTTPException(status_code=404, detail="Match not found")

        with patch("app.routers.matches._load_match_for_user", side_effect=raise_404):
            response = await client.post(f"/api/matches/{uuid.uuid4()}/accept")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_accept_cancelled_query_400(self, client, mock_api_db, mock_user):
        from fastapi import HTTPException

        async def raise_400(*args, **kwargs):
            raise HTTPException(status_code=400, detail="Cannot act on a match from a deleted query")

        with patch("app.routers.matches._load_match_for_user", side_effect=raise_400):
            response = await client.post(f"/api/matches/{uuid.uuid4()}/accept")

        assert response.status_code == 400
