from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.schemas.recommendation import SimilarQueryResponse, TrendingCategoryResponse, DemandGapResponse
from app.services.auth import get_current_user
from app.agents.recommendations import get_similar_queries, get_trending_categories, get_high_demand_queries

router = APIRouter(prefix="/api/recommendations", tags=["recommendations"])


@router.get("/similar", response_model=list[SimilarQueryResponse])
async def similar_queries(
    limit: int = 5,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    return await get_similar_queries(db, user.id, limit=limit)


@router.get("/trending", response_model=list[TrendingCategoryResponse])
async def trending(
    limit: int = 10,
    db: AsyncSession = Depends(get_db),
):
    return await get_trending_categories(db, limit=limit)


@router.get("/demand-gaps", response_model=list[DemandGapResponse])
async def demand_gaps(
    limit: int = 5,
    db: AsyncSession = Depends(get_db),
):
    return await get_high_demand_queries(db, limit=limit)
