"""Safety cap, submit-after-tool block, max tool calls, and duplicate scenarios (chat_turn-level)."""

from app.routers.conversation import MAX_TOOL_CALLS
from app.services.llm import MAX_CLARIFICATIONS
from tests.scenario_harness import (
    ConversationScenario,
    ExpectedOutcome,
    ToolResult,
    Turn,
)


def _build_safety_cap_history() -> list[dict]:
    """Build a history with MAX_CLARIFICATIONS user messages."""
    history = []
    for i in range(MAX_CLARIFICATIONS):
        history.append({"role": "user", "content": f"User message {i}"})
        if i < MAX_CLARIFICATIONS - 1:
            history.append({"role": "assistant", "content": f"Question {i}?"})
    return history


SCENARIOS = [
    # 11. Safety cap forces submit
    ConversationScenario(
        name="safety_cap_forces_submit",
        description="MAX_CLARIFICATIONS reached → forced submit → query created",
        initial_history=_build_safety_cap_history(),
        turns=[
            Turn(
                converse_result={
                    "action": "submit",
                    "summary": "I want to buy a used MacBook Pro 16-inch under $1500 in good condition.",
                },
            ),
        ],
        expected=ExpectedOutcome(
            final_action="submitted",
            message_contains=["query submitted"],
            query_id_present=True,
            tools_used_count=0,
        ),
    ),
    # 12. Submit blocked right after tool call
    ConversationScenario(
        name="submit_blocked_after_tool",
        description="tool → submit attempt → converted to ask by guardrail",
        initial_history=[
            {"role": "user", "content": "I want to sell my guitar"},
        ],
        turns=[
            Turn(
                converse_result={
                    "action": "tool_call",
                    "tool": "check_demand",
                    "args": {"category": "music"},
                },
                tool_result=ToolResult(
                    tool_name="check_demand",
                    args={"category": "music"},
                    result="In 'music': 5 buyer(s), 2 seller(s). High demand for sellers.",
                ),
            ),
            Turn(
                converse_result={
                    "action": "submit",
                    "summary": "I want to sell my guitar.",
                },
            ),
        ],
        expected=ExpectedOutcome(
            final_action="ask",
            message_contains=["guitar"],
            tools_used_count=1,
            query_id_present=False,
        ),
    ),
    # 13. Max tool calls cap — LLM keeps requesting tools
    ConversationScenario(
        name="max_tool_calls_cap",
        description="LLM requests tools beyond MAX_TOOL_CALLS → loop terminates",
        initial_history=[
            {"role": "user", "content": "I want to buy electronics"},
        ],
        turns=[
            *(
                Turn(
                    converse_result={
                        "action": "tool_call",
                        "tool": "check_demand",
                        "args": {"category": "electronics"},
                    },
                    tool_result=ToolResult(
                        tool_name="check_demand",
                        args={"category": "electronics"},
                        result="In 'electronics': 10 buyer(s), 5 seller(s).",
                    ),
                )
                for _ in range(MAX_TOOL_CALLS + 1)
            ),
        ],
        expected=ExpectedOutcome(
            final_action="ask",
            tools_used_count=MAX_TOOL_CALLS + 1,
        ),
    ),
    # 14. Duplicate query with same intent → blocked
    ConversationScenario(
        name="duplicate_query_same_intent_blocked",
        description="buy + existing buy with overlap → similar active query warning",
        initial_history=[
            {"role": "user", "content": "I want to buy a used laptop computer"},
        ],
        turns=[
            Turn(
                converse_result={
                    "action": "submit",
                    "summary": "I want to buy a used laptop computer under $1000.",
                },
            ),
        ],
        mock_check_user_queries=(
            "You have 1 active query/queries:\n"
            "  1) [buy] I want to buy a used laptop computer for school"
        ),
        expected=ExpectedOutcome(
            final_action="ask",
            message_contains=["similar active query"],
            query_id_present=False,
            tools_used_count=0,
        ),
    ),
    # 15. Duplicate skipped for opposite intent → allowed through
    ConversationScenario(
        name="duplicate_skipped_opposite_intent",
        description="sell vs existing buy → no duplicate block, query created",
        initial_history=[
            {"role": "user", "content": "I want to sell my used laptop computer"},
        ],
        turns=[
            Turn(
                converse_result={
                    "action": "submit",
                    "summary": "I want to sell my used laptop computer for $800.",
                },
            ),
        ],
        mock_check_user_queries=(
            "You have 1 active query/queries:\n"
            "  1) [buy] I want to buy a used laptop computer for school"
        ),
        mock_metadata={
            "intent": "sell",
            "category": "electronics",
            "attributes": {"item": "laptop", "price": 800},
            "complementary_intents": ["buy"],
            "required_match_attributes": [],
            "preferred_match_attributes": [],
        },
        expected=ExpectedOutcome(
            final_action="submitted",
            message_contains=["query submitted"],
            query_id_present=True,
            tools_used_count=0,
        ),
    ),
]
