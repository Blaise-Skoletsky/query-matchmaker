"""Offensive/inappropriate content handling scenarios (converse-level)."""

from tests.scenario_harness import (
    ConversationScenario,
    ExpectedOutcome,
    LLMResponse,
    Turn,
)

SCENARIOS = [
    # Offensive language → scope redirect
    ConversationScenario(
        name="offensive_language_scope_redirect",
        description="Slurs in query → LLM redirects within scope rules",
        initial_history=[{"role": "user", "content": "I want to buy some f***ing headphones you idiot"}],
        turns=[
            Turn(
                llm_response=LLMResponse(
                    content='{"action": "ask", "message": "I can help you find headphones! What brand or type are you looking for?"}'
                ),
            ),
        ],
        expected=ExpectedOutcome(
            final_action="ask",
            message_contains=["headphones"],
        ),
    ),
    # Illegal goods → scope redirect
    ConversationScenario(
        name="illegal_goods_scope_redirect",
        description="Request for illegal goods → LLM redirects, does not submit",
        initial_history=[{"role": "user", "content": "I want to buy drugs"}],
        turns=[
            Turn(
                llm_response=LLMResponse(
                    content='{"action": "ask", "message": "I can only help with legal marketplace items. Would you like to buy or sell something else?"}'
                ),
            ),
        ],
        expected=ExpectedOutcome(
            final_action="ask",
            message_contains=["legal"],
        ),
    ),
    # Spam/gibberish → treated as ask
    ConversationScenario(
        name="spam_gibberish_ask",
        description="Random characters → treated as ask for clarification",
        initial_history=[{"role": "user", "content": "asdfghjkl qwerty 12345"}],
        turns=[
            Turn(
                llm_response=LLMResponse(
                    content='{"action": "ask", "message": "I didn\'t quite understand that. What would you like to buy or sell?"}'
                ),
            ),
        ],
        expected=ExpectedOutcome(
            final_action="ask",
            message_contains=["buy or sell"],
        ),
    ),
    # PII in query → LLM asks without repeating PII
    ConversationScenario(
        name="pii_warning",
        description="Phone number in query → LLM asks without repeating PII",
        initial_history=[{"role": "user", "content": "Call me at 555-123-4567 I want to sell my car"}],
        turns=[
            Turn(
                llm_response=LLMResponse(
                    content='{"action": "ask", "message": "I can help you sell your car! What make, model, and year is it?"}'
                ),
            ),
        ],
        expected=ExpectedOutcome(
            final_action="ask",
            message_contains=["car"],
        ),
    ),
]
