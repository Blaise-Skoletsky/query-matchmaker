"""Query Expiration Agent

Periodically scans for queries past their expires_at timestamp and marks
them as expired. Also expires queries that have been active with no matches
for longer than a configurable maximum age (default: 30 days).
"""
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, and_, update

from app.database import async_session
from app.models.query import Query

logger = logging.getLogger("agents.expiration")

DEFAULT_MAX_AGE_DAYS = 30


async def run(max_age_days: int = DEFAULT_MAX_AGE_DAYS):
    """Expire stale queries. Returns count of expired queries."""
    now = datetime.now(timezone.utc)
    max_age_cutoff = now - timedelta(days=max_age_days)

    async with async_session() as db:
        # Queries with explicit expiration that have passed
        stmt_explicit = (
            update(Query)
            .where(
                and_(
                    Query.status == "active",
                    Query.expires_at.isnot(None),
                    Query.expires_at <= now,
                )
            )
            .values(status="expired")
            .returning(Query.id)
        )
        result_explicit = await db.execute(stmt_explicit)
        explicit_ids = list(result_explicit.scalars().all())

        # Queries older than max_age_days with no explicit expiration
        stmt_aged = (
            update(Query)
            .where(
                and_(
                    Query.status == "active",
                    Query.expires_at.is_(None),
                    Query.created_at <= max_age_cutoff,
                )
            )
            .values(status="expired")
            .returning(Query.id)
        )
        result_aged = await db.execute(stmt_aged)
        aged_ids = list(result_aged.scalars().all())

        await db.commit()

        total = len(explicit_ids) + len(aged_ids)
        if total > 0:
            logger.info(f"Expired {total} queries ({len(explicit_ids)} explicit, {len(aged_ids)} aged out)")
        return total
