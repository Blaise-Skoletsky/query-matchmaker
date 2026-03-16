"""Parametrized conversation scenario tests.

Add new scenarios to the files in tests/scenarios/ — they're picked up
automatically by pytest parametrize.
"""

import pytest

from tests.scenario_harness import run_chat_turn_scenario, run_converse_scenario
from tests.scenarios.basic_flow import SCENARIOS as BASIC_FLOW
from tests.scenarios.tool_calls import CHAT_TURN_SCENARIOS as TOOL_CHAT_TURN
from tests.scenarios.tool_calls import CONVERSE_SCENARIOS as TOOL_CONVERSE
from tests.scenarios.guardrails import SCENARIOS as GUARDRAILS
from tests.scenarios.offensive_content import SCENARIOS as OFFENSIVE
from tests.scenarios.edge_cases import SCENARIOS as EDGE_CASES

ALL_CONVERSE = BASIC_FLOW + TOOL_CONVERSE + OFFENSIVE + EDGE_CASES
ALL_CHAT_TURN = TOOL_CHAT_TURN + GUARDRAILS


@pytest.mark.asyncio
@pytest.mark.parametrize("scenario", ALL_CONVERSE, ids=lambda s: s.name)
async def test_converse_scenario(scenario):
    await run_converse_scenario(scenario)


@pytest.mark.asyncio
@pytest.mark.parametrize("scenario", ALL_CHAT_TURN, ids=lambda s: s.name)
async def test_chat_turn_scenario(scenario):
    await run_chat_turn_scenario(scenario)
