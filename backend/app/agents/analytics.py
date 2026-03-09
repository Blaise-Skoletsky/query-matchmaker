"""Analytics Aggregation Agent

Computes daily platform metrics and stores them as snapshots.
Runs once per day (typically at midnight) to aggregate the previous day's data.
"""
import logging
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import select, func, and_
from app.database import async_session
from app.models.user import User
from app.models.query import Query
from app.models.match import Match
from app.models.chat import Message
from app.models.analytics import AnalyticsSnapshot

logger = logging.getLogger("agents.analytics")


async def compute_daily_snapshot(target_date: date | None = None) -> AnalyticsSnapshot | None:
    """Compute and store a daily analytics snapshot. Returns the snapshot or None if already exists."""
    if target_date is None:
        target_date = (datetime.now(timezone.utc) - timedelta(days=1)).date()

    async with async_session() as db:
        # Check if snapshot already exists
        existing = await db.execute(
            select(AnalyticsSnapshot).where(
                and_(
                    AnalyticsSnapshot.snapshot_date == target_date,
                    AnalyticsSnapshot.period == "daily",
                )
            )
        )
        if existing.scalar_one_or_none():
            logger.debug(f"Snapshot for {target_date} already exists, skipping")
            return None

        day_start = datetime.combine(target_date, datetime.min.time()).replace(tzinfo=timezone.utc)
        day_end = day_start + timedelta(days=1)

        # Total users
        total_users = (await db.execute(select(func.count(User.id)))).scalar() or 0

        # Query stats
        total_queries = (await db.execute(select(func.count(Query.id)))).scalar() or 0
        active_queries = (await db.execute(
            select(func.count(Query.id)).where(Query.status == "active")
        )).scalar() or 0

        # Match stats
        total_matches = (await db.execute(select(func.count(Match.id)))).scalar() or 0
        accepted = (await db.execute(
            select(func.count(Match.id)).where(Match.status == "accepted")
        )).scalar() or 0
        rejected = (await db.execute(
            select(func.count(Match.id)).where(Match.status == "rejected")
        )).scalar() or 0

        decided = accepted + rejected
        acceptance_rate = (accepted / decided) if decided > 0 else None

        avg_score = (await db.execute(
            select(func.avg(Match.compatibility_score)).where(Match.compatibility_score.isnot(None))
        )).scalar()

        # Messages
        total_messages = (await db.execute(select(func.count(Message.id)))).scalar() or 0

        # Top categories
        cat_rows = (await db.execute(
            select(Query.category, func.count(Query.id).label("cnt"))
            .where(Query.category.isnot(None))
            .group_by(Query.category)
            .order_by(func.count(Query.id).desc())
            .limit(10)
        )).all()
        top_categories = {row[0]: row[1] for row in cat_rows} if cat_rows else None

        # Top intents
        intent_rows = (await db.execute(
            select(Query.intent, func.count(Query.id).label("cnt"))
            .where(Query.intent.isnot(None))
            .group_by(Query.intent)
            .order_by(func.count(Query.id).desc())
            .limit(10)
        )).all()
        top_intents = {row[0]: row[1] for row in intent_rows} if intent_rows else None

        snapshot = AnalyticsSnapshot(
            period="daily",
            snapshot_date=target_date,
            total_users=total_users,
            total_queries=total_queries,
            active_queries=active_queries,
            total_matches=total_matches,
            accepted_matches=accepted,
            rejected_matches=rejected,
            acceptance_rate=acceptance_rate,
            avg_compatibility_score=float(avg_score) if avg_score else None,
            total_messages=total_messages,
            top_categories=top_categories,
            top_intents=top_intents,
        )
        db.add(snapshot)
        await db.commit()

        logger.info(f"Daily snapshot for {target_date}: {total_queries} queries, {total_matches} matches, {total_messages} messages")
        return snapshot


async def run():
    """Entry point for the scheduler."""
    return await compute_daily_snapshot()
