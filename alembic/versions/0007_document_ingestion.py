"""Add bounded document ingestion runs and source-linked chunks.

Revision ID: 0007_document_ingestion
Revises: 0006_knowledge_sources
Create Date: 2026-09-01
"""

from typing import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0007_document_ingestion"
down_revision: str | Sequence[str] | None = "0006_knowledge_sources"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "ingestion_runs",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("project_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("source_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("source_checksum_sha256", sa.String(length=64), nullable=False),
        sa.Column(
            "status",
            sa.String(length=16),
            server_default=sa.text("'running'"),
            nullable=False,
        ),
        sa.Column(
            "chunk_count",
            sa.Integer(),
            server_default=sa.text("0"),
            nullable=False,
        ),
        sa.Column("error_message", sa.String(length=512), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "length(source_checksum_sha256) = 64",
            name="ck_ingestion_runs_source_checksum_sha256_length",
        ),
        sa.CheckConstraint(
            "chunk_count >= 0",
            name="ck_ingestion_runs_chunk_count_non_negative",
        ),
        sa.CheckConstraint(
            "status IN ('running', 'completed', 'failed')",
            name="ck_ingestion_runs_status",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["source_id"], ["knowledge_sources.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_ingestion_runs_project_created_at",
        "ingestion_runs",
        ["project_id", "created_at"],
    )
    op.create_index(
        "ix_ingestion_runs_source_created_at",
        "ingestion_runs",
        ["source_id", "created_at"],
    )

    op.create_table(
        "document_chunks",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("ingestion_run_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("project_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("source_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("heading", sa.String(length=512), nullable=True),
        sa.Column("location", sa.String(length=512), nullable=False),
        sa.Column("line_start", sa.Integer(), nullable=False),
        sa.Column("line_end", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("character_count", sa.Integer(), nullable=False),
        sa.Column("word_count", sa.Integer(), nullable=False),
        sa.Column("checksum_sha256", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "chunk_index >= 0",
            name="ck_document_chunks_index_non_negative",
        ),
        sa.CheckConstraint(
            "line_start > 0",
            name="ck_document_chunks_line_start_positive",
        ),
        sa.CheckConstraint(
            "line_end >= line_start",
            name="ck_document_chunks_line_range",
        ),
        sa.CheckConstraint(
            "character_count > 0",
            name="ck_document_chunks_character_count_positive",
        ),
        sa.CheckConstraint(
            "word_count > 0",
            name="ck_document_chunks_word_count_positive",
        ),
        sa.CheckConstraint(
            "length(checksum_sha256) = 64",
            name="ck_document_chunks_checksum_sha256_length",
        ),
        sa.ForeignKeyConstraint(
            ["ingestion_run_id"], ["ingestion_runs.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["source_id"], ["knowledge_sources.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "ingestion_run_id",
            "chunk_index",
            name="uq_document_chunks_ingestion_index",
        ),
    )
    op.create_index(
        "ix_document_chunks_project_source_index",
        "document_chunks",
        ["project_id", "source_id", "chunk_index"],
    )
    op.create_index(
        "ix_document_chunks_ingestion_index",
        "document_chunks",
        ["ingestion_run_id", "chunk_index"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_document_chunks_ingestion_index",
        table_name="document_chunks",
    )
    op.drop_index(
        "ix_document_chunks_project_source_index",
        table_name="document_chunks",
    )
    op.drop_table("document_chunks")
    op.drop_index(
        "ix_ingestion_runs_source_created_at",
        table_name="ingestion_runs",
    )
    op.drop_index(
        "ix_ingestion_runs_project_created_at",
        table_name="ingestion_runs",
    )
    op.drop_table("ingestion_runs")
