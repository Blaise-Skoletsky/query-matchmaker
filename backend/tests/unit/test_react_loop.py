"""Tests for the ReAct tool execution loop in conversation router."""
import json
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.routers.conversation import MAX_TOOL_CALLS


@pytest.mark.asyncio
async def test_react_loop_tool_then_ask():
    """The ReAct loop executes a tool call, appends result, and gets final ask."""
    tool_call_response = {
        "action": "tool_call",
        "tool": "check_demand",
        "args": {"category": "electronics"},
    }
    ask_response = {
        "action": "ask",
        "message": "There are 5 buyers. What condition is your item?",
    }

    call_count = 0

    async def mock_converse(history):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return tool_call_response
        return ask_response

    with patch("app.routers.conversation.converse", side_effect=mock_converse), \
         patch("app.routers.conversation.execute_tool", new=AsyncMock(return_value="In 'electronics': 5 buyer(s), 3 seller(s).")), \
         patch("app.routers.conversation.get_db"), \
         patch("app.routers.conversation.get_current_user"):

        from app.routers.conversation import chat_turn

        body = MagicMock()
        body.history = [{"role": "user", "content": "I want to sell electronics"}]
        bg = MagicMock()
        db = AsyncMock()
        user = MagicMock()
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

        body = MagicMock()
        body.history = [{"role": "user", "content": "test"}]
        bg = MagicMock()
        db = AsyncMock()
        user = MagicMock()
        user.id = "test-user-id"

        result = await chat_turn(body, bg, db, user)

    assert call_count == MAX_TOOL_CALLS + 1
    assert result.tools_used is not None


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
        return {
            "action": "submit",
            "summary": "I want to sell a stuffed rhino for $25.",
        }

    with patch("app.routers.conversation.converse", side_effect=mock_converse), \
         patch("app.routers.conversation.execute_tool", new=AsyncMock(return_value="Price range: $10-$30")):

        from app.routers.conversation import chat_turn

        body = MagicMock()
        body.history = [{"role": "user", "content": "I want to sell my stuffed rhino"}]
        bg = MagicMock()
        db = AsyncMock()
        user = MagicMock()
        user.id = "test-user-id"

        result = await chat_turn(body, bg, db, user)

    assert result.action == "ask"
    assert result.query_id is None
    assert len(result.tools_used) == 1


@pytest.mark.asyncio
async def test_duplicate_query_check_blocks_submission():
    """Submitting a query that overlaps with an existing active query returns ask instead."""
    async def mock_converse(history):
        return {"action": "submit", "summary": "I want to buy a stuffed animal rhino."}

    async def mock_check_user_queries(db, user_id):
        return (
            "You have 1 active query/queries:\n"
            "  1) [buy] I want to buy a stuffed animal rhino."
        )

    with patch("app.routers.conversation.converse", side_effect=mock_converse), \
         patch("app.routers.conversation.check_user_queries", side_effect=mock_check_user_queries):

        from app.routers.conversation import chat_turn

        body = MagicMock()
        body.history = [{"role": "user", "content": "I want to buy a stuffed animal rhino"}]
        bg = MagicMock()
        db = AsyncMock()
        user = MagicMock()
        user.id = "test-user-id"

        result = await chat_turn(body, bg, db, user)

    assert result.action == "ask"
    assert "similar active query" in result.message


@pytest.mark.asyncio
async def test_duplicate_check_skipped_after_warning():
    """If the user was already warned about a duplicate, allow submission."""
    async def mock_converse(history):
        return {"action": "submit", "summary": "I want to buy a stuffed animal rhino."}

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

        body = MagicMock()
        body.history = [
            {"role": "user", "content": "I want to buy a stuffed animal rhino"},
            {"role": "assistant", "content": "You already have a similar active query: 1) [buy] I want to buy a stuffed animal rhino. Would you like to continue and create a new one anyway?"},
            {"role": "user", "content": "Yes, create it anyway"},
        ]
        bg = MagicMock()
        db = AsyncMock()
        user = MagicMock()
        user.id = "test-user-id"

        result = await chat_turn(body, bg, db, user)

    assert result.action == "submitted"
    assert result.query_id is not None


@pytest.mark.asyncio
async def test_duplicate_check_ignores_opposite_intent():
    """Selling a MacBook should not flag a buy MacBook query as duplicate."""
    async def mock_converse(history):
        return {"action": "submit", "summary": "I want to sell my MacBook Pro for $10,000."}

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

        body = MagicMock()
        body.history = [{"role": "user", "content": "I want to sell my MacBook Pro"}]
        bg = MagicMock()
        db = AsyncMock()
        user = MagicMock()
        user.id = "test-user-id"

        result = await chat_turn(body, bg, db, user)

    assert result.action == "submitted"
    assert result.query_id is not None


@pytest.mark.asyncio
async def test_converse_scope_guardrail():
    """The converse() system prompt contains scope rules and early-submit rules."""
    with patch("app.services.llm._chat_with_tools", new=AsyncMock(return_value={
        "content": '{"action": "ask", "message": "What would you like to buy or sell?"}',
    })):
        from app.services.llm import converse, _chat_with_tools

        result = await converse([{"role": "user", "content": "Set up a notification for me"}])

        call_args = _chat_with_tools.call_args[0][0]
        system_content = call_args[0]["content"]

        assert "SCOPE RULES" in system_content
        assert "MUST NOT" in system_content
        assert "WHEN TO SUBMIT EARLY" in system_content


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
