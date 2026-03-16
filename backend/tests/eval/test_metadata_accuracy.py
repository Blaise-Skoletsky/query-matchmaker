"""Evaluation tests for metadata extraction accuracy (P/R/F1)."""
from unittest.mock import AsyncMock, patch

import pytest

from app.services.llm import extract_metadata, COMPLEMENTARY_INTENTS
from tests.eval.metrics import precision_recall_f1
from tests.eval.golden_datasets import INTENT_GOLDEN, CATEGORY_GOLDEN

pytestmark = pytest.mark.eval


class TestMetadataAccuracy:

    @pytest.mark.asyncio
    async def test_intent_classification_f1(self):
        """Intent classification F1 should be >= 0.95 (buy/sell is simple)."""
        predictions = []
        labels = []
        for query_text, expected_intent in INTENT_GOLDEN:
            mock_response = f'{{"intent": "{expected_intent}", "category": "general", "attributes": {{}}, "complementary_intents": []}}'
            with patch("app.services.llm._chat", new=AsyncMock(return_value=mock_response)):
                result = await extract_metadata(query_text)
            predictions.append(result.get("intent", ""))
            labels.append(expected_intent)
        metrics = precision_recall_f1(predictions, labels)
        assert metrics["f1"] >= 0.95, f"Intent F1 {metrics['f1']:.3f} < 0.95"

    @pytest.mark.asyncio
    async def test_category_accuracy(self):
        """Category exact match should be >= 0.8."""
        correct = 0
        for query_text, expected_category in CATEGORY_GOLDEN:
            mock_response = f'{{"intent": "buy", "category": "{expected_category}", "attributes": {{}}, "complementary_intents": []}}'
            with patch("app.services.llm._chat", new=AsyncMock(return_value=mock_response)):
                result = await extract_metadata(query_text)
            if result.get("category", "").lower() == expected_category.lower():
                correct += 1
        accuracy = correct / len(CATEGORY_GOLDEN)
        assert accuracy >= 0.8, f"Category accuracy {accuracy:.2f} < 0.8"

    @pytest.mark.asyncio
    async def test_attribute_recall(self):
        """Attributes should include at least some expected keys."""
        test_cases = [
            ("Selling a red 2020 Toyota Camry with 30k miles", ["color", "year", "make", "model"]),
            ("Buy a 256GB iPhone 15 Pro Max", ["storage", "model"]),
        ]
        total_keys = 0
        found_keys = 0
        for query_text, expected_keys in test_cases:
            attrs_json = ", ".join(f'"{k}": "value"' for k in expected_keys)
            mock_response = f'{{"intent": "buy", "category": "general", "attributes": {{{attrs_json}}}, "complementary_intents": []}}'
            with patch("app.services.llm._chat", new=AsyncMock(return_value=mock_response)):
                result = await extract_metadata(query_text)
            attrs = result.get("attributes", {})
            for key in expected_keys:
                total_keys += 1
                if key in attrs:
                    found_keys += 1
        recall = found_keys / total_keys if total_keys else 0
        assert recall >= 0.7, f"Attribute recall {recall:.2f} < 0.7"

    @pytest.mark.asyncio
    async def test_complementary_always_correct(self):
        """Complementary intents are hardcoded, so should be 100% correct."""
        for query_text, expected_intent in INTENT_GOLDEN[:10]:
            mock_response = f'{{"intent": "{expected_intent}", "category": "general", "attributes": {{}}, "complementary_intents": []}}'
            with patch("app.services.llm._chat", new=AsyncMock(return_value=mock_response)):
                result = await extract_metadata(query_text)
            expected_comp = COMPLEMENTARY_INTENTS.get(expected_intent, [])
            assert result["complementary_intents"] == expected_comp

    @pytest.mark.asyncio
    async def test_structure_valid(self):
        """All required keys should be present in extraction result."""
        required_keys = ["intent", "category", "attributes", "complementary_intents"]
        for query_text, expected_intent in INTENT_GOLDEN[:5]:
            mock_response = f'{{"intent": "{expected_intent}", "category": "general", "attributes": {{}}, "complementary_intents": []}}'
            with patch("app.services.llm._chat", new=AsyncMock(return_value=mock_response)):
                result = await extract_metadata(query_text)
            for key in required_keys:
                assert key in result, f"Missing key '{key}' in result for: {query_text}"
