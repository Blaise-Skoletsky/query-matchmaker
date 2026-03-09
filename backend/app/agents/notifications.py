"""Notification Agent

Creates in-app notifications for key events:
- New match found
- Match accepted/rejected by the other party
- Query expired
- Content moderation action

Also provides helpers used by other parts of the system to send notifications.
"""
import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.notification import Notification

logger = logging.getLogger("agents.notifications")


async def notify_match_found(
    db: AsyncSession,
    user_id: uuid.UUID,
    match_id: uuid.UUID,
    query_text: str,
    score: float,
):
    n = Notification(
        user_id=user_id,
        type="match_found",
        title="New match found!",
        body=f"Your query matched with a score of {score:.0%}: \"{query_text[:80]}\"",
        data={"match_id": str(match_id)},
    )
    db.add(n)
    logger.info(f"Notification: match_found for user {user_id}")


async def notify_match_accepted(
    db: AsyncSession,
    user_id: uuid.UUID,
    match_id: uuid.UUID,
    chatroom_id: uuid.UUID,
    accepter_name: str,
):
    n = Notification(
        user_id=user_id,
        type="match_accepted",
        title="Match accepted!",
        body=f"{accepter_name} accepted your match. Start chatting now!",
        data={"match_id": str(match_id), "chatroom_id": str(chatroom_id)},
    )
    db.add(n)
    logger.info(f"Notification: match_accepted for user {user_id}")


async def notify_match_rejected(
    db: AsyncSession,
    user_id: uuid.UUID,
    match_id: uuid.UUID,
):
    n = Notification(
        user_id=user_id,
        type="match_rejected",
        title="Match declined",
        body="The other party declined your match. Don't worry, we'll keep looking!",
        data={"match_id": str(match_id)},
    )
    db.add(n)
    logger.info(f"Notification: match_rejected for user {user_id}")


async def notify_query_expired(
    db: AsyncSession,
    user_id: uuid.UUID,
    query_id: uuid.UUID,
    query_text: str,
):
    n = Notification(
        user_id=user_id,
        type="query_expired",
        title="Query expired",
        body=f"Your query has expired: \"{query_text[:80]}\"",
        data={"query_id": str(query_id)},
    )
    db.add(n)
    logger.info(f"Notification: query_expired for user {user_id}")


async def notify_moderation(
    db: AsyncSession,
    user_id: uuid.UUID,
    query_id: uuid.UUID,
    reason: str,
):
    n = Notification(
        user_id=user_id,
        type="moderation",
        title="Query flagged for review",
        body=f"Your query was flagged: {reason}",
        data={"query_id": str(query_id)},
    )
    db.add(n)
    logger.info(f"Notification: moderation for user {user_id}")
