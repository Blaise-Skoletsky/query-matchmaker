"""Unit tests for llm.py — fully mocked, no Ollama required."""
import pytest
from unittest.mock import AsyncMock, patch

from app.services.llm import extract_metadata, evaluate_candidates


class TestComplementaryIntents:
    """Complementary intents are hardcoded post-LLM — verify the override."""

    async def _call_with_intent(self, intent: str) -> dict:
        llm_response = f'{{"intent": "{intent}", "category": "goods", "attributes": {{}}, "complementary_intents": ["{intent}"], "required_match_attributes": [], "preferred_match_attributes": []}}'
        with patch("app.services.llm._chat", new=AsyncMock(return_value=llm_response)):
            return await extract_metadata("test query")

    @pytest.mark.asyncio
    async def test_sell_query_gets_buy_complementary(self):
        result = await self._call_with_intent("sell")
        assert result["complementary_intents"] == ["buy"]

    @pytest.mark.asyncio
    async def test_buy_query_gets_sell_complementary(self):
        result = await self._call_with_intent("buy")
        assert result["complementary_intents"] == ["sell"]

    @pytest.mark.asyncio
    async def test_sell_never_gets_sell_complementary(self):
        result = await self._call_with_intent("sell")
        assert "sell" not in result["complementary_intents"]

    @pytest.mark.asyncio
    async def test_buy_never_gets_buy_complementary(self):
        result = await self._call_with_intent("buy")
        assert "buy" not in result["complementary_intents"]


class TestEvaluateCandidatesEdgeCases:

    @pytest.mark.asyncio
    async def test_empty_candidates_returns_empty(self):
        source = {
            "id": "src-1",
            "intent": "buy",
            "raw_text": "I want to buy a bike",
            "attributes": {},
            "required_match_attributes": [],
            "preferred_match_attributes": [],
        }
        results = await evaluate_candidates(source, [])
        assert results == []
