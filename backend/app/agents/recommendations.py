"""Query Recommendation Agent

Suggests similar or trending queries to users based on:
1. Vector similarity to their past queries
2. Popular categories/intents in the platform
3. Queries that have high match potential (many complementary queries exist)

Used by the recommendations API endpoint.
"""
import logging
import uuid

from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.query import Query

logger = logging.getLogger("agents.recommendations")


async def get_similar_queries(
    db: AsyncSession,
    user_id: uuid.UUID,
    limit: int = 5,
) -> list[dict]:
    """Find active queries from other users that are similar to this user's queries.
    Returns queries the user might want to match with."""

    # Get user's most recent active query embedding
    user_query_stmt = (
        select(Query)
        .where(and_(Query.user_id == user_id, Query.status == "active"))
        .order_by(Query.created_at.desc())
        .limit(1)
    )
    result = await db.execute(user_query_stmt)
    user_query = result.scalar_one_or_none()

    if not user_query or user_query.embedding is None:
        return []

    # Find similar queries from other users with complementary intents
    complementary = user_query.complementary_intents or []
    if not complementary:
        return []

    stmt = (
        select(Query)
        .where(
            and_(
                Query.status == "active",
                Query.user_id != user_id,
                Query.intent.in_(complementary),
            )
        )
        .order_by(Query.embedding.cosine_distance(user_query.embedding))
        .limit(limit)
    )
    # Include cosine distance in the query for ranking
    distance_col = Query.embedding.cosine_distance(user_query.embedding).label("distance")
    stmt = (
        select(Query, distance_col)
        .where(
            and_(
                Query.status == "active",
                Query.user_id != user_id,
                Query.intent.in_(complementary),
            )
        )
        .order_by(distance_col)
        .limit(limit)
    )
    result = await db.execute(stmt)
    rows = result.all()

    return [
        {
            "id": str(q.id),
            "raw_text": q.raw_text,
            "intent": q.intent,
            "category": q.category,
            "similarity": round(1.0 - float(dist), 4),
        }
        for q, dist in rows
    ]


async def get_trending_categories(db: AsyncSession, limit: int = 10) -> list[dict]:
    """Get the most active categories in the last 7 days."""
    from datetime import datetime, timedelta, timezone
    week_ago = datetime.now(timezone.utc) - timedelta(days=7)

    stmt = (
        select(
            Query.category,
            Query.intent,
            func.count(Query.id).label("count"),
        )
        .where(
            and_(
                Query.status == "active",
                Query.category.isnot(None),
                Query.created_at >= week_ago,
            )
        )
        .group_by(Query.category, Query.intent)
        .order_by(func.count(Query.id).desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    rows = result.all()

    return [
        {"category": row[0], "intent": row[1], "count": row[2]}
        for row in rows
    ]


async def get_high_demand_queries(db: AsyncSession, limit: int = 5) -> list[dict]:
    """Find query intents/categories where demand outstrips supply.
    E.g., many buyers but few sellers in a category."""

    # Count by (category, intent)
    stmt = (
        select(
            Query.category,
            Query.intent,
            func.count(Query.id).label("count"),
        )
        .where(and_(Query.status == "active", Query.category.isnot(None)))
        .group_by(Query.category, Query.intent)
        .order_by(func.count(Query.id).desc())
        .limit(50)
    )
    result = await db.execute(stmt)
    rows = result.all()

    # Build category -> {intent: count} map
    cat_intents: dict[str, dict[str, int]] = {}
    for category, intent, count in rows:
        cat_intents.setdefault(category, {})[intent] = count

    # Find imbalances
    COMPLEMENTARY = {
        "buy": "sell", "sell": "buy",
        "job_seek": "job_offer", "job_offer": "job_seek",
        "housing_seek": "housing_offer", "housing_offer": "housing_seek",
        "service_seek": "service_offer", "service_offer": "service_seek",
    }

    opportunities = []
    for category, intents in cat_intents.items():
        for intent, count in intents.items():
            complement = COMPLEMENTARY.get(intent)
            if complement:
                supply = intents.get(complement, 0)
                if count > supply + 2:  # Meaningful imbalance
                    opportunities.append({
                        "category": category,
                        "needed_intent": complement,
                        "demand_count": count,
                        "supply_count": supply,
                        "gap": count - supply,
                    })

    opportunities.sort(key=lambda x: x["gap"], reverse=True)
    return opportunities[:limit]
