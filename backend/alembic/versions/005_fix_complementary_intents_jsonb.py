"""Cast complementary_intents column from json to jsonb

Revision ID: 005
Revises: 004
Create Date: 2026-03-11
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "005"
down_revision: Union[str, None] = "004"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE queries ALTER COLUMN complementary_intents TYPE jsonb USING complementary_intents::text::jsonb"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE queries ALTER COLUMN complementary_intents TYPE json USING complementary_intents::text::json"
    )
