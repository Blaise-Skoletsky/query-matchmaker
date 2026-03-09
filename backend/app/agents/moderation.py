"""Content Moderation Agent

Uses the LLM to evaluate query text for:
- Spam / duplicate content
- Abusive or hateful language
- Illegal goods/services
- Scam patterns

Runs on newly created queries (called inline during creation) and can also
run as a batch sweep on unmoderated queries.
"""
import logging
import uuid

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session
from app.models.query import Query
from app.models.moderation import ModerationLog
from app.services.llm import _chat, _parse_json
from app.agents.notifications import notify_moderation

logger = logging.getLogger("agents.moderation")


async def moderate_query(db: AsyncSession, query: Query) -> ModerationLog:
    """Evaluate a single query for policy violations. Returns the log entry."""
    prompt = f"""You are a content moderation system. Evaluate this marketplace query for policy violations.

Query text: "{query.raw_text}"

Check for:
1. Spam or nonsensical content
2. Abusive, hateful, or threatening language
3. Illegal goods or services (drugs, weapons, stolen goods)
4. Scam patterns (too-good-to-be-true offers, advance fee requests)
5. Personal information exposure (phone numbers, addresses in query text)

Return ONLY valid JSON:
{{
  "flagged": true/false,
  "category": "safe" | "spam" | "abuse" | "illegal" | "scam" | "pii",
  "confidence": 0.0-1.0,
  "reason": "brief explanation"
}}"""

    try:
        result = _parse_json(await _chat([{"role": "user", "content": prompt}], max_tokens=256))
    except Exception as e:
        logger.error(f"Moderation LLM call failed for query {query.id}: {e}")
        result = {"flagged": False, "category": "safe", "confidence": 0.0, "reason": "Moderation check failed"}

    log = ModerationLog(
        query_id=query.id,
        flagged=result.get("flagged", False),
        reason=result.get("reason"),
        category=result.get("category", "safe"),
        confidence=result.get("confidence"),
        auto_action="none",
        details=result,
    )
    db.add(log)

    if result.get("flagged") and result.get("confidence", 0) >= 0.8:
        query.status = "suspended"
        log.auto_action = "suspended"
        await notify_moderation(db, query.user_id, query.id, result.get("reason", "Policy violation"))
        logger.warning(f"Query {query.id} suspended: {result.get('reason')}")

    return log


async def sweep_unmoderated(limit: int = 50) -> int:
    """Batch-moderate queries that haven't been checked yet. Returns count processed."""
    async with async_session() as db:
        # Find queries with no moderation log
        moderated_ids = select(ModerationLog.query_id)
        stmt = (
            select(Query)
            .where(
                and_(
                    Query.status == "active",
                    Query.id.notin_(moderated_ids),
                )
            )
            .limit(limit)
        )
        result = await db.execute(stmt)
        queries = list(result.scalars().all())

        for q in queries:
            await moderate_query(db, q)

        await db.commit()

        if queries:
            logger.info(f"Moderation sweep: processed {len(queries)} queries")
        return len(queries)
