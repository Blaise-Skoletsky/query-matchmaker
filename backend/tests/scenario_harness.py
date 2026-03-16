"""Data-driven conversation scenario test harness.

Defines dataclasses for scripting conversation scenarios and two runner
functions that wire up mocks automatically — no boilerplate per test.

Level 1: run_converse_scenario  — patches _chat_with_tools, calls converse()
Level 2: run_chat_turn_scenario — patches converse()/execute_tool, calls chat_turn()
"""

import contextlib
import json
import uuid
from dataclasses import dataclass, field
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.llm import converse


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class LLMResponse:
    """What _chat_with_tools returns for one converse() invocation."""
    content: str = ""
    tool_calls: list[dict] | None = None


@dataclass
class ToolResult:
    """Scripted tool execution result for chat_turn-level tests."""
    tool_name: str
    args: dict
    result: str


@dataclass
class ExpectedOutcome:
    """Assertions to verify after a scenario completes."""
    final_action: str  # "ask" | "submit" | "submitted"
    message_contains: list[str] = field(default_factory=list)
    tools_called: list[tuple[str, dict]] = field(default_factory=list)
    tool_call_order: list[str] | None = None
    query_id_present: bool | None = None
    tools_used_count: int | None = None


@dataclass
class Turn:
    """One step in a scripted conversation.

    For converse-level tests: llm_response + user_reply.
    For chat_turn-level tests: converse_result + tool_result.
    """
    # converse-level: raw LLM API return
    llm_response: LLMResponse | None = None
    user_reply: str | None = None

    # chat_turn-level: what converse() returns
    converse_result: dict | None = None
    tool_result: ToolResult | None = None


@dataclass
class ConversationScenario:
    """Full scenario definition — add one of these to create a new test."""
    name: str
    description: str
    initial_history: list[dict]
    turns: list[Turn]
    expected: ExpectedOutcome

    # chat_turn-level mocks
    mock_check_user_queries: str | None = None
    mock_embed: list[float] | None = None
    mock_metadata: dict | None = None
    synthesize_summary_return: str | None = None


# ---------------------------------------------------------------------------
# Level 1: converse()-level runner
# ---------------------------------------------------------------------------

async def run_converse_scenario(scenario: ConversationScenario):
    """Run a converse-level scenario by patching _chat_with_tools."""
    # Build the mock response queue from turns
    responses = []
    for turn in scenario.turns:
        if turn.llm_response is None:
            continue
        if turn.llm_response.tool_calls:
            responses.append({
                "content": turn.llm_response.content or "",
                "tool_calls": turn.llm_response.tool_calls,
            })
        else:
            responses.append({"content": turn.llm_response.content})

    call_idx = 0

    async def mock_chat_with_tools(messages, tools=None, temperature=0):
        nonlocal call_idx
        assert call_idx < len(responses), (
            f"Scenario '{scenario.name}': _chat_with_tools called more times "
            f"than responses provided ({len(responses)})"
        )
        resp = responses[call_idx]
        call_idx += 1
        return resp

    history = list(scenario.initial_history)
    final_result = None
    tools_requested: list[tuple[str, dict]] = []

    with patch("app.services.llm._chat_with_tools", side_effect=mock_chat_with_tools):
        for turn in scenario.turns:
            if turn.llm_response is None:
                continue

            result = await converse(history)
            final_result = result

            if result["action"] == "tool_call":
                tools_requested.append((result["tool"], result.get("args", {})))
                # At converse level, tool_call is returned to caller — no execution
                break

            if result["action"] == "ask" and turn.user_reply:
                history.append({"role": "assistant", "content": result["message"]})
                history.append({"role": "user", "content": turn.user_reply})
            elif result["action"] == "submit":
                break

    assert final_result is not None, f"Scenario '{scenario.name}': no result produced"

    # Verify final action
    assert final_result["action"] == scenario.expected.final_action, (
        f"Scenario '{scenario.name}': expected action '{scenario.expected.final_action}', "
        f"got '{final_result['action']}'"
    )

    # Verify message content
    msg = final_result.get("message") or final_result.get("summary", "")
    for substr in scenario.expected.message_contains:
        assert substr.lower() in msg.lower(), (
            f"Scenario '{scenario.name}': expected '{substr}' in message: {msg}"
        )

    # Verify tools requested
    if scenario.expected.tools_called:
        assert tools_requested == scenario.expected.tools_called, (
            f"Scenario '{scenario.name}': tool calls mismatch: "
            f"expected {scenario.expected.tools_called}, got {tools_requested}"
        )

    if scenario.expected.tool_call_order is not None:
        actual_order = [t[0] for t in tools_requested]
        assert actual_order == scenario.expected.tool_call_order, (
            f"Scenario '{scenario.name}': tool call order mismatch"
        )


# ---------------------------------------------------------------------------
# Level 2: chat_turn()-level runner
# ---------------------------------------------------------------------------

async def run_chat_turn_scenario(scenario: ConversationScenario):
    """Run a chat_turn-level scenario by patching converse/execute_tool/etc."""
    from app.routers.conversation import chat_turn, ConversationRequest

    # Build converse() mock responses
    converse_responses = []
    tool_results = []
    for turn in scenario.turns:
        if turn.converse_result is not None:
            converse_responses.append(turn.converse_result)
        if turn.tool_result is not None:
            tool_results.append(turn.tool_result)

    converse_idx = 0
    tool_idx = 0

    async def mock_converse(history):
        nonlocal converse_idx
        assert converse_idx < len(converse_responses), (
            f"Scenario '{scenario.name}': converse() called more times "
            f"than responses provided ({len(converse_responses)})"
        )
        resp = converse_responses[converse_idx]
        converse_idx += 1
        return resp

    async def mock_execute_tool(db, user_id, tool_name, args):
        nonlocal tool_idx
        assert tool_idx < len(tool_results), (
            f"Scenario '{scenario.name}': execute_tool() called more times "
            f"than results provided ({len(tool_results)})"
        )
        tr = tool_results[tool_idx]
        assert tool_name == tr.tool_name, (
            f"Scenario '{scenario.name}': expected tool '{tr.tool_name}', got '{tool_name}'"
        )
        assert args == tr.args, (
            f"Scenario '{scenario.name}': tool '{tool_name}' args mismatch: "
            f"expected {tr.args}, got {args}"
        )
        tool_idx += 1
        return tr.result

    # Mock dependencies
    mock_db = AsyncMock()
    mock_user = MagicMock()
    mock_user.id = uuid.uuid4()
    mock_bg = MagicMock()

    # Handle db.refresh to set query.id
    assigned_query_id = uuid.uuid4()

    async def mock_refresh(obj):
        obj.id = assigned_query_id

    mock_db.refresh = mock_refresh

    check_queries_return = scenario.mock_check_user_queries or "You have no active queries."
    embed_return = scenario.mock_embed or [0.0] * 384
    metadata_return = scenario.mock_metadata or {
        "intent": "buy",
        "category": "general",
        "attributes": {},
        "complementary_intents": ["sell"],
        "required_match_attributes": [],
        "preferred_match_attributes": [],
    }
    synth_return = scenario.synthesize_summary_return or "Synthesized summary."

    body = ConversationRequest(history=scenario.initial_history)

    with contextlib.ExitStack() as stack:
        stack.enter_context(
            patch("app.routers.conversation.converse", side_effect=mock_converse)
        )
        stack.enter_context(
            patch("app.routers.conversation.execute_tool", side_effect=mock_execute_tool)
        )
        stack.enter_context(
            patch(
                "app.routers.conversation.check_user_queries",
                new=AsyncMock(return_value=check_queries_return),
            )
        )
        stack.enter_context(
            patch(
                "app.routers.conversation.embed_async",
                new=AsyncMock(return_value=embed_return),
            )
        )
        stack.enter_context(
            patch(
                "app.routers.conversation.extract_metadata",
                new=AsyncMock(return_value=metadata_return),
            )
        )
        stack.enter_context(
            patch(
                "app.routers.conversation.synthesize_summary",
                new=AsyncMock(return_value=synth_return),
            )
        )

        response = await chat_turn(body, mock_bg, db=mock_db, user=mock_user)

    # Verify final action
    assert response.action == scenario.expected.final_action, (
        f"Scenario '{scenario.name}': expected action '{scenario.expected.final_action}', "
        f"got '{response.action}'"
    )

    # Verify message content
    msg = response.message or ""
    for substr in scenario.expected.message_contains:
        assert substr.lower() in msg.lower(), (
            f"Scenario '{scenario.name}': expected '{substr}' in message: {msg}"
        )

    # Verify query_id
    if scenario.expected.query_id_present is True:
        assert response.query_id is not None, (
            f"Scenario '{scenario.name}': expected query_id to be present"
        )
    elif scenario.expected.query_id_present is False:
        assert response.query_id is None, (
            f"Scenario '{scenario.name}': expected query_id to be absent"
        )

    # Verify tools_used count
    if scenario.expected.tools_used_count is not None:
        actual_count = len(response.tools_used) if response.tools_used else 0
        assert actual_count == scenario.expected.tools_used_count, (
            f"Scenario '{scenario.name}': expected {scenario.expected.tools_used_count} "
            f"tools_used, got {actual_count}"
        )

    # Verify tool call order
    if scenario.expected.tool_call_order is not None:
        actual_order = [t["tool"] for t in (response.tools_used or [])]
        assert actual_order == scenario.expected.tool_call_order, (
            f"Scenario '{scenario.name}': tool call order mismatch: "
            f"expected {scenario.expected.tool_call_order}, got {actual_order}"
        )
