import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, exists
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.database import get_db
from app.models.user import User
from app.models.match import Match, MatchQuery
from app.models.query import Query
from app.schemas.match import MatchResponse
from app.services.auth import get_current_user
from app.services.matching import accept_match
from app.agents.notifications import notify_match_accepted, notify_match_rejected

router = APIRouter(prefix="/api/matches", tags=["matches"])


async def _get_user_matches(db: AsyncSession, user_id: uuid.UUID) -> list[Match]:
    # Use a subquery filter instead of JOIN so the identity map stays clean
    # for selectinload — a JOIN + WHERE can cause selectinload to only populate
    # the filtered MatchQuery rows, hiding the other side of each match.
    user_match_ids = (
        select(MatchQuery.match_id)
        .join(Query, Query.id == MatchQuery.query_id)
        .where(Query.user_id == user_id)
    )
    stmt = (
        select(Match)
        .where(Match.id.in_(user_match_ids))
        .options(selectinload(Match.match_queries).selectinload(MatchQuery.query))
        .order_by(Match.created_at.desc())
    )
    result = await db.execute(stmt)
    return list(result.scalars().all())


@router.get("", response_model=list[MatchResponse])
async def list_matches(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await _get_user_matches(db, user.id)


@router.post("/{match_id}/accept", response_model=MatchResponse)
async def accept(
    match_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    stmt = (
        select(Match)
        .options(selectinload(Match.match_queries).selectinload(MatchQuery.query))
        .where(Match.id == match_id)
    )
    result = await db.execute(stmt)
    match = result.scalar_one_or_none()
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")

    user_query_ids = {mq.query.id for mq in match.match_queries if mq.query.user_id == user.id}
    if not user_query_ids:
        raise HTTPException(status_code=403, detail="Not your match")

    chatroom = await accept_match(db, match)
    await db.refresh(match, ["match_queries"])

    # Notify other users in the match
    for mq in match.match_queries:
        if mq.query.user_id != user.id:
            await notify_match_accepted(
                db, mq.query.user_id, match.id,
                match.chatroom_id or (chatroom.id if chatroom else None),
                user.display_name,
            )
    await db.commit()

    return match


@router.post("/{match_id}/reject", response_model=MatchResponse)
async def reject(
    match_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    stmt = (
        select(Match)
        .options(selectinload(Match.match_queries).selectinload(MatchQuery.query))
        .where(Match.id == match_id)
    )
    result = await db.execute(stmt)
    match = result.scalar_one_or_none()
    if not match:
        raise HTTPException(status_code=404, detail="Match not found")

    user_query_ids = {mq.query.id for mq in match.match_queries if mq.query.user_id == user.id}
    if not user_query_ids:
        raise HTTPException(status_code=403, detail="Not your match")

    match.status = "rejected"

    # Notify other users
    for mq in match.match_queries:
        if mq.query.user_id != user.id:
            await notify_match_rejected(db, mq.query.user_id, match.id)

    await db.commit()
    return match
