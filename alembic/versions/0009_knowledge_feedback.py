"""Add privacy-bounded knowledge feedback and issue reports.

Revision ID: 0009_knowledge_feedback
Revises: 0008_semantic_search
Create Date: 2026-09-15
"""

from typing import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0009_knowledge_feedback"
down_revision: str | Sequence[str] | None = "0008_semantic_search"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "knowledge_feedback",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("project_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("actor_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("rating", sa.String(length=16), nullable=False),
        sa.Column("reason", sa.String(length=32), nullable=True),
        sa.Column("answer_status", sa.String(length=16), nullable=False),
        sa.Column("citation_count", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "rating IN ('helpful', 'not_helpful')",
            name="ck_knowledge_feedback_rating",
        ),
        sa.CheckConstraint(
            "answer_status IN ('answered', 'refused')",
            name="ck_knowledge_feedback_answer_status",
        ),
        sa.CheckConstraint(
            "citation_count >= 0 AND citation_count <= 3",
            name="ck_knowledge_feedback_citation_count",
        ),
        sa.CheckConstraint(
            "reason IS NULL OR reason IN "
            "('accurate', 'clear', 'missing_evidence', 'wrong_source', 'other')",
            name="ck_knowledge_feedback_reason",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_knowledge_feedback_project_created_at",
        "knowledge_feedback",
        ["project_id", "created_at"],
    )

    op.create_table(
        "knowledge_error_reports",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("project_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("actor_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("surface", sa.String(length=16), nullable=False),
        sa.Column("category", sa.String(length=32), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "surface IN ('search', 'answer')",
            name="ck_knowledge_error_reports_surface",
        ),
        sa.CheckConstraint(
            "category IN "
            "('wrong_answer', 'missing_evidence', 'wrong_source', 'technical_error', 'other')",
            name="ck_knowledge_error_reports_category",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_knowledge_error_reports_project_created_at",
        "knowledge_error_reports",
        ["project_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_knowledge_error_reports_project_created_at",
        table_name="knowledge_error_reports",
    )
    op.drop_table("knowledge_error_reports")
    op.drop_index(
        "ix_knowledge_feedback_project_created_at",
        table_name="knowledge_feedback",
    )
    op.drop_table("knowledge_feedback")
