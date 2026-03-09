import uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import String, Integer, Float, Date, DateTime, func
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class AnalyticsSnapshot(Base):
    __tablename__ = "analytics_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    period: Mapped[str] = mapped_column(String(20), nullable=False)  # daily, weekly
    snapshot_date = mapped_column(Date, nullable=False, index=True)
    total_users: Mapped[int] = mapped_column(Integer, default=0)
    total_queries: Mapped[int] = mapped_column(Integer, default=0)
    active_queries: Mapped[int] = mapped_column(Integer, default=0)
    total_matches: Mapped[int] = mapped_column(Integer, default=0)
    accepted_matches: Mapped[int] = mapped_column(Integer, default=0)
    rejected_matches: Mapped[int] = mapped_column(Integer, default=0)
    acceptance_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    avg_compatibility_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    total_messages: Mapped[int] = mapped_column(Integer, default=0)
    top_categories = mapped_column(JSONB, nullable=True)
    top_intents = mapped_column(JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
