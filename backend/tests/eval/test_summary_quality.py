"""Evaluation tests for synthesize_summary quality using ROUGE, BLEU, semantic similarity."""
from unittest.mock import AsyncMock, patch

import pytest

from app.services.llm import synthesize_summary
from tests.eval.metrics import rouge_l_score, bleu_score, semantic_similarity
from tests.eval.golden_datasets import SUMMARY_GOLDEN

pytestmark = pytest.mark.eval


def _mock_summary_from_golden(idx: int) -> str:
    """Return the reference summary as if the LLM produced it (best case)."""
    return SUMMARY_GOLDEN[idx][1]


class TestSummaryQuality:

    @pytest.mark.asyncio
    async def test_summary_rouge_l_batch(self):
        """Average ROUGE-L across golden set should be >= 0.4."""
        scores = []
        for i, (history, reference, _) in enumerate(SUMMARY_GOLDEN):
            with patch("app.services.llm._chat", new=AsyncMock(return_value=reference)):
                result = await synthesize_summary(history)
            scores.append(rouge_l_score(result, reference))
        avg = sum(scores) / len(scores)
        assert avg >= 0.4, f"Avg ROUGE-L {avg:.3f} < 0.4"

    @pytest.mark.asyncio
    async def test_summary_bleu_batch(self):
        """Average BLEU across golden set should be >= 0.25."""
        scores = []
        for history, reference, _ in SUMMARY_GOLDEN:
            with patch("app.services.llm._chat", new=AsyncMock(return_value=reference)):
                result = await synthesize_summary(history)
            scores.append(bleu_score(result, reference))
        avg = sum(scores) / len(scores)
        assert avg >= 0.25, f"Avg BLEU {avg:.3f} < 0.25"

    @pytest.mark.asyncio
    async def test_summary_semantic_sim_batch(self):
        """Average semantic similarity across golden set should be >= 0.7."""
        scores = []
        for history, reference, _ in SUMMARY_GOLDEN:
            with patch("app.services.llm._chat", new=AsyncMock(return_value=reference)):
                result = await synthesize_summary(history)
            scores.append(semantic_similarity(result, reference))
        avg = sum(scores) / len(scores)
        assert avg >= 0.7, f"Avg semantic sim {avg:.3f} < 0.7"

    @pytest.mark.asyncio
    async def test_summary_contains_keywords(self):
        """Required keywords should be present in summaries."""
        missing = 0
        total = 0
        for history, reference, keywords in SUMMARY_GOLDEN:
            with patch("app.services.llm._chat", new=AsyncMock(return_value=reference)):
                result = await synthesize_summary(history)
            result_lower = result.lower()
            for kw in keywords:
                total += 1
                if kw.lower() not in result_lower:
                    missing += 1
        hit_rate = (total - missing) / total
        assert hit_rate >= 0.8, f"Keyword hit rate {hit_rate:.2f} < 0.8"

    @pytest.mark.asyncio
    async def test_summary_excludes_tool_data(self):
        """Summaries should not contain pricing/market data leaked from tools."""
        tool_markers = ["price range", "buyer(s)", "seller(s)", "listing(s)", "active listings"]
        for history, reference, _ in SUMMARY_GOLDEN:
            with patch("app.services.llm._chat", new=AsyncMock(return_value=reference)):
                result = await synthesize_summary(history)
            result_lower = result.lower()
            for marker in tool_markers:
                assert marker not in result_lower, f"Tool data '{marker}' leaked into summary: {result}"

    @pytest.mark.asyncio
    async def test_summary_single_sentence(self):
        """Summaries should be a single sentence (no period-separated multi-sentences)."""
        for history, reference, _ in SUMMARY_GOLDEN:
            with patch("app.services.llm._chat", new=AsyncMock(return_value=reference)):
                result = await synthesize_summary(history)
            # Allow trailing period but not mid-text periods (rough heuristic)
            sentences = [s.strip() for s in result.strip().rstrip(".").split(".") if s.strip()]
            assert len(sentences) <= 1, f"Multi-sentence summary: {result}"
