import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest


def pytest_collection_modifyitems(config, items):
    """Auto-skip integration tests when Ollama is unavailable."""
    for item in items:
        if item.get_closest_marker("asyncio") is None:
            if hasattr(item, "function") and hasattr(item.function, "__wrapped__"):
                item.add_marker(pytest.mark.asyncio)


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def fake_user_id():
    return uuid.uuid4()


@pytest.fixture
def mock_db():
    """AsyncSession mock with common methods pre-configured."""
    db = AsyncMock()
    db.commit = AsyncMock()
    db.flush = AsyncMock()
    db.add = MagicMock()
    db.refresh = AsyncMock()
    db.get = AsyncMock(return_value=None)
    return db


def _make_query(
    raw_text="Test item",
    intent="sell",
    category="electronics",
    embedding=None,
    attributes=None,
    user_id=None,
    status="active",
    complementary_intents=None,
    required_match_attributes=None,
    preferred_match_attributes=None,
    match_trace=None,
    created_at=None,
):
    q = MagicMock()
    q.id = uuid.uuid4()
    q.raw_text = raw_text
    q.intent = intent
    q.category = category
    q.embedding = embedding
    q.created_at = created_at
    q.attributes = attributes
    q.user_id = user_id or uuid.uuid4()
    q.status = status
    q.complementary_intents = complementary_intents
    q.required_match_attributes = required_match_attributes
    q.preferred_match_attributes = preferred_match_attributes
    q.match_trace = match_trace
    return q


def _make_match(
    status="pending",
    chatroom_id=None,
    compatibility_score=0.85,
    reasoning="Good match",
    match_queries=None,
):
    m = MagicMock()
    m.id = uuid.uuid4()
    m.status = status
    m.chatroom_id = chatroom_id
    m.compatibility_score = compatibility_score
    m.reasoning = reasoning
    m.match_queries = match_queries or []
    return m


@pytest.fixture
def make_query():
    return _make_query


@pytest.fixture
def make_match():
    return _make_match
