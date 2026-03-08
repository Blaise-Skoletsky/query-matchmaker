"""
Tests for LLM compatibility scoring.

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
# Should match
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
    async def test_job_offer_seek_software_engineer(self):
        """Job poster and job seeker with matching skills should match."""
        results = await evaluate_candidates(
            src("job_offer", "Hiring a Python backend engineer for a fintech startup", {"role": "backend engineer", "skill": "python"}),
            [cand("c1", "job_seek", "Python backend developer looking for a new role, 4 years experience", {"role": "backend engineer", "skill": "python"})],
        )
        assert score_of(results) >= THRESHOLD, f"Expected >= {THRESHOLD}, got {score_of(results)}"

    @pytest.mark.asyncio
    async def test_housing_offer_seek_room(self):
        """Landlord offering a room and someone seeking a room should match."""
        results = await evaluate_candidates(
            src("housing_offer", "Spare room available for rent in downtown Seattle, $900/month", {"type": "room", "location": "downtown Seattle"}),
            [cand("c1", "housing_seek", "Looking for a room to rent in downtown Seattle, budget $1000", {"type": "room", "location": "downtown Seattle"})],
        )
        assert score_of(results) >= THRESHOLD, f"Expected >= {THRESHOLD}, got {score_of(results)}"

    @pytest.mark.asyncio
    async def test_service_offer_seek_web_developer(self):
        """Freelance web developer and someone who needs a website should match."""
        results = await evaluate_candidates(
            src("service_seek", "Need a freelance developer to build a small e-commerce website", {"service": "web development"}),
            [cand("c1", "service_offer", "Freelance full-stack developer available for e-commerce and web projects", {"service": "web development"})],
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

    @pytest.mark.asyncio
    async def test_meetup_organizer_joiner_hiking(self):
        """Hiking group organizer and someone looking to join a hiking group should match."""
        results = await evaluate_candidates(
            src("event", "Organising a beginner hiking meetup this Saturday morning", {"activity": "hiking", "level": "beginner"}),
            [cand("c1", "meetup", "Looking to join a hiking group, I am a beginner", {"activity": "hiking", "level": "beginner"})],
        )
        assert score_of(results) >= THRESHOLD, f"Expected >= {THRESHOLD}, got {score_of(results)}"


# ---------------------------------------------------------------------------
# Should NOT match
# ---------------------------------------------------------------------------

class TestShouldNotMatch:

    @pytest.mark.asyncio
    async def test_macbook_pro_vs_old_macbook_air(self):
        """Buyer wanting a specific MacBook Pro 16-inch M3 should not match a 2015 MacBook Air."""
        results = await evaluate_candidates(
            src("buy", "I want to buy a MacBook Pro 16-inch with M3 chip, nothing else", {"model": "macbook pro 16-inch", "chip": "M3"}, required=["model", "chip"]),
            [cand("c1", "sell", "Selling a 2015 MacBook Air 11-inch, Intel i5, some wear", {"model": "macbook air", "chip": "Intel i5", "year": "2015"})],
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

    @pytest.mark.asyncio
    async def test_job_wrong_skill(self):
        """Job posting for a React frontend developer should not match a backend Python engineer."""
        results = await evaluate_candidates(
            src("job_offer", "Hiring a React frontend engineer", {"role": "frontend engineer", "skill": "react"}, required=["skill"]),
            [cand("c1", "job_seek", "Backend Python developer looking for work, no frontend experience", {"role": "backend engineer", "skill": "python"})],
        )
        assert score_of(results) < THRESHOLD, f"Expected < {THRESHOLD}, got {score_of(results)}"

    @pytest.mark.asyncio
    async def test_housing_rent_vs_buy(self):
        """Landlord renting a flat should not match someone trying to buy a property."""
        results = await evaluate_candidates(
            src("housing_offer", "One-bedroom flat available to rent, $1400/month", {"type": "flat", "transaction": "rent"}),
            [cand("c1", "housing_seek", "Looking to buy a two-bedroom apartment, have financing ready", {"type": "apartment", "transaction": "buy"})],
        )
        assert score_of(results) < THRESHOLD, f"Expected < {THRESHOLD}, got {score_of(results)}"

    @pytest.mark.asyncio
    async def test_hiking_vs_book_club(self):
        """Hiking meetup organiser should not match someone looking for a book club."""
        results = await evaluate_candidates(
            src("event", "Starting a weekend hiking club for outdoor enthusiasts", {"activity": "hiking"}),
            [cand("c1", "meetup", "Looking for a book club to join, love fiction", {"activity": "book club"})],
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
    async def test_three_candidates_ordered(self):
        """Three candidates with varying relevance should be ordered by score."""
        results = await evaluate_candidates(
            src("job_offer", "Hiring a senior React developer for a SaaS company", {"role": "frontend engineer", "skill": "react", "level": "senior"}),
            [
                cand("exact", "job_seek", "Senior React developer with 6 years of SaaS experience", {"role": "frontend engineer", "skill": "react", "level": "senior"}),
                cand("partial", "job_seek", "Junior React developer, 1 year experience", {"role": "frontend engineer", "skill": "react", "level": "junior"}),
                cand("wrong", "job_seek", "DevOps engineer specializing in AWS infrastructure", {"role": "devops engineer", "skill": "aws"}),
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
    async def test_required_attributes_contradicted_caps_score(self):
        """When a required attribute directly contradicts, score should be below threshold."""
        results = await evaluate_candidates(
            src(
                "buy",
                "Need a pet-friendly apartment, I have two large dogs, this is non-negotiable",
                {"location": "Manhattan", "pets": "two large dogs"},
                required=["pets"],
            ),
            [cand("c1", "housing_offer", "Luxury apartment in Manhattan, strictly no pets of any kind", {"location": "Manhattan", "pets": "absolutely not allowed"})],
        )
        assert score_of(results) < THRESHOLD, f"Expected < {THRESHOLD}, got {score_of(results)}"
