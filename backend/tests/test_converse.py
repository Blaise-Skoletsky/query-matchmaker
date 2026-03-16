"""Tests for the agentic converse() function."""
from unittest.mock import AsyncMock, patch

import pytest

from app.services.llm import MAX_CLARIFICATIONS, synthesize_summary, converse


@pytest.mark.asyncio
async def test_asks_followup_on_vague_input():
    """A sparse first message should get an 'ask', not immediate submit."""
    history = [{"role": "user", "content": "I want to buy something"}]

    with patch("app.services.llm._chat_with_tools", new=AsyncMock(return_value={"content": '{"action": "ask", "message": "What specifically are you looking to buy?"}'})):
        result = await converse(history)

    assert result["action"] == "ask"
    assert "message" in result


@pytest.mark.asyncio
async def test_submits_at_safety_cap():
    """At MAX_CLARIFICATIONS user messages the result must be 'submit'."""
    history = []
    for i in range(MAX_CLARIFICATIONS):
        history.append({"role": "user", "content": f"User message {i}"})
        if i < MAX_CLARIFICATIONS - 1:
            history.append({"role": "assistant", "content": f"Question {i}?"})

    with patch("app.services.llm._chat_with_tools", new=AsyncMock(return_value={"content": '{"action": "submit", "summary": "Buying a used MacBook Pro 16-inch under $1500 in good condition"}'})):
        result = await converse(history)

    assert result["action"] == "submit"
    assert "summary" in result


@pytest.mark.asyncio
async def test_synthesize_summary_incorporates_answers():
    """The synthesized summary contains key details from the conversation."""
    history = [
        {"role": "assistant", "content": "What are you looking for?"},
        {"role": "user", "content": "I want to buy a bicycle"},
        {"role": "assistant", "content": "What is your budget?"},
        {"role": "user", "content": "Around $300, must be a road bike"},
    ]

    expected_summary = "Looking to buy a road bicycle for around $300."
    with patch("app.services.llm._chat", new=AsyncMock(return_value=expected_summary)):
        result = await synthesize_summary(history)

    assert "bicycle" in result.lower() or "road" in result.lower() or "300" in result


@pytest.mark.asyncio
async def test_converse_returns_tool_call():
    """converse() returns tool_call action when LLM returns native tool_calls."""
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
        result = await converse([{"role": "user", "content": "I want to buy a car"}])

    assert result["action"] == "tool_call"
    assert result["tool"] == "check_demand"
    assert result["args"] == {"category": "vehicles"}


@pytest.mark.asyncio
async def test_converse_prose_treated_as_ask():
    """LLM returning prose instead of JSON is treated as an ask."""
    with patch("app.services.llm._chat_with_tools", new=AsyncMock(return_value={
        "content": "What kind of product are you looking to buy or sell today?"
    })):
        result = await converse([{"role": "user", "content": "hello"}])

    assert result["action"] == "ask"


@pytest.mark.asyncio
async def test_converse_empty_content_retries():
    """Empty content from LLM triggers retry, eventually falls back to ask."""
    call_count = 0

    async def mock_chat(messages, tools=None, temperature=0):
        nonlocal call_count
        call_count += 1
        return {"content": ""}

    with patch("app.services.llm._chat_with_tools", side_effect=mock_chat):
        result = await converse([{"role": "user", "content": "buy something"}])

    assert call_count == 3  # retries 3 times
    assert result["action"] == "ask"


@pytest.mark.asyncio
async def test_converse_forced_submit_fallback():
    """At safety cap, if LLM still returns ask, synthesize_summary is used."""
    history = []
    for i in range(MAX_CLARIFICATIONS):
        history.append({"role": "user", "content": f"msg {i}"})
        if i < MAX_CLARIFICATIONS - 1:
            history.append({"role": "assistant", "content": f"q {i}?"})

    with patch("app.services.llm._chat_with_tools", new=AsyncMock(return_value={
        "content": '{"action": "ask", "message": "What else?"}'
    })):
        with patch("app.services.llm.synthesize_summary", new=AsyncMock(return_value="Synthesized summary")) as mock_synth:
            result = await converse(history)

    assert result["action"] == "submit"
    assert result["summary"] == "Synthesized summary"


@pytest.mark.asyncio
async def test_converse_tool_args_string_parsed():
    """When Ollama returns tool_call args as a JSON string, it's parsed correctly."""
    mock_msg = {
        "content": "",
        "tool_calls": [{
            "function": {
                "name": "get_price_range",
                "arguments": '{"category": "electronics"}',
            }
        }],
    }

    with patch("app.services.llm._chat_with_tools", new=AsyncMock(return_value=mock_msg)):
        result = await converse([{"role": "user", "content": "sell laptop"}])

    assert result["action"] == "tool_call"
    assert result["args"] == {"category": "electronics"}


@pytest.mark.asyncio
async def test_converse_tools_disabled_at_safety_cap():
    """At safety cap, tools are not offered to the LLM (must_submit path)."""
    history = []
    for i in range(MAX_CLARIFICATIONS):
        history.append({"role": "user", "content": f"msg {i}"})
        if i < MAX_CLARIFICATIONS - 1:
            history.append({"role": "assistant", "content": f"q {i}?"})

    captured_tools = []

    async def mock_chat(messages, tools=None, temperature=0):
        captured_tools.append(tools)
        return {"content": '{"action": "submit", "summary": "Buy a laptop"}'}

    with patch("app.services.llm._chat_with_tools", side_effect=mock_chat):
        await converse(history)

    assert captured_tools[0] is None


@pytest.mark.asyncio
async def test_converse_tools_disabled_after_tool_result():
    """When last messages include a tool result, tools are disabled."""
    history = [
        {"role": "user", "content": "sell my laptop"},
        {"role": "assistant", "content": "", "tool_calls": [{"function": {"name": "check_demand", "arguments": {}}}]},
        {"role": "tool", "content": "5 buyers"},
        {"role": "system", "content": "You just called a tool..."},
    ]

    captured_tools = []

    async def mock_chat(messages, tools=None, temperature=0):
        captured_tools.append(tools)
        return {"content": '{"action": "ask", "message": "There are 5 buyers."}'}

    with patch("app.services.llm._chat_with_tools", side_effect=mock_chat):
        await converse(history)

    assert captured_tools[0] is None
