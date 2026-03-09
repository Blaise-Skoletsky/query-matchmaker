import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func, and_, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.models.notification import Notification
from app.schemas.notification import NotificationResponse, NotificationCount
from app.services.auth import get_current_user

router = APIRouter(prefix="/api/notifications", tags=["notifications"])


@router.get("", response_model=list[NotificationResponse])
async def list_notifications(
    unread_only: bool = False,
    limit: int = 50,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    stmt = select(Notification).where(Notification.user_id == user.id)
    if unread_only:
        stmt = stmt.where(Notification.read == False)
    stmt = stmt.order_by(Notification.created_at.desc()).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/count", response_model=NotificationCount)
async def notification_count(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    unread = (await db.execute(
        select(func.count(Notification.id)).where(
            and_(Notification.user_id == user.id, Notification.read == False)
        )
    )).scalar() or 0
    total = (await db.execute(
        select(func.count(Notification.id)).where(Notification.user_id == user.id)
    )).scalar() or 0
    return NotificationCount(unread=unread, total=total)


@router.post("/{notification_id}/read", response_model=NotificationResponse)
async def mark_read(
    notification_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    n = await db.get(Notification, notification_id)
    if not n or n.user_id != user.id:
        raise HTTPException(status_code=404, detail="Notification not found")
    n.read = True
    await db.commit()
    return n


@router.post("/read-all")
async def mark_all_read(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await db.execute(
        update(Notification)
        .where(and_(Notification.user_id == user.id, Notification.read == False))
        .values(read=True)
    )
    await db.commit()
    return {"status": "ok"}
