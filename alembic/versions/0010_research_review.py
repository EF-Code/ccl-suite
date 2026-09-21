"""Persist human review, correction, verification, and approval state."""

from typing import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = "0010_research_review"
down_revision: str | Sequence[str] | None = "0009_knowledge_feedback"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "research_reviews",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("project_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("created_by_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("approved_by_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("source_title", sa.String(length=200), nullable=False),
        sa.Column("source_reference", sa.String(length=512), nullable=False),
        sa.Column("source_date", sa.Date(), nullable=True),
        sa.Column("target_scope", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
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
            "status IN ('needs_review', 'changes_requested', 'verified', 'approved')",
            name="ck_research_reviews_status",
        ),
        sa.ForeignKeyConstraint(
            ["project_id"], ["projects.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["created_by_id"], ["users.id"], ondelete="SET NULL"
        ),
        sa.ForeignKeyConstraint(
            ["approved_by_id"], ["users.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_research_reviews_project_status",
        "research_reviews",
        ["project_id", "status"],
    )

    op.create_table(
        "research_review_claims",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("review_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("claim_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("claim", sa.String(length=500), nullable=False),
        sa.Column("classification", sa.String(length=16), nullable=False),
        sa.Column("source_title", sa.String(length=200), nullable=False),
        sa.Column("source_reference", sa.String(length=512), nullable=False),
        sa.Column("source_date", sa.Date(), nullable=True),
        sa.Column("passage", sa.Text(), nullable=False),
        sa.Column("scope", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("correction_note", sa.String(length=500), nullable=True),
        sa.Column("corrected_claim", sa.String(length=500), nullable=True),
        sa.Column("corrected_scope", sa.JSON(), nullable=True),
        sa.Column("verified_by_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
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
            "status IN ('needs_review', 'changes_requested', 'verified')",
            name="ck_research_review_claims_status",
        ),
        sa.CheckConstraint(
            "classification IN ('factual', 'heading', 'instruction', 'opinion', 'creative')",
            name="ck_research_review_claims_classification",
        ),
        sa.ForeignKeyConstraint(
            ["review_id"], ["research_reviews.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["verified_by_id"], ["users.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "review_id", "claim_id", name="uq_research_review_claims_review_claim"
        ),
    )
    op.create_index(
        "ix_research_review_claims_review_status",
        "research_review_claims",
        ["review_id", "status"],
    )

    op.create_table(
        "research_review_events",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("review_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("claim_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("actor_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("action", sa.String(length=32), nullable=False),
        sa.Column("note", sa.String(length=500), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "action IN ('submitted', 'correction_requested', 'verified', 'approved', 'exported')",
            name="ck_research_review_events_action",
        ),
        sa.ForeignKeyConstraint(
            ["review_id"], ["research_reviews.id"], ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["actor_id"], ["users.id"], ondelete="SET NULL"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_research_review_events_review_created_at",
        "research_review_events",
        ["review_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_research_review_events_review_created_at",
        table_name="research_review_events",
    )
    op.drop_table("research_review_events")
    op.drop_index(
        "ix_research_review_claims_review_status",
        table_name="research_review_claims",
    )
    op.drop_table("research_review_claims")
    op.drop_index("ix_research_reviews_project_status", table_name="research_reviews")
    op.drop_table("research_reviews")
