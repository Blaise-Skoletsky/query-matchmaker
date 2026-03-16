"""Tests for query API endpoints."""
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


class TestQueryEndpoints:

    @pytest.mark.asyncio
    async def test_create_query(self, client, mock_api_db, mock_user):
        async def mock_refresh(obj):
            obj.id = uuid.uuid4()
            obj.raw_text = "Buy a laptop"
            obj.intent = "buy"
            obj.category = "electronics"
            obj.attributes = {}
            obj.complementary_intents = ["sell"]
            obj.location = None
            obj.status = "active"
            obj.created_at = datetime.now(timezone.utc)

        mock_api_db.refresh = mock_refresh

        with patch("app.routers.queries.embed_async", new=AsyncMock(return_value=[0.0] * 384)), \
             patch("app.routers.queries.extract_metadata", new=AsyncMock(return_value={
                 "intent": "buy", "category": "electronics", "attributes": {},
                 "complementary_intents": ["sell"],
                 "required_match_attributes": [], "preferred_match_attributes": [],
             })), \
             patch("app.routers.queries.moderate_query", new=AsyncMock(return_value=MagicMock())), \
             patch("app.routers.queries.run_matching_bg"):
            response = await client.post("/api/queries", json={"raw_text": "Buy a laptop"})

        assert response.status_code == 201
        data = response.json()
        assert data["raw_text"] == "Buy a laptop"

    @pytest.mark.asyncio
    async def test_list_queries(self, client, mock_api_db, mock_user):
        q = MagicMock()
        q.id = uuid.uuid4()
        q.raw_text = "Test"
        q.intent = "buy"
        q.category = "electronics"
        q.attributes = {}
        q.complementary_intents = ["sell"]
        q.location = None
        q.status = "active"
        q.created_at = datetime.now(timezone.utc)

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [q]
        mock_api_db.execute.return_value = mock_result

        response = await client.get("/api/queries")
        assert response.status_code == 200
        assert isinstance(response.json(), list)

    @pytest.mark.asyncio
    async def test_get_query(self, client, mock_api_db, mock_user):
        query_id = uuid.uuid4()
        q = MagicMock()
        q.id = query_id
        q.user_id = mock_user.id
        q.raw_text = "Test query"
        q.intent = "buy"
        q.category = "electronics"
        q.attributes = {}
        q.complementary_intents = ["sell"]
        q.location = None
        q.status = "active"
        q.created_at = datetime.now(timezone.utc)

        mock_api_db.get.return_value = q

        response = await client.get(f"/api/queries/{query_id}")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_get_query_other_user_404(self, client, mock_api_db, mock_user):
        query_id = uuid.uuid4()
        q = MagicMock()
        q.id = query_id
        q.user_id = uuid.uuid4()  # Different user
        mock_api_db.get.return_value = q

        response = await client.get(f"/api/queries/{query_id}")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_get_trace(self, client, mock_api_db, mock_user):
        query_id = uuid.uuid4()
        q = MagicMock()
        q.id = query_id
        q.user_id = mock_user.id
        q.match_trace = {"status": "complete", "steps": []}
        mock_api_db.get.return_value = q

        response = await client.get(f"/api/queries/{query_id}/trace")
        assert response.status_code == 200
        data = response.json()
        assert data["ready"] is True
        assert "trace" in data

    @pytest.mark.asyncio
    async def test_delete_cancels_matches(self, client, mock_api_db, mock_user):
        query_id = uuid.uuid4()
        q = MagicMock()
        q.id = query_id
        q.user_id = mock_user.id
        q.status = "active"
        mock_api_db.get.return_value = q

        mock_match = MagicMock()
        mock_match.status = "pending"
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_match]
        mock_api_db.execute.return_value = mock_result

        response = await client.delete(f"/api/queries/{query_id}")
        assert response.status_code == 204
        assert q.status == "cancelled"
        assert mock_match.status == "cancelled"

    @pytest.mark.asyncio
    async def test_create_moderation_suspends(self, client, mock_api_db, mock_user):
        async def mock_refresh(obj):
            obj.id = uuid.uuid4()
            obj.raw_text = "Bad content"
            obj.intent = "sell"
            obj.category = "illegal"
            obj.attributes = {}
            obj.complementary_intents = ["buy"]
            obj.location = None
            obj.status = "suspended"
            obj.created_at = datetime.now(timezone.utc)

        mock_api_db.refresh = mock_refresh

        async def mock_moderate(db, query):
            query.status = "suspended"
            return MagicMock()

        with patch("app.routers.queries.embed_async", new=AsyncMock(return_value=[0.0] * 384)), \
             patch("app.routers.queries.extract_metadata", new=AsyncMock(return_value={
                 "intent": "sell", "category": "illegal", "attributes": {},
                 "complementary_intents": ["buy"],
                 "required_match_attributes": [], "preferred_match_attributes": [],
             })), \
             patch("app.routers.queries.moderate_query", side_effect=mock_moderate), \
             patch("app.routers.queries.run_matching_bg"):
            response = await client.post("/api/queries", json={"raw_text": "Bad content"})

        assert response.status_code == 201
        assert response.json()["status"] == "suspended"
