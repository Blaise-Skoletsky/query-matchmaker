"""Edge case conversation scenarios (converse-level)."""

from tests.scenario_harness import (
    ConversationScenario,
    ExpectedOutcome,
    LLMResponse,
    Turn,
)

SCENARIOS = [
    # Empty input → fallback ask
    ConversationScenario(
        name="empty_input_fallback",
        description="Empty or whitespace input → fallback ask",
        initial_history=[{"role": "user", "content": "   "}],
        turns=[
            Turn(
                llm_response=LLMResponse(
                    content='{"action": "ask", "message": "What would you like to buy or sell?"}'
                ),
            ),
        ],
        expected=ExpectedOutcome(
            final_action="ask",
            message_contains=["buy or sell"],
        ),
    ),
    # Very long input → still processes
    ConversationScenario(
        name="very_long_input_processed",
        description="2000 char input → still processes normally",
        initial_history=[{"role": "user", "content": "I want to buy a laptop " + "with great specs " * 100}],
        turns=[
            Turn(
                llm_response=LLMResponse(
                    content='{"action": "ask", "message": "What specific laptop model are you looking for?"}'
                ),
            ),
        ],
        expected=ExpectedOutcome(
            final_action="ask",
            message_contains=["laptop"],
        ),
    ),
    # Unicode input → treated normally
    ConversationScenario(
        name="unicode_input",
        description="Non-ASCII input → treated normally",
        initial_history=[{"role": "user", "content": "買いたい MacBook Pro"}],
        turns=[
            Turn(
                llm_response=LLMResponse(
                    content='{"action": "ask", "message": "Are you looking to buy a MacBook Pro? What specifications do you need?"}'
                ),
            ),
        ],
        expected=ExpectedOutcome(
            final_action="ask",
            message_contains=["macbook"],
        ),
    ),
    # Multiple items in single query → ask to clarify
    ConversationScenario(
        name="multiple_items_single_query",
        description="Multiple items → ask which one to focus on",
        initial_history=[{"role": "user", "content": "I want to buy a laptop and a phone and a tablet"}],
        turns=[
            Turn(
                llm_response=LLMResponse(
                    content='{"action": "ask", "message": "I can help with one item at a time. Which would you like to start with - the laptop, phone, or tablet?"}'
                ),
            ),
        ],
        expected=ExpectedOutcome(
            final_action="ask",
            message_contains=["laptop"],
        ),
    ),
]
