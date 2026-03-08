"""
Tests for LLM metadata extraction.

Verifies that extract_metadata returns correct intents, categories, and
complementary intents for various query types.
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
    async def test_job_seek_intent(self):
        result = await extract_metadata("Python developer looking for remote work, 5 years experience")
        assert result["intent"] == "job_seek"
        assert "job_offer" in result["complementary_intents"]

    @pytest.mark.asyncio
    async def test_job_offer_intent(self):
        result = await extract_metadata("Hiring a data scientist for our AI startup, competitive salary")
        assert result["intent"] == "job_offer"
        assert "job_seek" in result["complementary_intents"]

    @pytest.mark.asyncio
    async def test_housing_seek_intent(self):
        result = await extract_metadata("Looking for a 1-bedroom apartment to rent near campus")
        assert result["intent"] == "housing_seek"
        assert "housing_offer" in result["complementary_intents"]

    @pytest.mark.asyncio
    async def test_service_offer_intent(self):
        result = await extract_metadata("Professional photographer available for weddings and events")
        assert result["intent"] == "service_offer"
        assert "service_seek" in result["complementary_intents"]


class TestAttributeExtraction:

    @pytest.mark.asyncio
    async def test_extracts_product_attributes(self):
        result = await extract_metadata("Selling a red 2020 Toyota Camry with 30k miles")
        attrs = result.get("attributes", {})
        # Should extract at least some of: color, year, make, model, mileage
        assert len(attrs) >= 2, f"Expected at least 2 attributes, got {attrs}"

    @pytest.mark.asyncio
    async def test_extracts_category(self):
        result = await extract_metadata("Looking for a used electric guitar, preferably Fender")
        assert result.get("category") is not None
        assert len(result["category"]) > 0

    @pytest.mark.asyncio
    async def test_returns_valid_structure(self):
        """All required fields should be present in the response."""
        result = await extract_metadata("Need a plumber to fix a leaky faucet this weekend")
        assert "intent" in result
        assert "category" in result
        assert "attributes" in result
        assert "complementary_intents" in result
        assert isinstance(result["complementary_intents"], list)
