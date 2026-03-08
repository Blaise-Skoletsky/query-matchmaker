import uuid
from datetime import datetime

from pydantic import BaseModel


class MessageCreate(BaseModel):
    content: str


class MessageResponse(BaseModel):
    id: uuid.UUID
    chatroom_id: uuid.UUID
    user_id: uuid.UUID
    user_display_name: str | None = None
    content: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ChatroomResponse(BaseModel):
    id: uuid.UUID
    name: str
    created_at: datetime

    model_config = {"from_attributes": True}


class ChatroomMemberInfo(BaseModel):
    user_id: uuid.UUID
    display_name: str


class ChatroomDetailResponse(BaseModel):
    id: uuid.UUID
    name: str
    created_at: datetime
    members: list[ChatroomMemberInfo]
