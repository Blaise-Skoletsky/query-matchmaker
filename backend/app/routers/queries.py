import uuid

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.models.query import Query
from app.models.match import Match, MatchQuery
from app.schemas.query import QueryCreate, QueryResponse
from app.services.auth import get_current_user
from app.services.embedding import embed_async
from app.services.llm import extract_metadata
from app.services.matching import run_matching_bg
from app.agents.moderation import moderate_query

router = APIRouter(prefix="/api/queries", tags=["queries"])


@router.post("", response_model=QueryResponse, status_code=status.HTTP_201_CREATED)
async def create_query(
    body: QueryCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    embedding = await embed_async(body.raw_text)

    try:
        metadata = await extract_metadata(body.raw_text)
    except Exception:
        metadata = {}

    query = Query(
        user_id=user.id,
        raw_text=body.raw_text,
        intent=metadata.get("intent"),
        category=metadata.get("category"),
        attributes=metadata.get("attributes"),
        complementary_intents=metadata.get("complementary_intents"),
        required_match_attributes=metadata.get("required_match_attributes"),
        preferred_match_attributes=metadata.get("preferred_match_attributes"),
        location=body.location,
        latitude=body.latitude,
        longitude=body.longitude,
        embedding=embedding,
        group_size=body.group_size,
    )
    db.add(query)
    await db.commit()
    await db.refresh(query)

    # Inline moderation check before matching
    mod_log = await moderate_query(db, query)
    await db.commit()

    if query.status == "suspended":
        await db.refresh(query)
        return query

    background_tasks.add_task(run_matching_bg, query.id)

    return query


@router.get("", response_model=list[QueryResponse])
async def list_queries(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Query).where(Query.user_id == user.id).order_by(Query.created_at.desc())
    )
    return result.scalars().all()


@router.get("/{query_id}", response_model=QueryResponse)
async def get_query(
    query_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = await db.get(Query, query_id)
    if not query or query.user_id != user.id:
        raise HTTPException(status_code=404, detail="Query not found")
    return query


@router.get("/{query_id}/trace")
async def get_match_trace(
    query_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = await db.get(Query, query_id)
    if not query or query.user_id != user.id:
        raise HTTPException(status_code=404, detail="Query not found")
    return {"ready": query.match_trace is not None, "trace": query.match_trace}


@router.delete("/{query_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_query(
    query_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    query = await db.get(Query, query_id)
    if not query or query.user_id != user.id:
        raise HTTPException(status_code=404, detail="Query not found")
    query.status = "cancelled"

    result = await db.execute(
        select(Match)
        .join(MatchQuery, MatchQuery.match_id == Match.id)
        .where(MatchQuery.query_id == query.id)
    )
    for match in result.scalars().all():
        match.status = "cancelled"

    await db.commit()
