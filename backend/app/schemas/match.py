import uuid
from datetime import datetime

from pydantic import BaseModel

from app.schemas.query import QueryResponse


class MatchQueryResponse(BaseModel):
    query: QueryResponse

    model_config = {"from_attributes": True}


class MatchResponse(BaseModel):
    id: uuid.UUID
    status: str
    compatibility_score: float | None
    reasoning: str | None
    chatroom_id: uuid.UUID | None
    created_at: datetime
    match_queries: list[MatchQueryResponse]

    model_config = {"from_attributes": True}
