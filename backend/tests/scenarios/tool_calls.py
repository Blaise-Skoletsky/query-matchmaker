"""Tool usage pattern scenarios (converse-level and chat_turn-level)."""

from tests.scenario_harness import (
    ConversationScenario,
    ExpectedOutcome,
    LLMResponse,
    ToolResult,
    Turn,
)

# ---------------------------------------------------------------------------
# Converse-level scenarios (verify converse() returns tool_call correctly)
# ---------------------------------------------------------------------------

CONVERSE_SCENARIOS = [
    # 6. Single tool then ask — converse returns tool_call
    ConversationScenario(
        name="single_tool_then_ask",
        description="LLM requests check_demand tool → converse returns tool_call",
        initial_history=[
            {"role": "user", "content": "I want to sell my old laptop"},
        ],
        turns=[
            Turn(
                llm_response=LLMResponse(
                    tool_calls=[{
                        "function": {
                            "name": "check_demand",
                            "arguments": {"category": "electronics"},
                        }
                    }],
                ),
            ),
        ],
        expected=ExpectedOutcome(
            final_action="tool_call",
            tools_called=[("check_demand", {"category": "electronics"})],
        ),
    ),
    # 7. Price check with keywords
    ConversationScenario(
        name="price_check_with_keywords",
        description="LLM requests get_price_range with category and keywords",
        initial_history=[
            {"role": "user", "content": "I want to sell my 2019 Honda Civic"},
        ],
        turns=[
            Turn(
                llm_response=LLMResponse(
                    tool_calls=[{
                        "function": {
                            "name": "get_price_range",
                            "arguments": {
                                "category": "vehicles",
                                "keywords": "Honda Civic 2019",
                            },
                        }
                    }],
                ),
            ),
        ],
        expected=ExpectedOutcome(
            final_action="tool_call",
            tools_called=[
                ("get_price_range", {"category": "vehicles", "keywords": "Honda Civic 2019"})
            ],
        ),
    ),
]

# ---------------------------------------------------------------------------
# Chat_turn-level scenarios (verify full ReAct loop)
# ---------------------------------------------------------------------------

CHAT_TURN_SCENARIOS = [
    # 8. Two sequential tools then ask
    ConversationScenario(
        name="two_sequential_tools",
        description="search_listings → get_price_range → ask (order verified)",
        initial_history=[
            {"role": "user", "content": "I want to buy a used mountain bike"},
        ],
        turns=[
            Turn(
                converse_result={
                    "action": "tool_call",
                    "tool": "search_listings",
                    "args": {"category": "sports", "keywords": "mountain bike"},
                },
                tool_result=ToolResult(
                    tool_name="search_listings",
                    args={"category": "sports", "keywords": "mountain bike"},
                    result="Found 3 active listing(s) in 'sports'. Top matches:\n  1) [sell] Used Trek mountain bike",
                ),
            ),
            Turn(
                converse_result={
                    "action": "tool_call",
                    "tool": "get_price_range",
                    "args": {"category": "sports", "keywords": "mountain bike"},
                },
                tool_result=ToolResult(
                    tool_name="get_price_range",
                    args={"category": "sports", "keywords": "mountain bike"},
                    result="Found 3 similar listing(s). Price range: $200\u2013$800. Most common: ~$450.",
                ),
            ),
            Turn(
                converse_result={
                    "action": "ask",
                    "message": "I found some mountain bikes listed between $200 and $800. What's your budget?",
                },
            ),
        ],
        expected=ExpectedOutcome(
            final_action="ask",
            message_contains=["budget"],
            tools_used_count=2,
            tool_call_order=["search_listings", "get_price_range"],
            query_id_present=False,
        ),
    ),
    # 9. Tool returns no results → graceful continue
    ConversationScenario(
        name="tool_returns_no_results",
        description="Tool returns no listings → LLM continues gracefully",
        initial_history=[
            {"role": "user", "content": "I want to buy a vintage typewriter"},
        ],
        turns=[
            Turn(
                converse_result={
                    "action": "tool_call",
                    "tool": "search_listings",
                    "args": {"category": "antiques", "keywords": "typewriter"},
                },
                tool_result=ToolResult(
                    tool_name="search_listings",
                    args={"category": "antiques", "keywords": "typewriter"},
                    result="No active listings found in 'antiques'.",
                ),
            ),
            Turn(
                converse_result={
                    "action": "ask",
                    "message": "There aren't any typewriter listings right now. What brand or era are you looking for?",
                },
            ),
        ],
        expected=ExpectedOutcome(
            final_action="ask",
            message_contains=["typewriter"],
            tools_used_count=1,
            tool_call_order=["search_listings"],
        ),
    ),
    # 10. count_by_category exploration
    ConversationScenario(
        name="count_by_category_exploration",
        description="count_by_category → ask about specific category",
        initial_history=[
            {"role": "user", "content": "I want to buy something, what's available?"},
        ],
        turns=[
            Turn(
                converse_result={
                    "action": "tool_call",
                    "tool": "count_by_category",
                    "args": {},
                },
                tool_result=ToolResult(
                    tool_name="count_by_category",
                    args={},
                    result="Active listings by category: electronics (12), vehicles (8), furniture (5).",
                ),
            ),
            Turn(
                converse_result={
                    "action": "ask",
                    "message": "Here's what's available: electronics (12), vehicles (8), and furniture (5). Which category interests you?",
                },
            ),
        ],
        expected=ExpectedOutcome(
            final_action="ask",
            message_contains=["electronics", "vehicles"],
            tools_used_count=1,
            tool_call_order=["count_by_category"],
        ),
    ),
]
