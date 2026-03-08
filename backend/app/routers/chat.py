import uuid

from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.database import get_db, async_session
from app.models.user import User
from app.models.chat import Chatroom, ChatroomMember, Message
from app.schemas.chat import ChatroomResponse, ChatroomDetailResponse, ChatroomMemberInfo, MessageResponse
from app.services.auth import get_current_user
from app.ws.manager import manager

router = APIRouter(tags=["chat"])


async def _verify_membership(db: AsyncSession, chatroom_id: uuid.UUID, user_id: uuid.UUID):
    stmt = select(ChatroomMember).where(
        ChatroomMember.chatroom_id == chatroom_id,
        ChatroomMember.user_id == user_id,
    )
    result = await db.execute(stmt)
    if not result.scalar_one_or_none():
        raise HTTPException(status_code=403, detail="Not a member of this chatroom")


@router.get("/api/chatrooms", response_model=list[ChatroomResponse])
async def list_chatrooms(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    stmt = (
        select(Chatroom)
        .join(ChatroomMember)
        .where(ChatroomMember.user_id == user.id)
        .order_by(Chatroom.created_at.desc())
    )
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/api/chatrooms/{chatroom_id}", response_model=ChatroomDetailResponse)
async def get_chatroom(
    chatroom_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await _verify_membership(db, chatroom_id, user.id)
    chatroom = await db.get(Chatroom, chatroom_id)
    if not chatroom:
        raise HTTPException(status_code=404, detail="Chatroom not found")
    await db.refresh(chatroom, ["members"])
    members = []
    for m in chatroom.members:
        member_user = await db.get(User, m.user_id)
        if member_user:
            members.append(ChatroomMemberInfo(user_id=member_user.id, display_name=member_user.display_name))
    return ChatroomDetailResponse(
        id=chatroom.id,
        name=chatroom.name,
        created_at=chatroom.created_at,
        members=members,
    )


@router.get("/api/chatrooms/{chatroom_id}/messages", response_model=list[MessageResponse])
async def get_messages(
    chatroom_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user),
):
    await _verify_membership(db, chatroom_id, user.id)
    stmt = (
        select(Message)
        .options(selectinload(Message.user))
        .where(Message.chatroom_id == chatroom_id)
        .order_by(Message.created_at.asc())
    )
    result = await db.execute(stmt)
    messages = result.scalars().all()
    return [
        MessageResponse(
            id=m.id,
            chatroom_id=m.chatroom_id,
            user_id=m.user_id,
            user_display_name=m.user.display_name,
            content=m.content,
            created_at=m.created_at,
        )
        for m in messages
    ]


@router.websocket("/ws/chat/{room_id}")
async def websocket_chat(ws: WebSocket, room_id: uuid.UUID):
    token = ws.query_params.get("token")
    if not token:
        await ws.close(code=4001, reason="Missing token")
        return

    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        user_id = uuid.UUID(payload["sub"])
    except (JWTError, ValueError):
        await ws.close(code=4001, reason="Invalid token")
        return

    async with async_session() as db:
        stmt = select(ChatroomMember).where(
            ChatroomMember.chatroom_id == room_id,
            ChatroomMember.user_id == user_id,
        )
        result = await db.execute(stmt)
        if not result.scalar_one_or_none():
            await ws.close(code=4003, reason="Not a member")
            return

        user = await db.get(User, user_id)
        display_name = user.display_name if user else "Unknown"

    await manager.connect(room_id, user_id, ws)
    try:
        while True:
            data = await ws.receive_json()
            content = data.get("content", "").strip()
            if not content:
                continue

            async with async_session() as db:
                msg = Message(chatroom_id=room_id, user_id=user_id, content=content)
                db.add(msg)
                await db.commit()
                await db.refresh(msg)

                await manager.publish(
                    room_id,
                    {
                        "id": str(msg.id),
                        "chatroom_id": str(room_id),
                        "user_id": str(user_id),
                        "user_display_name": display_name,
                        "content": content,
                        "created_at": msg.created_at.isoformat(),
                    },
                )
    except WebSocketDisconnect:
        await manager.disconnect(room_id, user_id)
