"""Tests for tool registry and tool functions (moved from tests/test_tools.py)."""
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.services.tools import (
    execute_tool, search_listings, check_demand,
    get_price_range, count_by_category, check_user_queries,
    TOOL_REGISTRY, get_ollama_tools,
    _category_filter,
)

FAKE_USER_ID = uuid.uuid4()


def _make_query(raw_text="Test item", intent="sell", category="electronics",
                embedding=None, attributes=None, user_id=None):
    q = MagicMock()
    q.raw_text = raw_text
    q.intent = intent
    q.category = category
    q.embedding = embedding
    q.created_at = None
    q.attributes = attributes
    q.user_id = user_id
    return q


@pytest.mark.asyncio
async def test_search_listings_returns_formatted():
    db = AsyncMock()
    q1 = _make_query("Selling MacBook Pro 16 inch", "sell", "electronics")
    q2 = _make_query("Selling iPhone 15", "sell", "electronics")
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [q1, q2]
    db.execute.return_value = mock_result
    result = await search_listings(db, FAKE_USER_ID, category="electronics")
    assert "2 active listing(s)" in result
    assert "MacBook" in result
    assert "iPhone" in result


@pytest.mark.asyncio
async def test_search_listings_empty():
    db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    db.execute.return_value = mock_result
    result = await search_listings(db, FAKE_USER_ID, category="nonexistent")
    assert "No active listings" in result


@pytest.mark.asyncio
async def test_check_demand_balanced():
    db = AsyncMock()
    mock_result = MagicMock()
    mock_result.all.return_value = [("buy", 5), ("sell", 4)]
    db.execute.return_value = mock_result
    result = await check_demand(db, FAKE_USER_ID, category="electronics")
    assert "5 buyer(s)" in result
    assert "balanced" in result.lower()


@pytest.mark.asyncio
async def test_check_demand_high_buyer_demand():
    db = AsyncMock()
    mock_result = MagicMock()
    mock_result.all.return_value = [("buy", 10), ("sell", 2)]
    db.execute.return_value = mock_result
    result = await check_demand(db, FAKE_USER_ID, category="electronics")
    assert "High demand for sellers" in result


@pytest.mark.asyncio
async def test_check_demand_empty():
    db = AsyncMock()
    mock_result = MagicMock()
    mock_result.all.return_value = []
    db.execute.return_value = mock_result
    result = await check_demand(db, FAKE_USER_ID, category="nothing")
    assert "No active listings" in result


@pytest.mark.asyncio
async def test_get_price_range_with_prices():
    db = AsyncMock()
    q1 = _make_query("Selling laptop for $500", "sell", "electronics", attributes={"price": 500})
    q2 = _make_query("iPhone $800 firm", "sell", "electronics", attributes={})
    q3 = _make_query("Budget around $300", "buy", "electronics", attributes={"budget": "300"})
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [q1, q2, q3]
    db.execute.return_value = mock_result
    result = await get_price_range(db, FAKE_USER_ID, category="electronics")
    assert "Price range:" in result
    assert "$300" in result
    assert "$800" in result


@pytest.mark.asyncio
async def test_get_price_range_no_data():
    db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    db.execute.return_value = mock_result
    result = await get_price_range(db, FAKE_USER_ID, category="nonexistent")
    assert "No pricing data available" in result


@pytest.mark.asyncio
async def test_count_by_category():
    db = AsyncMock()
    mock_result = MagicMock()
    mock_result.all.return_value = [("electronics", 15), ("vehicles", 9), ("clothing", 7)]
    db.execute.return_value = mock_result
    result = await count_by_category(db, FAKE_USER_ID)
    assert "electronics (15)" in result
    assert "vehicles (9)" in result


@pytest.mark.asyncio
async def test_count_by_category_empty():
    db = AsyncMock()
    mock_result = MagicMock()
    mock_result.all.return_value = []
    db.execute.return_value = mock_result
    result = await count_by_category(db, FAKE_USER_ID)
    assert "No active listings" in result


@pytest.mark.asyncio
async def test_check_user_queries():
    db = AsyncMock()
    q1 = _make_query("Looking for a laptop", "buy", "electronics", user_id=FAKE_USER_ID)
    q2 = _make_query("Selling my bike", "sell", "sports", user_id=FAKE_USER_ID)
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [q1, q2]
    db.execute.return_value = mock_result
    result = await check_user_queries(db, FAKE_USER_ID)
    assert "2 active" in result
    assert "[buy]" in result


@pytest.mark.asyncio
async def test_check_user_queries_none():
    db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    db.execute.return_value = mock_result
    result = await check_user_queries(db, FAKE_USER_ID)
    assert "no active queries" in result


@pytest.mark.asyncio
async def test_execute_tool_unknown():
    db = AsyncMock()
    result = await execute_tool(db, FAKE_USER_ID, "nonexistent_tool", {})
    assert "Error: Unknown tool" in result


@pytest.mark.asyncio
async def test_execute_tool_dispatches():
    db = AsyncMock()
    mock_result = MagicMock()
    mock_result.all.return_value = [("buy", 3), ("sell", 3)]
    db.execute.return_value = mock_result
    result = await execute_tool(db, FAKE_USER_ID, "check_demand", {"category": "vehicles"})
    assert "vehicles" in result


def test_get_ollama_tools_format():
    tools = get_ollama_tools()
    assert len(tools) == 5
    for tool in tools:
        assert tool["type"] == "function"
        fn = tool["function"]
        assert "name" in fn
        assert "description" in fn
        assert "parameters" in fn


def test_get_ollama_tools_matches_registry():
    ollama_names = {t["function"]["name"] for t in get_ollama_tools()}
    registry_names = set(TOOL_REGISTRY.keys())
    assert ollama_names == registry_names


@pytest.mark.asyncio
async def test_search_listings_fuzzy_category():
    db = AsyncMock()
    q1 = _make_query("Selling a rhino stuffed animal", "sell", "toys")
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [q1]
    db.execute.return_value = mock_result
    result = await search_listings(db, FAKE_USER_ID, category="stuffed_animals")
    assert "1 active listing(s)" in result


@pytest.mark.asyncio
async def test_check_demand_fuzzy_category():
    db = AsyncMock()
    mock_result = MagicMock()
    mock_result.all.return_value = [("buy", 3), ("sell", 1)]
    db.execute.return_value = mock_result
    await check_demand(db, FAKE_USER_ID, category="stuffed_animals")


@pytest.mark.asyncio
async def test_get_price_range_fuzzy_category():
    db = AsyncMock()
    q1 = _make_query("Selling a rhino stuffed animal for $25", "sell", "toys", attributes={"price": 25})
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [q1]
    db.execute.return_value = mock_result
    result = await get_price_range(db, FAKE_USER_ID, category="stuffed_animals")
    assert "$25" in result


def test_category_filter_splits_words():
    from sqlalchemy.dialects import sqlite
    clause = _category_filter("stuffed_animals")
    compiled = str(clause.compile(dialect=sqlite.dialect(), compile_kwargs={"literal_binds": True}))
    assert "stuffed" in compiled.lower()
    assert "animals" in compiled.lower()

    clause = _category_filter("stuffed animals")
    compiled = str(clause.compile(dialect=sqlite.dialect(), compile_kwargs={"literal_binds": True}))
    assert "stuffed" in compiled.lower()
    assert "animals" in compiled.lower()

    clause = _category_filter("electronics")
    compiled = str(clause.compile(dialect=sqlite.dialect(), compile_kwargs={"literal_binds": True}))
    assert "electronics" in compiled.lower()
