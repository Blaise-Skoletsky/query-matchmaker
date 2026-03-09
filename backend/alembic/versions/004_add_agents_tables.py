"""Add notifications, analytics_snapshots, and moderation_logs tables

Revision ID: 004
Revises: 003
Create Date: 2026-03-08
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "004"
down_revision: Union[str, None] = "003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "notifications",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("user_id", sa.UUID(), sa.ForeignKey("users.id"), nullable=False, index=True),
        sa.Column("type", sa.String(50), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("data", sa.JSON()),
        sa.Column("read", sa.Boolean(), default=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "analytics_snapshots",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("period", sa.String(20), nullable=False),
        sa.Column("snapshot_date", sa.Date(), nullable=False, index=True),
        sa.Column("total_users", sa.Integer(), default=0),
        sa.Column("total_queries", sa.Integer(), default=0),
        sa.Column("active_queries", sa.Integer(), default=0),
        sa.Column("total_matches", sa.Integer(), default=0),
        sa.Column("accepted_matches", sa.Integer(), default=0),
        sa.Column("rejected_matches", sa.Integer(), default=0),
        sa.Column("acceptance_rate", sa.Float()),
        sa.Column("avg_compatibility_score", sa.Float()),
        sa.Column("total_messages", sa.Integer(), default=0),
        sa.Column("top_categories", sa.JSON()),
        sa.Column("top_intents", sa.JSON()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "moderation_logs",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("query_id", sa.UUID(), sa.ForeignKey("queries.id"), nullable=False),
        sa.Column("flagged", sa.Boolean(), default=False),
        sa.Column("reason", sa.Text()),
        sa.Column("category", sa.String(50)),
        sa.Column("confidence", sa.Float()),
        sa.Column("auto_action", sa.String(20)),
        sa.Column("details", sa.JSON()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("moderation_logs")
    op.drop_table("analytics_snapshots")
    op.drop_table("notifications")
