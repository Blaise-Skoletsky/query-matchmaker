"""Drop group_size column from queries table

Revision ID: 006
Revises: 005
Create Date: 2026-03-13
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "006"
down_revision: Union[str, None] = "005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("queries", "group_size")


def downgrade() -> None:
    op.add_column(
        "queries",
        sa.Column("group_size", sa.Integer(), nullable=True, server_default="2"),
    )
