"""Tests for the agentic converse() function."""
from unittest.mock import AsyncMock, patch

import pytest

from app.services.llm import MAX_CLARIFICATIONS, synthesize_summary, converse


@pytest.mark.asyncio
async def test_asks_followup_on_vague_input():
    """A sparse first message should get an 'ask', not immediate submit."""
    history = [{"role": "user", "content": "I want to buy something"}]

    with patch("app.services.llm._chat", new=AsyncMock(return_value='{"action": "ask", "message": "What specifically are you looking to buy?"}')):
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

    with patch("app.services.llm._chat", new=AsyncMock(return_value='{"action": "submit", "summary": "Buying a used MacBook Pro 16-inch under $1500 in good condition"}')):
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
