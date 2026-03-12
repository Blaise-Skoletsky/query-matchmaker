import logging
import uuid

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.models.query import Query
from app.models.match import Match, MatchQuery
from app.models.chat import Chatroom, ChatroomMember
from app.services.llm import evaluate_candidates
from app.agents.notifications import notify_match_found

logger = logging.getLogger(__name__)


async def find_candidates(db: AsyncSession, query: Query) -> list[Query]:
    if not query.complementary_intents or query.embedding is None:
        return []

    stmt = (
        select(Query)
        .where(
            and_(
                Query.status == "active",
                Query.intent.in_(query.complementary_intents),
                Query.user_id != query.user_id,
            )
        )
        .order_by(Query.embedding.cosine_distance(query.embedding))
        .limit(settings.candidate_limit)
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


async def run_matching_pipeline(db: AsyncSession, query: Query):
    trace = {"status": "complete", "steps": []}

    # Step 1: metadata
    query_label = query.raw_text[:60] + "…" if len(query.raw_text) > 60 else query.raw_text
    if query.intent:
        trace["steps"].append({
            "step": "metadata",
            "label": query_label,
            "status": "pass",
            "intent": query.intent,
            "category": query.category,
            "attributes": query.attributes or {},
            "complementary_intents": query.complementary_intents or [],
        })
    else:
        trace["steps"].append({
            "step": "metadata",
            "label": query_label,
            "status": "fail",
            "detail": "Could not extract intent from query.",
        })
        await _save_trace(db, query.id, trace)
        return

    # Step 2: candidate search
    candidates = await find_candidates(db, query)
    if not candidates:
        trace["steps"].append({
            "step": "candidate_search",
            "label": "Finding candidates",
            "status": "fail",
            "detail": "No active queries found with a complementary intent.",
            "candidates": [],
        })
        await _save_trace(db, query.id, trace)
        return

    trace["steps"].append({
        "step": "candidate_search",
        "label": "Finding candidates",
        "status": "pass",
        "total_found": len(candidates),
        "candidates": [
            {"id": str(c.id), "text": c.raw_text, "intent": c.intent}
            for c in candidates
        ],
    })

    # Step 3: LLM scoring
    eval_candidates = candidates[: settings.llm_eval_limit]
    source_dict = {
        "id": str(query.id),
        "intent": query.intent,
        "raw_text": query.raw_text,
        "attributes": query.attributes,
        "required_match_attributes": query.required_match_attributes,
        "preferred_match_attributes": query.preferred_match_attributes,
    }
    candidate_dicts = [
        {
            "id": str(c.id),
            "intent": c.intent,
            "raw_text": c.raw_text,
            "attributes": c.attributes,
        }
        for c in eval_candidates
    ]

    try:
        scores = await evaluate_candidates(source_dict, candidate_dicts)
    except Exception as e:
        trace["steps"].append({
            "step": "llm_scoring",
            "label": "AI compatibility scoring",
            "status": "fail",
            "detail": f"LLM scoring failed: {str(e)}",
            "candidates": [],
        })
        await _save_trace(db, query.id, trace)
        return

    candidate_id_to_obj = {str(c.id): c for c in eval_candidates}

    def _resolve_candidate(raw_id: str) -> Query | None:
        """Look up candidate by ID, handling LLM-mangled UUIDs."""
        obj = candidate_id_to_obj.get(raw_id)
        if obj:
            return obj
        # Try normalising: strip whitespace/quotes, lowercase
        cleaned = raw_id.strip().strip('"').strip("'").lower()
        obj = candidate_id_to_obj.get(cleaned)
        if obj:
            return obj
        # Try prefix match (LLM may truncate UUIDs)
        for key, val in candidate_id_to_obj.items():
            if key.startswith(cleaned) or cleaned.startswith(key):
                return val
        logger.warning("Could not resolve LLM-returned candidate id=%s", raw_id)
        return None

    scored = [
        {
            "id": r["id"],
            "text": (c.raw_text if (c := _resolve_candidate(r["id"])) else ""),
            "score": r.get("score", 0),
            "reasoning": r.get("reasoning", ""),
            "passed": r.get("score", 0) >= settings.match_score_threshold,
        }
        for r in scores
    ]

    trace["steps"].append({
        "step": "llm_scoring",
        "label": "AI compatibility scoring",
        "status": "pass",
        "threshold": settings.match_score_threshold,
        "candidates": scored,
    })

    # Step 4: create matches
    matches_created = 0
    for result in scores:
        if result.get("score", 0) >= settings.match_score_threshold:
            candidate = _resolve_candidate(result["id"])
            if not candidate:
                continue

            if query.group_size > 2 or candidate.group_size > 2:
                await _handle_group_match(db, query, candidate, result)
            else:
                match = Match(
                    compatibility_score=result["score"],
                    reasoning=result.get("reasoning"),
                )
                db.add(match)
                await db.flush()
                db.add(MatchQuery(match_id=match.id, query_id=query.id))
                db.add(MatchQuery(match_id=match.id, query_id=candidate.id))

                # Notify both users
                await notify_match_found(db, query.user_id, match.id, candidate.raw_text, result["score"])
                await notify_match_found(db, candidate.user_id, match.id, query.raw_text, result["score"])

                await db.commit()
            matches_created += 1

    trace["steps"].append({
        "step": "matches_created",
        "label": "Matches created",
        "status": "pass" if matches_created > 0 else "fail",
        "count": matches_created,
        "detail": f"{matches_created} match(es) created." if matches_created > 0 else "No candidates scored above the threshold.",
    })

    await _save_trace(db, query.id, trace)


async def _save_trace(db: AsyncSession, query_id: uuid.UUID, trace: dict):
    q = await db.get(Query, query_id)
    if q:
        q.match_trace = trace
        await db.commit()


async def _handle_group_match(db: AsyncSession, query: Query, candidate: Query, result: dict):
    target_size = max(query.group_size, candidate.group_size)

    existing = await _find_partial_group_match(db, candidate, target_size)

    if existing:
        db.add(MatchQuery(match_id=existing.id, query_id=query.id))
        await db.flush()

        member_count = len(existing.match_queries) + 1
        if member_count >= target_size:
            existing.status = "pending"
            await _create_chatroom_for_match(db, existing)
        await db.commit()
    else:
        match = Match(
            compatibility_score=result["score"],
            reasoning=result.get("reasoning"),
            status="partial",
        )
        db.add(match)
        await db.flush()
        db.add(MatchQuery(match_id=match.id, query_id=query.id))
        db.add(MatchQuery(match_id=match.id, query_id=candidate.id))
        await db.commit()


async def _find_partial_group_match(db: AsyncSession, candidate: Query, target_size: int) -> Match | None:
    stmt = (
        select(Match)
        .join(MatchQuery)
        .where(
            and_(
                MatchQuery.query_id == candidate.id,
                Match.status == "partial",
            )
        )
        .options(selectinload(Match.match_queries))
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


async def run_reverse_matching(db: AsyncSession, new_query: Query):
    """Find existing queries that should match against the new query and run their pipelines."""
    if not new_query.intent:
        return

    # Find active queries whose complementary_intents include the new query's intent
    stmt = (
        select(Query)
        .where(
            and_(
                Query.status == "active",
                Query.id != new_query.id,
                Query.user_id != new_query.user_id,
                Query.complementary_intents.contains([new_query.intent]),
            )
        )
    )
    result = await db.execute(stmt)
    candidates = list(result.scalars().all())

    for candidate in candidates:
        # Skip if a match already exists between these two queries
        existing = await db.execute(
            select(Match.id)
            .join(MatchQuery)
            .where(MatchQuery.query_id == candidate.id)
            .intersect(
                select(Match.id)
                .join(MatchQuery)
                .where(MatchQuery.query_id == new_query.id)
            )
        )
        if existing.first():
            continue

        await run_matching_pipeline(db, candidate)


async def accept_match(db: AsyncSession, match: Match) -> Chatroom | None:
    match.status = "accepted"
    if not match.chatroom_id:
        chatroom = await _create_chatroom_for_match(db, match)
        await db.commit()
        return chatroom
    await db.commit()
    return None


async def _create_chatroom_for_match(db: AsyncSession, match: Match) -> Chatroom:
    if not match.match_queries:
        await db.refresh(match, ["match_queries"])

    query_texts = []
    seen_users = set()
    for mq in match.match_queries:
        query = await db.get(Query, mq.query_id)
        if query:
            query_texts.append(query.raw_text)
            if query.user_id not in seen_users:
                seen_users.add(query.user_id)

    name = _build_chatroom_name(query_texts)
    chatroom = Chatroom(name=name)
    db.add(chatroom)
    await db.flush()

    match.chatroom_id = chatroom.id

    for uid in seen_users:
        db.add(ChatroomMember(chatroom_id=chatroom.id, user_id=uid))

    return chatroom


def _build_chatroom_name(query_texts: list[str]) -> str:
    if not query_texts:
        return "Chat"
    combined = query_texts[0]
    if len(combined) > 60:
        combined = combined[:57] + "..."
    return combined
