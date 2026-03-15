"""Tests for the tool registry and ReAct tool execution loop."""
import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.services.tools import (
    execute_tool, search_listings, check_demand,
    get_price_range, count_by_category, check_user_queries,
    TOOL_REGISTRY, get_ollama_tools,
    _category_filter,
)
from app.routers.conversation import MAX_TOOL_CALLS

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
    """search_listings returns formatted results from the DB."""
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
    """search_listings returns a message when no listings found."""
    db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    db.execute.return_value = mock_result

    result = await search_listings(db, FAKE_USER_ID, category="nonexistent")

    assert "No active listings" in result


@pytest.mark.asyncio
async def test_check_demand_balanced():
    """check_demand reports balanced market."""
    db = AsyncMock()
    mock_result = MagicMock()
    mock_result.all.return_value = [("buy", 5), ("sell", 4)]
    db.execute.return_value = mock_result

    result = await check_demand(db, FAKE_USER_ID, category="electronics")

    assert "5 buyer(s)" in result
    assert "4 seller(s)" in result
    assert "balanced" in result.lower()


@pytest.mark.asyncio
async def test_check_demand_high_buyer_demand():
    """check_demand reports high demand for sellers."""
    db = AsyncMock()
    mock_result = MagicMock()
    mock_result.all.return_value = [("buy", 10), ("sell", 2)]
    db.execute.return_value = mock_result

    result = await check_demand(db, FAKE_USER_ID, category="electronics")

    assert "High demand for sellers" in result


@pytest.mark.asyncio
async def test_check_demand_empty():
    """check_demand handles categories with no listings."""
    db = AsyncMock()
    mock_result = MagicMock()
    mock_result.all.return_value = []
    db.execute.return_value = mock_result

    result = await check_demand(db, FAKE_USER_ID, category="nothing")

    assert "No active listings" in result


@pytest.mark.asyncio
async def test_get_price_range_with_prices():
    """get_price_range extracts prices from attributes and raw_text."""
    db = AsyncMock()
    q1 = _make_query("Selling laptop for $500", "sell", "electronics",
                     attributes={"price": 500})
    q2 = _make_query("iPhone $800 firm", "sell", "electronics",
                     attributes={})
    q3 = _make_query("Budget around $300", "buy", "electronics",
                     attributes={"budget": "300"})

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [q1, q2, q3]
    db.execute.return_value = mock_result

    result = await get_price_range(db, FAKE_USER_ID, category="electronics")

    assert "Price range:" in result
    assert "$300" in result
    assert "$800" in result


@pytest.mark.asyncio
async def test_get_price_range_no_data():
    """get_price_range returns message when no listings found."""
    db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    db.execute.return_value = mock_result

    result = await get_price_range(db, FAKE_USER_ID, category="nonexistent")

    assert "No pricing data available" in result


@pytest.mark.asyncio
async def test_count_by_category():
    """count_by_category returns formatted category counts."""
    db = AsyncMock()
    mock_result = MagicMock()
    mock_result.all.return_value = [("electronics", 15), ("vehicles", 9), ("clothing", 7)]
    db.execute.return_value = mock_result

    result = await count_by_category(db, FAKE_USER_ID)

    assert "electronics (15)" in result
    assert "vehicles (9)" in result
    assert "clothing (7)" in result


@pytest.mark.asyncio
async def test_count_by_category_empty():
    """count_by_category handles no active listings."""
    db = AsyncMock()
    mock_result = MagicMock()
    mock_result.all.return_value = []
    db.execute.return_value = mock_result

    result = await count_by_category(db, FAKE_USER_ID)

    assert "No active listings" in result


@pytest.mark.asyncio
async def test_check_user_queries():
    """check_user_queries lists the user's active queries."""
    db = AsyncMock()
    q1 = _make_query("Looking for a laptop", "buy", "electronics", user_id=FAKE_USER_ID)
    q2 = _make_query("Selling my bike", "sell", "sports", user_id=FAKE_USER_ID)

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [q1, q2]
    db.execute.return_value = mock_result

    result = await check_user_queries(db, FAKE_USER_ID)

    assert "2 active" in result
    assert "[buy]" in result
    assert "[sell]" in result
    assert "laptop" in result
    assert "bike" in result


@pytest.mark.asyncio
async def test_check_user_queries_none():
    """check_user_queries handles user with no active queries."""
    db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    db.execute.return_value = mock_result

    result = await check_user_queries(db, FAKE_USER_ID)

    assert "no active queries" in result


@pytest.mark.asyncio
async def test_execute_tool_unknown():
    """execute_tool returns error for unknown tool names."""
    db = AsyncMock()
    result = await execute_tool(db, FAKE_USER_ID, "nonexistent_tool", {})
    assert "Error: Unknown tool" in result
    assert "nonexistent_tool" in result


@pytest.mark.asyncio
async def test_execute_tool_dispatches():
    """execute_tool dispatches to the correct tool function."""
    db = AsyncMock()
    mock_result = MagicMock()
    mock_result.all.return_value = [("buy", 3), ("sell", 3)]
    db.execute.return_value = mock_result

    result = await execute_tool(db, FAKE_USER_ID, "check_demand", {"category": "vehicles"})
    assert "vehicles" in result


@pytest.mark.asyncio
async def test_react_loop_tool_then_ask():
    """The ReAct loop executes a tool call, appends result, and gets final ask."""
    tool_call_response = json.dumps({
        "action": "tool_call",
        "tool": "check_demand",
        "args": {"category": "electronics"},
    })
    ask_response = json.dumps({
        "action": "ask",
        "message": "There are 5 buyers. What condition is your item?",
    })

    call_count = 0

    async def mock_converse(history):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return json.loads(tool_call_response)
        return json.loads(ask_response)

    with patch("app.routers.conversation.converse", side_effect=mock_converse), \
         patch("app.routers.conversation.execute_tool", new=AsyncMock(return_value="In 'electronics': 5 buyer(s), 3 seller(s).")), \
         patch("app.routers.conversation.get_db"), \
         patch("app.routers.conversation.get_current_user"):

        from app.routers.conversation import chat_turn
        from unittest.mock import MagicMock as SyncMock

        body = SyncMock()
        body.history = [{"role": "user", "content": "I want to sell electronics"}]
        bg = SyncMock()
        db = AsyncMock()
        user = SyncMock()
        user.id = "test-user-id"

        result = await chat_turn(body, bg, db, user)

    assert result.action == "ask"
    assert result.tools_used is not None
    assert len(result.tools_used) == 1
    assert result.tools_used[0]["tool"] == "check_demand"


@pytest.mark.asyncio
async def test_react_loop_safety_cap():
    """The ReAct loop stops after MAX_TOOL_CALLS even if LLM keeps requesting tools."""
    call_count = 0

    async def mock_converse_always_tool(history):
        nonlocal call_count
        call_count += 1
        return {
            "action": "tool_call",
            "tool": "check_demand",
            "args": {"category": "test"},
        }

    with patch("app.routers.conversation.converse", side_effect=mock_converse_always_tool), \
         patch("app.routers.conversation.execute_tool", new=AsyncMock(return_value="result")):

        from app.routers.conversation import chat_turn
        from unittest.mock import MagicMock as SyncMock

        body = SyncMock()
        body.history = [{"role": "user", "content": "test"}]
        bg = SyncMock()
        db = AsyncMock()
        user = SyncMock()
        user.id = "test-user-id"

        result = await chat_turn(body, bg, db, user)

    assert call_count == MAX_TOOL_CALLS + 1
    assert result.tools_used is not None


def test_get_ollama_tools_format():
    """OLLAMA_TOOLS has valid OpenAI-compatible schema for all 5 tools."""
    tools = get_ollama_tools()
    assert len(tools) == 5

    for tool in tools:
        assert tool["type"] == "function"
        fn = tool["function"]
        assert "name" in fn
        assert "description" in fn
        assert "parameters" in fn
        params = fn["parameters"]
        assert params["type"] == "object"
        assert "properties" in params
        assert "required" in params


def test_get_ollama_tools_matches_registry():
    """Every TOOL_REGISTRY key has a corresponding get_ollama_tools() entry."""
    ollama_names = {t["function"]["name"] for t in get_ollama_tools()}
    registry_names = set(TOOL_REGISTRY.keys())
    assert ollama_names == registry_names


@pytest.mark.asyncio
async def test_react_loop_blocks_submit_after_tool():
    """If LLM returns submit immediately after a tool call, the router converts it to ask."""
    call_count = 0

    async def mock_converse(history):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return {
                "action": "tool_call",
                "tool": "get_price_range",
                "args": {"category": "toys"},
            }
        # LLM tries to submit right after tool — should be blocked
        return {
            "action": "submit",
            "summary": "I want to sell a stuffed rhino for $25.",
        }

    with patch("app.routers.conversation.converse", side_effect=mock_converse), \
         patch("app.routers.conversation.execute_tool", new=AsyncMock(return_value="Price range: $10-$30")):

        from app.routers.conversation import chat_turn
        from unittest.mock import MagicMock as SyncMock

        body = SyncMock()
        body.history = [{"role": "user", "content": "I want to sell my stuffed rhino"}]
        bg = SyncMock()
        db = AsyncMock()
        user = SyncMock()
        user.id = "test-user-id"

        result = await chat_turn(body, bg, db, user)

    # Should be converted to ask, not submitted
    assert result.action == "ask"
    assert result.query_id is None  # not submitted
    assert result.tools_used is not None
    assert len(result.tools_used) == 1
    assert result.tools_used[0]["tool"] == "get_price_range"


@pytest.mark.asyncio
async def test_duplicate_query_check_blocks_submission():
    """Submitting a query that overlaps with an existing active query returns ask instead."""
    async def mock_converse(history):
        return {
            "action": "submit",
            "summary": "I want to buy a stuffed animal rhino.",
        }

    async def mock_check_user_queries(db, user_id):
        return (
            "You have 1 active query/queries:\n"
            "  1) [buy] I want to buy a stuffed animal rhino."
        )

    with patch("app.routers.conversation.converse", side_effect=mock_converse), \
         patch("app.routers.conversation.check_user_queries", side_effect=mock_check_user_queries):

        from app.routers.conversation import chat_turn
        from unittest.mock import MagicMock as SyncMock

        body = SyncMock()
        body.history = [{"role": "user", "content": "I want to buy a stuffed animal rhino"}]
        bg = SyncMock()
        db = AsyncMock()
        user = SyncMock()
        user.id = "test-user-id"

        result = await chat_turn(body, bg, db, user)

    assert result.action == "ask"
    assert "similar active query" in result.message
    assert result.query_id is None


@pytest.mark.asyncio
async def test_duplicate_check_skipped_after_warning():
    """If the user was already warned about a duplicate, allow submission."""
    async def mock_converse(history):
        return {
            "action": "submit",
            "summary": "I want to buy a stuffed animal rhino.",
        }

    async def mock_check_user_queries(db, user_id):
        return (
            "You have 1 active query/queries:\n"
            "  1) [buy] I want to buy a stuffed animal rhino."
        )

    with patch("app.routers.conversation.converse", side_effect=mock_converse), \
         patch("app.routers.conversation.check_user_queries", side_effect=mock_check_user_queries), \
         patch("app.routers.conversation.embed_async", new=AsyncMock(return_value=[0.0] * 384)), \
         patch("app.routers.conversation.extract_metadata", new=AsyncMock(return_value={"intent": "buy", "category": "toys", "attributes": {}, "complementary_intents": ["sell"]})):

        from app.routers.conversation import chat_turn
        from unittest.mock import MagicMock as SyncMock

        body = SyncMock()
        body.history = [
            {"role": "user", "content": "I want to buy a stuffed animal rhino"},
            {"role": "assistant", "content": "You already have a similar active query: 1) [buy] I want to buy a stuffed animal rhino. Would you like to continue and create a new one anyway?"},
            {"role": "user", "content": "Yes, create it anyway"},
        ]
        bg = SyncMock()
        db = AsyncMock()
        user = SyncMock()
        user.id = "test-user-id"

        result = await chat_turn(body, bg, db, user)

    # Should allow submission since user confirmed after warning
    assert result.action == "submitted"
    assert result.query_id is not None


@pytest.mark.asyncio
async def test_duplicate_check_ignores_opposite_intent():
    """Selling a MacBook should not flag a buy MacBook query as duplicate."""
    async def mock_converse(history):
        return {
            "action": "submit",
            "summary": "I want to sell my MacBook Pro for $10,000.",
        }

    async def mock_check_user_queries(db, user_id):
        return (
            "You have 1 active query/queries:\n"
            "  1) [buy] I want to buy a MacBook Pro."
        )

    with patch("app.routers.conversation.converse", side_effect=mock_converse), \
         patch("app.routers.conversation.check_user_queries", side_effect=mock_check_user_queries), \
         patch("app.routers.conversation.embed_async", new=AsyncMock(return_value=[0.0] * 384)), \
         patch("app.routers.conversation.extract_metadata", new=AsyncMock(return_value={"intent": "sell", "category": "electronics", "attributes": {}, "complementary_intents": ["buy"]})):

        from app.routers.conversation import chat_turn
        from unittest.mock import MagicMock as SyncMock

        body = SyncMock()
        body.history = [{"role": "user", "content": "I want to sell my MacBook Pro"}]
        bg = SyncMock()
        db = AsyncMock()
        user = SyncMock()
        user.id = "test-user-id"

        result = await chat_turn(body, bg, db, user)

    # Opposite intents (sell vs buy) — should NOT be flagged as duplicate
    assert result.action == "submitted"
    assert result.query_id is not None


@pytest.mark.asyncio
async def test_search_listings_fuzzy_category():
    """search_listings finds listings via word-level ILIKE when category has underscores/plurals."""
    db = AsyncMock()
    # Listing has category="toys" but user searches with "stuffed_animals"
    q1 = _make_query("Selling a rhino stuffed animal", "sell", "toys")

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [q1]
    db.execute.return_value = mock_result

    result = await search_listings(db, FAKE_USER_ID, category="stuffed_animals")

    # Verify word-level splitting: "stuffed_animals" → words "stuffed", "animals"
    # Each word gets its own ILIKE against both category and raw_text
    call_args = db.execute.call_args[0][0]
    where_str = str(call_args.compile(compile_kwargs={"literal_binds": True}))
    assert "like" in where_str.lower()
    # Word-level: should have individual words, not the full underscore string
    assert "stuffed" in where_str.lower()
    assert "animals" in where_str.lower()

    assert "1 active listing(s)" in result
    assert "rhino" in result


@pytest.mark.asyncio
async def test_check_demand_fuzzy_category():
    """check_demand uses word-level ILIKE matching on category and raw_text."""
    db = AsyncMock()
    mock_result = MagicMock()
    mock_result.all.return_value = [("buy", 3), ("sell", 1)]
    db.execute.return_value = mock_result

    result = await check_demand(db, FAKE_USER_ID, category="stuffed_animals")

    call_args = db.execute.call_args[0][0]
    where_str = str(call_args.compile(compile_kwargs={"literal_binds": True}))
    assert "like" in where_str.lower()
    assert "stuffed" in where_str.lower()
    assert "animals" in where_str.lower()


@pytest.mark.asyncio
async def test_get_price_range_fuzzy_category():
    """get_price_range uses word-level ILIKE matching on category and raw_text."""
    db = AsyncMock()
    q1 = _make_query("Selling a rhino stuffed animal for $25", "sell", "toys",
                     attributes={"price": 25})

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [q1]
    db.execute.return_value = mock_result

    result = await get_price_range(db, FAKE_USER_ID, category="stuffed_animals")

    call_args = db.execute.call_args[0][0]
    where_str = str(call_args.compile(compile_kwargs={"literal_binds": True}))
    assert "like" in where_str.lower()
    assert "stuffed" in where_str.lower()
    assert "animals" in where_str.lower()

    assert "$25" in result


@pytest.mark.asyncio
async def test_converse_scope_guardrail():
    """The converse() system prompt contains scope rules and early-submit rules."""
    with patch("app.services.llm._chat_with_tools", new=AsyncMock(return_value={
        "content": '{"action": "ask", "message": "What would you like to buy or sell?"}',
    })):
        from app.services.llm import converse

        # Capture the messages passed to _chat_with_tools
        from app.services.llm import _chat_with_tools
        result = await converse([{"role": "user", "content": "Set up a notification for me"}])

        call_args = _chat_with_tools.call_args[0][0]
        system_content = call_args[0]["content"]

        assert "SCOPE RULES" in system_content
        assert "notifications" in system_content.lower()
        assert "MUST NOT" in system_content

        # Early-submit rules
        assert "WHEN TO SUBMIT EARLY" in system_content
        assert "doesn't matter" in system_content
        assert "submit immediately" in system_content.lower()


@pytest.mark.asyncio
async def test_converse_native_tool_call():
    """converse() returns tool_call action when Ollama returns native tool_calls."""
    mock_msg = {
        "content": "",
        "tool_calls": [{
            "function": {
                "name": "check_demand",
                "arguments": {"category": "vehicles"},
            }
        }],
    }

    with patch("app.services.llm._chat_with_tools", new=AsyncMock(return_value=mock_msg)):
        from app.services.llm import converse

        result = await converse([{"role": "user", "content": "I want to buy a car"}])

    assert result["action"] == "tool_call"
    assert result["tool"] == "check_demand"
    assert result["args"] == {"category": "vehicles"}


def test_category_filter_splits_words():
    """_category_filter splits on spaces/underscores and generates per-word ILIKE conditions."""
    from sqlalchemy.dialects import sqlite

    # Multi-word with underscore
    clause = _category_filter("stuffed_animals")
    compiled = str(clause.compile(dialect=sqlite.dialect(), compile_kwargs={"literal_binds": True}))
    compiled_lower = compiled.lower()
    # Should split into "stuffed" and "animals", each matched against category and raw_text
    assert "stuffed" in compiled_lower
    assert "animals" in compiled_lower

    # Multi-word with space
    clause = _category_filter("stuffed animals")
    compiled = str(clause.compile(dialect=sqlite.dialect(), compile_kwargs={"literal_binds": True}))
    compiled_lower = compiled.lower()
    assert "stuffed" in compiled_lower
    assert "animals" in compiled_lower

    # Short words filtered out (< 3 chars)
    clause = _category_filter("a of toys")
    compiled = str(clause.compile(dialect=sqlite.dialect(), compile_kwargs={"literal_binds": True}))
    compiled_lower = compiled.lower()
    assert "toys" in compiled_lower
    # "a" and "of" should not appear as separate ILIKE patterns
    assert "%a%" not in compiled_lower or "a" in "toys"  # only appears within "toys"

    # Single word passes through
    clause = _category_filter("electronics")
    compiled = str(clause.compile(dialect=sqlite.dialect(), compile_kwargs={"literal_binds": True}))
    assert "electronics" in compiled.lower()
