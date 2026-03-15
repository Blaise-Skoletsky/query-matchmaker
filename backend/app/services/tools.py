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
    """Build an OR filter that matches ANY word from category against category/raw_text.

    Args:
        category: Category string (e.g. "vehicles" or "software_engineering");
            may be split on whitespace/underscores; words shorter than 3 chars are ignored.

    Returns:
        A SQLAlchemy OR condition for Query.category and Query.raw_text ilike matches.
    """
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
    """Search active marketplace listings by category and optional keywords.

    Args:
        db: Database session.
        user_id: Current user; their own listings are excluded.
        category: Item category to search (e.g. "electronics", "vehicles").
        keywords: Optional keywords; when provided, results are ordered by
            embedding similarity to this string.

    Returns:
        Human-readable summary: count and top listing lines, or a "no listings" message.
    """
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
    """Check supply vs demand balance for a category (buy vs sell counts).

    Args:
        db: Database session.
        user_id: Unused; kept for consistent tool signature.
        category: Item category to analyze.

    Returns:
        Human-readable string: buyer/seller counts and a short assessment
        (e.g. "High demand for sellers", "Roughly balanced"), or a no-data message.
    """
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
    """Search active listings in a category and extract pricing data.

    Args:
        db: Database session.
        user_id: Unused; kept for consistent tool signature.
        category: Item category to check.
        keywords: Optional; when provided, listings are ordered by embedding similarity.

    Returns:
        Human-readable string with price range and typical (median) price, or
        a message if no listings or no prices found.
    """
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
    """Return a full market overview of active listings grouped by category.

    Args:
        db: Database session.
        user_id: Unused; kept for consistent tool signature.

    Returns:
        Human-readable string: "Active listings by category: cat1 (n1), cat2 (n2), ..."
        or a no-listings message. Limited to top 10 categories by count.
    """
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
    """List the current user's active queries.

    Args:
        db: Database session.
        user_id: User whose active queries to list.

    Returns:
        Human-readable list of the user's active queries (intent + raw_text),
        or "You have no active queries." if none.
    """
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
        "description": "Search active marketplace listings by category and optional keywords.",
        "parameters": {
            "type": "object",
            "properties": {
                "category": {"type": "string", "description": "Item category to search"},
                "keywords": {"type": "string", "description": "Optional search keywords"},
            },
            "required": ["category"],
        },
        "function": search_listings,
    },
    "check_demand": {
        "description": "Check supply vs demand balance for a category. Shows buyer/seller counts.",
        "parameters": {
            "type": "object",
            "properties": {
                "category": {"type": "string", "description": "Item category to check"},
            },
            "required": ["category"],
        },
        "function": check_demand,
    },
    "get_price_range": {
        "description": "Get pricing data for a category. Returns price range and typical price.",
        "parameters": {
            "type": "object",
            "properties": {
                "category": {"type": "string", "description": "Item category to check pricing"},
                "keywords": {"type": "string", "description": "Optional search keywords"},
            },
            "required": ["category"],
        },
        "function": get_price_range,
    },
    "count_by_category": {
        "description": "Get a full market overview showing active listing counts by category.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
        "function": count_by_category,
    },
    "check_user_queries": {
        "description": "List the current user's active queries to check for duplicates.",
        "parameters": {
            "type": "object",
            "properties": {},
            "required": [],
        },
        "function": check_user_queries,
    },
}


def get_ollama_tools() -> list[dict]:
    """Return the list of tool definitions in Ollama function-calling format.

    Generated from TOOL_REGISTRY so definitions stay in sync automatically.

    Returns:
        List of dicts with "type": "function" and "function": {name, description, parameters}.
    """
    return [
        {
            "type": "function",
            "function": {
                "name": name,
                "description": tool["description"],
                "parameters": tool["parameters"],
            },
        }
        for name, tool in TOOL_REGISTRY.items()
    ]


async def execute_tool(
    db: AsyncSession, user_id: uuid.UUID, tool_name: str, args: dict
) -> str:
    """Look up and execute a tool from the registry.

    Args:
        db: Database session passed to the tool.
        user_id: Current user id passed to the tool.
        tool_name: Key in TOOL_REGISTRY (e.g. "search_listings", "check_demand").
        args: Keyword arguments for the tool (e.g. {"category": "electronics"}).

    Returns:
        The tool's result string (for the LLM), or an error message string
        if the tool is unknown or raises an exception.
    """
    tool = TOOL_REGISTRY.get(tool_name)
    if not tool:
        return f"Error: Unknown tool '{tool_name}'. Available tools: {', '.join(TOOL_REGISTRY.keys())}"

    logger.info("Tool called: %s args=%s", tool_name, args)
    try:
        return await tool["function"](db, user_id, **args)
    except Exception as e:
        logger.exception("Tool '%s' failed: %s", tool_name, e)
        return f"Error executing '{tool_name}': {str(e)}"
