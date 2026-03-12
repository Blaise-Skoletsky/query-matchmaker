"""
Tests for LLM metadata extraction.

Verifies that extract_metadata returns correct intents, categories, and
complementary intents for buy/sell queries.
Requires Ollama to be running.
"""

import pytest
from app.services.llm import extract_metadata


class TestIntentExtraction:

    @pytest.mark.asyncio
    async def test_buy_intent(self):
        result = await extract_metadata("I want to buy a used mountain bike")
        assert result["intent"] == "buy"
        assert "sell" in result["complementary_intents"]

    @pytest.mark.asyncio
    async def test_sell_intent(self):
        result = await extract_metadata("Selling my old couch, good condition, $200")
        assert result["intent"] == "sell"
        assert "buy" in result["complementary_intents"]

    @pytest.mark.asyncio
    async def test_ambiguous_defaults_to_buy(self):
        """Ambiguous query like 'I need a laptop' should default to buy."""
        result = await extract_metadata("I need a laptop for school")
        assert result["intent"] == "buy"

    @pytest.mark.asyncio
    async def test_selling_extracts_sell(self):
        """Explicit selling language should extract sell intent."""
        result = await extract_metadata("Getting rid of my old PS5, $300 OBO")
        assert result["intent"] == "sell"


class TestComplementaryIntentHardcoding:
    """Verify complementary_intents are always hardcoded correctly, regardless of LLM output."""

    @pytest.mark.asyncio
    async def test_sell_query_gets_buy_complementary(self):
        result = await extract_metadata("Sell apple")
        assert result["complementary_intents"] == ["buy"]

    @pytest.mark.asyncio
    async def test_buy_query_gets_sell_complementary(self):
        result = await extract_metadata("Buy stuffed animal")
        assert result["complementary_intents"] == ["sell"]

    @pytest.mark.asyncio
    async def test_sell_never_gets_sell_complementary(self):
        result = await extract_metadata("Selling my old laptop for cheap")
        assert "sell" not in result["complementary_intents"]
        assert result["complementary_intents"] == ["buy"]

    @pytest.mark.asyncio
    async def test_buy_never_gets_buy_complementary(self):
        result = await extract_metadata("Looking to buy a bicycle")
        assert "buy" not in result["complementary_intents"]
        assert result["complementary_intents"] == ["sell"]


class TestAttributeExtraction:

    @pytest.mark.asyncio
    async def test_extracts_product_attributes(self):
        result = await extract_metadata("Selling a red 2020 Toyota Camry with 30k miles")
        attrs = result.get("attributes", {})
        assert len(attrs) >= 2, f"Expected at least 2 attributes, got {attrs}"

    @pytest.mark.asyncio
    async def test_extracts_category(self):
        result = await extract_metadata("Looking for a used electric guitar, preferably Fender")
        assert result.get("category") is not None
        assert len(result["category"]) > 0

    @pytest.mark.asyncio
    async def test_returns_valid_structure(self):
        """All required fields should be present in the response."""
        result = await extract_metadata("I want to buy a Nintendo Switch")
        assert "intent" in result
        assert "category" in result
        assert "attributes" in result
        assert "complementary_intents" in result
        assert isinstance(result["complementary_intents"], list)
