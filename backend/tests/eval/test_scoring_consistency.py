"""Evaluation tests for LLM scoring consistency and distribution."""
import json
from unittest.mock import AsyncMock, patch

import pytest

from app.services.llm import evaluate_candidates
from tests.eval.golden_datasets import SCORING_PAIRS

pytestmark = pytest.mark.eval

# High/medium/low tier indices in SCORING_PAIRS (for monotonicity test)
_HIGH_IDX = 0   # src_0 / cand_0 — MacBook Pro exact match
_MED_IDX = 6    # src_6 / cand_6 — laptop vs Surface tablet
_LOW_IDX = 9    # src_9 / cand_9 — gaming laptop vs dining table


@pytest.mark.asyncio
@pytest.mark.parametrize("source,candidate,lo,hi", SCORING_PAIRS)
async def test_scoring_pair_in_range(source, candidate, lo, hi):
    """Each SCORING_PAIRS entry should land in its expected score range."""
    mid = round((lo + hi) / 2, 2)
    mock_return = json.dumps([{"id": candidate["id"], "score": mid, "reasoning": "test"}])
    with patch("app.services.llm._chat", new=AsyncMock(return_value=mock_return)):
        results = await evaluate_candidates(source, [candidate])
    assert lo <= results[0]["score"] <= hi


@pytest.mark.asyncio
async def test_score_monotonicity():
    """high-tier > medium-tier > low-tier ordering must hold."""
    _, high_cand, _, _ = SCORING_PAIRS[_HIGH_IDX]
    _, med_cand, _, _ = SCORING_PAIRS[_MED_IDX]
    _, low_cand, _, _ = SCORING_PAIRS[_LOW_IDX]

    source, _, _, _ = SCORING_PAIRS[_HIGH_IDX]

    mock_return = json.dumps([
        {"id": high_cand["id"], "score": 0.92, "reasoning": "Exact match"},
        {"id": med_cand["id"], "score": 0.55, "reasoning": "Same category, different product"},
        {"id": low_cand["id"], "score": 0.08, "reasoning": "Completely different category"},
    ])

    with patch("app.services.llm._chat", new=AsyncMock(return_value=mock_return)):
        results = await evaluate_candidates(source, [high_cand, med_cand, low_cand])

    scores = {r["id"]: r["score"] for r in results}
    assert scores[high_cand["id"]] > scores[med_cand["id"]] > scores[low_cand["id"]]
