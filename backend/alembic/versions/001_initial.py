"""Initial schema

Revision ID: 001
Revises:
Create Date: 2026-03-05
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    op.create_table(
        "users",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("email", sa.String(255), unique=True, nullable=False, index=True),
        sa.Column("display_name", sa.String(100), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "queries",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("user_id", sa.UUID(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("raw_text", sa.Text(), nullable=False),
        sa.Column("intent", sa.String(50)),
        sa.Column("category", sa.String(100)),
        sa.Column("attributes", sa.JSON()),
        sa.Column("complementary_intents", sa.JSON()),
        sa.Column("required_match_attributes", sa.JSON()),
        sa.Column("preferred_match_attributes", sa.JSON()),
        sa.Column("location", sa.String(255)),
        sa.Column("latitude", sa.Float()),
        sa.Column("longitude", sa.Float()),
        sa.Column("embedding", Vector(384)),
        sa.Column("group_size", sa.Integer(), default=2),
        sa.Column("status", sa.String(20), default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
    )

    op.create_table(
        "chatrooms",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "matches",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("chatroom_id", sa.UUID(), sa.ForeignKey("chatrooms.id")),
        sa.Column("status", sa.String(20), default="pending"),
        sa.Column("compatibility_score", sa.Float()),
        sa.Column("reasoning", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "match_queries",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("match_id", sa.UUID(), sa.ForeignKey("matches.id"), nullable=False),
        sa.Column("query_id", sa.UUID(), sa.ForeignKey("queries.id"), nullable=False),
    )

    op.create_table(
        "chatroom_members",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("chatroom_id", sa.UUID(), sa.ForeignKey("chatrooms.id"), nullable=False),
        sa.Column("user_id", sa.UUID(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("joined_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )

    op.create_table(
        "messages",
        sa.Column("id", sa.UUID(), primary_key=True),
        sa.Column("chatroom_id", sa.UUID(), sa.ForeignKey("chatrooms.id"), nullable=False),
        sa.Column("user_id", sa.UUID(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("messages")
    op.drop_table("chatroom_members")
    op.drop_table("match_queries")
    op.drop_table("matches")
    op.drop_table("chatrooms")
    op.drop_table("queries")
    op.drop_table("users")
    op.execute("DROP EXTENSION IF EXISTS vector")
