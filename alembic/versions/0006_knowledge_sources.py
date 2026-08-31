"""Add the approved knowledge-source register.

Revision ID: 0006_knowledge_sources
Revises: 0005_project_storage_slug
Create Date: 2026-08-31
"""

from typing import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0006_knowledge_sources"
down_revision: str | Sequence[str] | None = "0005_project_storage_slug"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "knowledge_sources",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("project_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("file_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("owner_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("created_by_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("reviewed_by_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("source_type", sa.String(length=32), nullable=False),
        sa.Column("sensitivity", sa.String(length=16), nullable=False),
        sa.Column(
            "approval_status",
            sa.String(length=16),
            server_default=sa.text("'pending'"),
            nullable=False,
        ),
        sa.Column("rejection_reason", sa.String(length=255), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "source_type IN ('sop', 'prompt_bank', 'style_guide', 'project_rule')",
            name="ck_knowledge_sources_source_type",
        ),
        sa.CheckConstraint(
            "sensitivity IN ('public', 'internal', 'confidential', 'restricted')",
            name="ck_knowledge_sources_sensitivity",
        ),
        sa.CheckConstraint(
            "approval_status IN ('pending', 'approved', 'rejected')",
            name="ck_knowledge_sources_approval_status",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["file_id"], ["files.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["owner_id"], ["users.id"], ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"], ["users.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["reviewed_by_id"], ["users.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "project_id",
            "file_id",
            name="uq_knowledge_sources_project_file",
        ),
    )
    op.create_index(
        "ix_knowledge_sources_project_status",
        "knowledge_sources",
        ["project_id", "approval_status"],
    )
    op.create_index(
        "ix_knowledge_sources_owner_status",
        "knowledge_sources",
        ["owner_id", "approval_status"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_knowledge_sources_owner_status",
        table_name="knowledge_sources",
    )
    op.drop_index(
        "ix_knowledge_sources_project_status",
        table_name="knowledge_sources",
    )
    op.drop_table("knowledge_sources")
