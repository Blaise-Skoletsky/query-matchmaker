import uuid
from datetime import datetime

from pydantic import BaseModel


class NotificationResponse(BaseModel):
    id: uuid.UUID
    type: str
    title: str
    body: str
    data: dict | None
    read: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class NotificationCount(BaseModel):
    unread: int
    total: int
