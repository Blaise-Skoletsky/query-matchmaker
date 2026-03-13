"""Tool registry for LLM agent tool use during conversations.

Implements the ReAct pattern: the LLM can call these tools mid-conversation
to ground its responses in live marketplace data.
"""

import logging
import re
import uuid

from sqlalchemy import select, func, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.query import Query
from app.services.embedding import embed_async

logger = logging.getLogger(__name__)


def _category_filter(category: str):
    """Build an OR filter that matches ANY word from category against category/raw_text."""
    words = re.split(r'[\s_]+', category.strip())
    words = [w for w in words if len(w) >= 3]  # skip tiny words like "a", "of"
    if not words:
        return or_(
            Query.category.ilike(f"%{category}%"),
            Query.raw_text.ilike(f"%{category}%"),
        )
    conditions = []
    for word in words:
        conditions.append(Query.category.ilike(f"%{word}%"))
        conditions.append(Query.raw_text.ilike(f"%{word}%"))
    return or_(*conditions)


async def search_listings(
    db: AsyncSession, user_id: uuid.UUID, category: str, keywords: str | None = None
) -> str:
    """Search active marketplace listings by category/keywords, excluding the current user."""
    stmt = select(Query).where(
        and_(
            Query.status == "active",
            _category_filter(category),
            Query.user_id != user_id,
        )
    )

    if keywords:
        keyword_embedding = await embed_async(keywords)
        stmt = (
            stmt.order_by(Query.embedding.cosine_distance(keyword_embedding))
            .limit(5)
        )
    else:
        stmt = stmt.order_by(Query.created_at.desc()).limit(5)

    result = await db.execute(stmt)
    listings = list(result.scalars().all())

    if not listings:
        return f"No active listings found in '{category}'."

    lines = [f"Found {len(listings)} active listing(s) in '{category}'. Top matches:"]
    for i, q in enumerate(listings, 1):
        intent_label = q.intent or "unknown"
        lines.append(f"  {i}) [{intent_label}] {q.raw_text}")
    return "\n".join(lines)


async def check_demand(db: AsyncSession, user_id: uuid.UUID, category: str) -> str:
    """Check supply vs demand balance for a category."""
    stmt = (
        select(Query.intent, func.count(Query.id).label("count"))
        .where(
            and_(
                Query.status == "active",
                _category_filter(category),
            )
        )
        .group_by(Query.intent)
    )
    result = await db.execute(stmt)
    rows = {intent: count for intent, count in result.all()}

    buyers = rows.get("buy", 0)
    sellers = rows.get("sell", 0)
    total = buyers + sellers

    if total == 0:
        return f"No active listings found in '{category}'."

    if buyers > sellers + 2:
        assessment = "High demand for sellers — buyers outnumber sellers significantly."
    elif sellers > buyers + 2:
        assessment = "Surplus of sellers — buyers are scarce in this category."
    else:
        assessment = "Roughly balanced between buyers and sellers."

    return f"In '{category}': {buyers} buyer(s), {sellers} seller(s). {assessment}"


async def get_price_range(
    db: AsyncSession, user_id: uuid.UUID, category: str, keywords: str | None = None
) -> str:
    """Search active listings in a category and extract pricing data."""
    stmt = select(Query).where(
        and_(
            Query.status == "active",
            _category_filter(category),
        )
    )

    if keywords:
        keyword_embedding = await embed_async(keywords)
        stmt = stmt.order_by(Query.embedding.cosine_distance(keyword_embedding)).limit(10)
    else:
        stmt = stmt.order_by(Query.created_at.desc()).limit(10)

    result = await db.execute(stmt)
    listings = list(result.scalars().all())

    if not listings:
        return f"No pricing data available for '{category}'."

    prices: list[float] = []
    dollar_re = re.compile(r"\$\s?([\d,]+(?:\.\d{2})?)")

    for q in listings:
        # Check attributes dict for price/budget keys
        attrs = q.attributes or {}
        for key in ("price", "budget", "asking_price", "max_price", "min_price"):
            val = attrs.get(key)
            if val is not None:
                try:
                    prices.append(float(str(val).replace(",", "").replace("$", "")))
                except (ValueError, TypeError):
                    pass
        # Regex-parse raw_text for dollar amounts
        for match in dollar_re.findall(q.raw_text):
            try:
                prices.append(float(match.replace(",", "")))
            except (ValueError, TypeError):
                pass

    if not prices:
        return f"Found {len(listings)} listing(s) in '{category}' but no pricing data available."

    low, high = min(prices), max(prices)
    median = sorted(prices)[len(prices) // 2]
    return (
        f"Found {len(listings)} similar listing(s). "
        f"Price range: ${low:,.0f}\u2013${high:,.0f}. Most common: ~${median:,.0f}."
    )


async def count_by_category(db: AsyncSession, user_id: uuid.UUID) -> str:
    """Return a full market overview of active listings grouped by category."""
    stmt = (
        select(Query.category, func.count(Query.id).label("count"))
        .where(
            and_(
                Query.status == "active",
                Query.category.is_not(None),
            )
        )
        .group_by(Query.category)
        .order_by(func.count(Query.id).desc())
        .limit(10)
    )
    result = await db.execute(stmt)
    rows = result.all()

    if not rows:
        return "No active listings in the marketplace right now."

    parts = [f"{cat} ({count})" for cat, count in rows]
    return f"Active listings by category: {', '.join(parts)}."


async def check_user_queries(db: AsyncSession, user_id: uuid.UUID) -> str:
    """List the current user's active queries."""
    stmt = (
        select(Query)
        .where(
            and_(
                Query.user_id == user_id,
                Query.status == "active",
            )
        )
        .order_by(Query.created_at.desc())
    )
    result = await db.execute(stmt)
    queries = list(result.scalars().all())

    if not queries:
        return "You have no active queries."

    lines = [f"You have {len(queries)} active query/queries:"]
    for i, q in enumerate(queries, 1):
        intent_label = q.intent or "unknown"
        lines.append(f"  {i}) [{intent_label}] {q.raw_text}")
    return "\n".join(lines)


TOOL_REGISTRY: dict[str, dict] = {
    "search_listings": {
        "description": "Search active marketplace listings by category/keywords. Returns count and top examples.",
        "parameters": {"category": "string", "keywords": "string (optional)"},
        "function": search_listings,
    },
    "check_demand": {
        "description": "Check supply vs demand balance for a category. Shows if there are more buyers or sellers.",
        "parameters": {"category": "string"},
        "function": check_demand,
    },
    "get_price_range": {
        "description": "Get pricing data for a category. Returns price range and typical price from active listings.",
        "parameters": {"category": "string", "keywords": "string (optional)"},
        "function": get_price_range,
    },
    "count_by_category": {
        "description": "Get a full market overview showing active listing counts by category.",
        "parameters": {},
        "function": count_by_category,
    },
    "check_user_queries": {
        "description": "List the current user's active queries to check for duplicates or reference existing activity.",
        "parameters": {},
        "function": check_user_queries,
    },
}


OLLAMA_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "search_listings",
            "description": "Search active marketplace listings by category and optional keywords.",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {"type": "string", "description": "Item category to search"},
                    "keywords": {"type": "string", "description": "Optional search keywords"},
                },
                "required": ["category"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_demand",
            "description": "Check supply vs demand balance for a category. Shows buyer/seller counts.",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {"type": "string", "description": "Item category to check"},
                },
                "required": ["category"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_price_range",
            "description": "Get pricing data for a category. Returns price range and typical price.",
            "parameters": {
                "type": "object",
                "properties": {
                    "category": {"type": "string", "description": "Item category to check pricing"},
                    "keywords": {"type": "string", "description": "Optional search keywords"},
                },
                "required": ["category"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "count_by_category",
            "description": "Get a full market overview showing active listing counts by category.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "check_user_queries",
            "description": "List the current user's active queries to check for duplicates.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
]


def get_ollama_tools() -> list[dict]:
    return OLLAMA_TOOLS


async def execute_tool(
    db: AsyncSession, user_id: uuid.UUID, tool_name: str, args: dict
) -> str:
    """Look up and execute a tool from the registry."""
    tool = TOOL_REGISTRY.get(tool_name)
    if not tool:
        return f"Error: Unknown tool '{tool_name}'. Available tools: {', '.join(TOOL_REGISTRY.keys())}"

    logger.info("Tool called: %s args=%s", tool_name, args)
    try:
        return await tool["function"](db, user_id, **args)
    except Exception as e:
        logger.exception("Tool '%s' failed: %s", tool_name, e)
        return f"Error executing '{tool_name}': {str(e)}"
