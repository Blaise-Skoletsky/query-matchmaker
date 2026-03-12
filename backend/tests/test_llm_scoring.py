"""
Tests for LLM compatibility scoring (buy/sell only).

Each test has a clear intent: SHOULD match (score >= 0.7) or SHOULD NOT match (score < 0.7).
These call Ollama directly -- requires the server to be running.
"""

import pytest
from app.services.llm import evaluate_candidates

THRESHOLD = 0.7


def src(intent, text, attributes=None, required=None, preferred=None):
    return {
        "id": "source",
        "intent": intent,
        "raw_text": text,
        "attributes": attributes or {},
        "required_match_attributes": required or [],
        "preferred_match_attributes": preferred or [],
    }


def cand(id, intent, text, attributes=None):
    return {"id": id, "intent": intent, "raw_text": text, "attributes": attributes or {}}


def score_of(results, id="c1"):
    return next(r["score"] for r in results if r["id"] == id)


# ---------------------------------------------------------------------------
# Should match (score >= 0.7)
# ---------------------------------------------------------------------------

class TestShouldMatch:

    @pytest.mark.asyncio
    async def test_buy_sell_macbook_pro_exact(self):
        """Buyer and seller for the exact same product should match."""
        results = await evaluate_candidates(
            src("buy", "I want to buy a MacBook Pro", {"model": "macbook pro"}),
            [cand("c1", "sell", "I want to sell a MacBook Pro", {"model": "macbook pro"})],
        )
        assert score_of(results) >= THRESHOLD, f"Expected >= {THRESHOLD}, got {score_of(results)}"

    @pytest.mark.asyncio
    async def test_buy_sell_iphone_same_model(self):
        """Buyer and seller for the same iPhone model should match."""
        results = await evaluate_candidates(
            src("buy", "Looking to buy an iPhone 15 Pro Max", {"model": "iPhone 15 Pro Max"}),
            [cand("c1", "sell", "Selling my iPhone 15 Pro Max, 256GB", {"model": "iPhone 15 Pro Max", "storage": "256GB"})],
        )
        assert score_of(results) >= THRESHOLD, f"Expected >= {THRESHOLD}, got {score_of(results)}"

    @pytest.mark.asyncio
    async def test_buy_sell_toyota_camry(self):
        """Buyer and seller for the same car model should match."""
        results = await evaluate_candidates(
            src("buy", "Want to buy a Toyota Camry", {"make": "Toyota", "model": "Camry"}),
            [cand("c1", "sell", "Selling my 2021 Toyota Camry, low miles", {"make": "Toyota", "model": "Camry", "year": "2021"})],
        )
        assert score_of(results) >= THRESHOLD, f"Expected >= {THRESHOLD}, got {score_of(results)}"

    @pytest.mark.asyncio
    async def test_buy_sell_generic_laptop(self):
        """Generic laptop buyer should match a laptop seller."""
        results = await evaluate_candidates(
            src("buy", "I need a laptop for work", {"type": "laptop"}),
            [cand("c1", "sell", "Selling a Dell XPS 15 laptop, great condition", {"type": "laptop", "brand": "Dell"})],
        )
        assert score_of(results) >= THRESHOLD, f"Expected >= {THRESHOLD}, got {score_of(results)}"

    @pytest.mark.asyncio
    async def test_buy_sell_furniture_synonym(self):
        """Couch and sofa are synonyms — should match."""
        results = await evaluate_candidates(
            src("buy", "Looking for a couch for my living room", {"type": "couch"}),
            [cand("c1", "sell", "Selling a leather sofa, seats 3", {"type": "sofa"})],
        )
        assert score_of(results) >= THRESHOLD, f"Expected >= {THRESHOLD}, got {score_of(results)}"

    @pytest.mark.asyncio
    async def test_buy_sell_gaming_console_name_variation(self):
        """PS5 and PlayStation 5 are the same product."""
        results = await evaluate_candidates(
            src("buy", "Want to buy a PS5", {"type": "gaming console", "model": "PS5"}),
            [cand("c1", "sell", "Selling PlayStation 5 with two controllers", {"type": "gaming console", "model": "PlayStation 5"})],
        )
        assert score_of(results) >= THRESHOLD, f"Expected >= {THRESHOLD}, got {score_of(results)}"

    @pytest.mark.asyncio
    async def test_buy_sell_road_bike(self):
        """Buyer and seller for the same type of bike should match."""
        results = await evaluate_candidates(
            src("buy", "Looking to buy a road bike, any brand", {"type": "road bike"}),
            [cand("c1", "sell", "Selling my road bike, barely used", {"type": "road bike"})],
        )
        assert score_of(results) >= THRESHOLD, f"Expected >= {THRESHOLD}, got {score_of(results)}"


# ---------------------------------------------------------------------------
# Should NOT match (score < 0.7)
# ---------------------------------------------------------------------------

class TestShouldNotMatch:

    @pytest.mark.asyncio
    async def test_toys_vs_apples(self):
        """Toys and apples are completely different categories — regression test."""
        results = await evaluate_candidates(
            src("buy", "I want to buy toys for my kids", {"category": "toys"}),
            [cand("c1", "sell", "Selling honey crisp apples, fresh picked", {"category": "food", "product": "apples"})],
        )
        assert score_of(results) < THRESHOLD, f"Expected < {THRESHOLD}, got {score_of(results)}"

    @pytest.mark.asyncio
    async def test_electronics_vs_food(self):
        """Laptop and cookies are completely different categories."""
        results = await evaluate_candidates(
            src("buy", "I want to buy a laptop", {"type": "laptop"}),
            [cand("c1", "sell", "Selling homemade cookies, dozen for $15", {"category": "food", "product": "cookies"})],
        )
        assert score_of(results) < THRESHOLD, f"Expected < {THRESHOLD}, got {score_of(results)}"

    @pytest.mark.asyncio
    async def test_clothing_vs_furniture(self):
        """Jacket and dining table are different categories."""
        results = await evaluate_candidates(
            src("buy", "Looking for a winter jacket, size L", {"type": "jacket", "size": "L"}),
            [cand("c1", "sell", "Selling a dining table, seats 6", {"type": "dining table"})],
        )
        assert score_of(results) < THRESHOLD, f"Expected < {THRESHOLD}, got {score_of(results)}"

    @pytest.mark.asyncio
    async def test_car_vs_bicycle(self):
        """Car and bicycle are different transport categories."""
        results = await evaluate_candidates(
            src("buy", "Want to buy a sedan, preferably Honda", {"type": "car", "make": "Honda"}),
            [cand("c1", "sell", "Selling a mountain bicycle, 21-speed", {"type": "bicycle"})],
        )
        assert score_of(results) < THRESHOLD, f"Expected < {THRESHOLD}, got {score_of(results)}"

    @pytest.mark.asyncio
    async def test_phone_vs_tv(self):
        """Phone and TV — both electronics but different products."""
        results = await evaluate_candidates(
            src("buy", "Want to buy an iPhone 15", {"type": "phone", "model": "iPhone 15"}),
            [cand("c1", "sell", "Selling a 65-inch Samsung TV", {"type": "tv", "brand": "Samsung"})],
        )
        assert score_of(results) < THRESHOLD, f"Expected < {THRESHOLD}, got {score_of(results)}"

    @pytest.mark.asyncio
    async def test_specific_brand_size_mismatch(self):
        """Nike size 10 vs Adidas size 8 — brand and size both differ."""
        results = await evaluate_candidates(
            src("buy", "Looking for Nike Air Max size 10", {"brand": "Nike", "model": "Air Max", "size": "10"}, required=["brand", "size"]),
            [cand("c1", "sell", "Selling Adidas Ultraboost size 8", {"brand": "Adidas", "model": "Ultraboost", "size": "8"})],
        )
        assert score_of(results) < THRESHOLD, f"Expected < {THRESHOLD}, got {score_of(results)}"

    @pytest.mark.asyncio
    async def test_macbook_vs_iphone(self):
        """Buyer wanting a MacBook should not match seller offering an iPhone."""
        results = await evaluate_candidates(
            src("buy", "I want to buy a MacBook Pro", {"model": "macbook pro"}),
            [cand("c1", "sell", "I want to sell an iPhone 15 Pro", {"model": "iphone 15 pro"})],
        )
        assert score_of(results) < THRESHOLD, f"Expected < {THRESHOLD}, got {score_of(results)}"


# ---------------------------------------------------------------------------
# Multiple candidates — should rank correctly
# ---------------------------------------------------------------------------

class TestMultipleCandidates:

    @pytest.mark.asyncio
    async def test_best_candidate_ranks_highest(self):
        """Given a perfect match and a weak match, the perfect one should score higher."""
        results = await evaluate_candidates(
            src("buy", "I want to buy a Canon EOS R5 camera", {"brand": "Canon", "model": "EOS R5"}),
            [
                cand("good", "sell", "Selling my Canon EOS R5, mint condition with box", {"brand": "Canon", "model": "EOS R5"}),
                cand("weak", "sell", "Selling a Nikon D3500 starter camera", {"brand": "Nikon", "model": "D3500"}),
            ],
        )
        good_score = score_of(results, "good")
        weak_score = score_of(results, "weak")
        assert good_score > weak_score, f"Expected good ({good_score}) > weak ({weak_score})"
        assert good_score >= THRESHOLD

    @pytest.mark.asyncio
    async def test_three_candidates_camera_ranking(self):
        """Three camera candidates with varying relevance should be ordered by score."""
        results = await evaluate_candidates(
            src("buy", "I want to buy a Canon EOS R5 mirrorless camera", {"brand": "Canon", "model": "EOS R5", "type": "mirrorless"}),
            [
                cand("exact", "sell", "Selling Canon EOS R5 mirrorless, like new with box", {"brand": "Canon", "model": "EOS R5", "type": "mirrorless"}),
                cand("partial", "sell", "Selling Canon EOS R6, good condition", {"brand": "Canon", "model": "EOS R6", "type": "mirrorless"}),
                cand("wrong", "sell", "Selling a GoPro Hero 11 action camera", {"brand": "GoPro", "model": "Hero 11", "type": "action camera"}),
            ],
        )
        exact = score_of(results, "exact")
        partial = score_of(results, "partial")
        wrong = score_of(results, "wrong")
        assert exact > partial > wrong, f"Expected exact ({exact}) > partial ({partial}) > wrong ({wrong})"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------

class TestEdgeCases:

    @pytest.mark.asyncio
    async def test_empty_candidates_returns_empty(self):
        """Empty candidate list should return empty results."""
        results = await evaluate_candidates(
            src("buy", "I want to buy a laptop"),
            [],
        )
        assert results == []

    @pytest.mark.asyncio
    async def test_missing_attributes_still_scores(self):
        """Candidates with no attributes should still get a score based on text."""
        results = await evaluate_candidates(
            src("sell", "Selling a vintage 1960s Fender Stratocaster guitar", {"type": "guitar", "brand": "Fender", "era": "1960s"}),
            [cand("c1", "buy", "Looking to buy a vintage Fender guitar", {})],
        )
        assert isinstance(score_of(results), float)
        assert 0.0 <= score_of(results) <= 1.0

    @pytest.mark.asyncio
    async def test_vague_buy_vs_specific_sell(self):
        """Vague 'kitchen item' buyer vs specific KitchenAid mixer seller — broad category overlap."""
        results = await evaluate_candidates(
            src("buy", "Looking for kitchen items", {"category": "kitchen"}),
            [cand("c1", "sell", "Selling a KitchenAid stand mixer, barely used", {"brand": "KitchenAid", "type": "stand mixer"})],
        )
        assert isinstance(score_of(results), float)
        assert 0.0 <= score_of(results) <= 1.0

    @pytest.mark.asyncio
    async def test_required_attribute_contradiction(self):
        """New sealed vs refurbished — contradicting condition should lower score."""
        results = await evaluate_candidates(
            src("buy", "Want to buy a new sealed AirPods Pro", {"product": "AirPods Pro", "condition": "new sealed"}, required=["condition"]),
            [cand("c1", "sell", "Selling refurbished AirPods Pro, works fine", {"product": "AirPods Pro", "condition": "refurbished"})],
        )
        assert score_of(results) < THRESHOLD, f"Expected < {THRESHOLD}, got {score_of(results)}"

    @pytest.mark.asyncio
    async def test_same_product_different_condition_still_matches(self):
        """Same product with different (non-contradicting) conditions should still match."""
        results = await evaluate_candidates(
            src("buy", "Want to buy AirPods Pro", {"product": "AirPods Pro"}),
            [cand("c1", "sell", "Selling AirPods Pro, used but great condition", {"product": "AirPods Pro", "condition": "used"})],
        )
        assert score_of(results) >= THRESHOLD, f"Expected >= {THRESHOLD}, got {score_of(results)}"
