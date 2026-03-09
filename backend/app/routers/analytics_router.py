from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.analytics import AnalyticsSnapshot
from app.schemas.analytics import AnalyticsSnapshotResponse

router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/snapshots", response_model=list[AnalyticsSnapshotResponse])
async def list_snapshots(
    limit: int = 30,
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(AnalyticsSnapshot)
        .where(AnalyticsSnapshot.period == "daily")
        .order_by(AnalyticsSnapshot.date.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/latest", response_model=AnalyticsSnapshotResponse | None)
async def latest_snapshot(
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(AnalyticsSnapshot)
        .where(AnalyticsSnapshot.period == "daily")
        .order_by(AnalyticsSnapshot.date.desc())
        .limit(1)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()
