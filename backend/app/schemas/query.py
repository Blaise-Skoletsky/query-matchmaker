import uuid
from datetime import datetime

from pydantic import BaseModel


class QueryCreate(BaseModel):
    raw_text: str
    location: str | None = None
    latitude: float | None = None
    longitude: float | None = None


class QueryResponse(BaseModel):
    id: uuid.UUID
    raw_text: str
    intent: str | None
    category: str | None
    attributes: dict | None
    complementary_intents: list | None
    location: str | None
    status: str
    created_at: datetime

    model_config = {"from_attributes": True}
