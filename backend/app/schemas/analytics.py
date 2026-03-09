import uuid
from datetime import date, datetime

from pydantic import BaseModel


class AnalyticsSnapshotResponse(BaseModel):
    id: uuid.UUID
    period: str
    snapshot_date: date
    total_users: int
    total_queries: int
    active_queries: int
    total_matches: int
    accepted_matches: int
    rejected_matches: int
    acceptance_rate: float | None
    avg_compatibility_score: float | None
    total_messages: int
    top_categories: dict | None
    top_intents: dict | None
    created_at: datetime

    model_config = {"from_attributes": True}
