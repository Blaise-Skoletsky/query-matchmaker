"""Match Reprocessing Agent

Retries the matching pipeline for queries that failed during initial processing.
Detects failures by looking for queries with no match_trace or a trace with
status != "complete" that are still active.
"""
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session
from app.models.query import Query

logger = logging.getLogger("agents.reprocessing")

MAX_RETRIES = 3
RETRY_MIN_AGE_MINUTES = 5  # Don't retry queries created less than 5 min ago (still processing)


async def run(limit: int = 20) -> int:
    """Find and reprocess failed queries. Returns count of reprocessed queries."""
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=RETRY_MIN_AGE_MINUTES)

    async with async_session() as db:
        stmt = (
            select(Query)
            .where(
                and_(
                    Query.status == "active",
                    Query.embedding.isnot(None),
                    Query.created_at <= cutoff,
                    or_(
                        Query.match_trace.is_(None),
                        Query.match_trace["status"].as_string() != "complete",
                    ),
                )
            )
            .limit(limit)
        )
        result = await db.execute(stmt)
        queries = list(result.scalars().all())

        reprocessed = 0
        for query in queries:
            trace = query.match_trace or {}
            retry_count = trace.get("retry_count", 0)

            if retry_count >= MAX_RETRIES:
                logger.warning(f"Query {query.id} exceeded max retries ({MAX_RETRIES}), skipping")
                continue

            logger.info(f"Reprocessing query {query.id} (retry #{retry_count + 1})")
            try:
                from app.services.matching import run_matching_pipeline
                await run_matching_pipeline(db, query)
                # Update retry count in trace
                updated_trace = query.match_trace or {}
                updated_trace["retry_count"] = retry_count + 1
                query.match_trace = updated_trace
                await db.commit()
                reprocessed += 1
            except Exception as e:
                logger.error(f"Reprocessing failed for query {query.id}: {e}")
                query.match_trace = {
                    **(query.match_trace or {}),
                    "retry_count": retry_count + 1,
                    "last_error": str(e),
                }
                await db.commit()

        if reprocessed > 0:
            logger.info(f"Reprocessed {reprocessed} queries")
        return reprocessed
