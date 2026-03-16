"""Happy-path conversation scenarios (converse-level)."""

from tests.scenario_harness import (
    ConversationScenario,
    ExpectedOutcome,
    LLMResponse,
    Turn,
)

SCENARIOS = [
    # 1. Vague input → ask follow-up
    ConversationScenario(
        name="vague_input_asks_followup",
        description="A sparse first message should get an ask, not immediate submit",
        initial_history=[{"role": "user", "content": "I want to buy something"}],
        turns=[
            Turn(
                llm_response=LLMResponse(
                    content='{"action": "ask", "message": "What specifically are you looking to buy?"}'
                ),
            ),
        ],
        expected=ExpectedOutcome(
            final_action="ask",
            message_contains=["what"],
        ),
    ),
    # 2. Detailed input → submit directly
    ConversationScenario(
        name="detailed_input_submits_directly",
        description="A fully detailed message should submit immediately",
        initial_history=[
            {
                "role": "user",
                "content": "I want to buy a 2020 MacBook Pro 16-inch, good condition, under $1500",
            }
        ],
        turns=[
            Turn(
                llm_response=LLMResponse(
                    content='{"action": "submit", "summary": "I want to buy a 2020 MacBook Pro 16-inch in good condition under $1500."}'
                ),
            ),
        ],
        expected=ExpectedOutcome(
            final_action="submit",
            message_contains=["macbook", "1500"],
        ),
    ),
    # 3. Multi-turn converges to submit
    ConversationScenario(
        name="multi_turn_converges_to_submit",
        description="Three turns: vague → ask → answer → ask → answer → submit",
        initial_history=[{"role": "user", "content": "I want to buy a laptop"}],
        turns=[
            Turn(
                llm_response=LLMResponse(
                    content='{"action": "ask", "message": "What brand and model are you looking for?"}'
                ),
                user_reply="MacBook Pro, 16 inch",
            ),
            Turn(
                llm_response=LLMResponse(
                    content='{"action": "ask", "message": "What is your budget and preferred condition?"}'
                ),
                user_reply="Under $1500, good condition",
            ),
            Turn(
                llm_response=LLMResponse(
                    content='{"action": "submit", "summary": "I want to buy a MacBook Pro 16-inch in good condition under $1500."}'
                ),
            ),
        ],
        expected=ExpectedOutcome(
            final_action="submit",
            message_contains=["macbook", "1500"],
        ),
    ),
    # 4. "Doesn't matter" triggers early submit
    ConversationScenario(
        name="dont_care_triggers_early_submit",
        description="User says doesn't matter → early submit",
        initial_history=[
            {"role": "user", "content": "I want to sell my bike"},
            {"role": "assistant", "content": "What's the condition and asking price?"},
            {"role": "user", "content": "doesn't matter, just list it"},
        ],
        turns=[
            Turn(
                llm_response=LLMResponse(
                    content='{"action": "submit", "summary": "I want to sell my bike."}'
                ),
            ),
        ],
        expected=ExpectedOutcome(
            final_action="submit",
            message_contains=["sell", "bike"],
        ),
    ),
    # 5. Prose response treated as ask
    ConversationScenario(
        name="prose_response_treated_as_ask",
        description="LLM returns prose instead of JSON → treated as ask",
        initial_history=[{"role": "user", "content": "I want to buy a car"}],
        turns=[
            Turn(
                llm_response=LLMResponse(
                    content="What kind of car are you looking for? I can help you find the right one."
                ),
            ),
        ],
        expected=ExpectedOutcome(
            final_action="ask",
            message_contains=["car"],
        ),
    ),
]
