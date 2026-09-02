"""Store deterministic chunk embeddings for bounded semantic search.

Revision ID: 0008_semantic_search
Revises: 0007_document_ingestion
Create Date: 2026-09-02
"""

from typing import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0008_semantic_search"
down_revision: str | Sequence[str] | None = "0007_document_ingestion"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("document_chunks") as batch_op:
        batch_op.add_column(sa.Column("embedding_json", sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column("embedding_model", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("embedding_dimensions", sa.Integer(), nullable=True))
        batch_op.create_check_constraint(
            "ck_document_chunks_embedding_metadata",
            "(embedding_json IS NULL AND embedding_model IS NULL AND embedding_dimensions IS NULL) "
            "OR (embedding_json IS NOT NULL AND embedding_model IS NOT NULL AND embedding_dimensions > 0)",
        )


def downgrade() -> None:
    with op.batch_alter_table("document_chunks") as batch_op:
        batch_op.drop_constraint(
            "ck_document_chunks_embedding_metadata",
            type_="check",
        )
        batch_op.drop_column("embedding_dimensions")
        batch_op.drop_column("embedding_model")
        batch_op.drop_column("embedding_json")
