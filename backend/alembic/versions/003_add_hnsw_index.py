"""Add HNSW index on embeddings and composite index on (status, intent)

Revision ID: 003
Revises: 002
Create Date: 2026-03-06
"""
from typing import Sequence, Union

from alembic import op

revision: str = "003"
down_revision: Union[str, None] = "002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # HNSW index for approximate nearest neighbor search — O(log n) vs O(n)
    op.execute(
        "CREATE INDEX ix_queries_embedding_hnsw ON queries "
        "USING hnsw (embedding vector_cosine_ops) "
        "WITH (m = 16, ef_construction = 64)"
    )
    # Composite B-tree index for fast pre-filtering before vector search
    op.execute(
        "CREATE INDEX ix_queries_status_intent ON queries (status, intent)"
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_queries_status_intent")
    op.execute("DROP INDEX IF EXISTS ix_queries_embedding_hnsw")
