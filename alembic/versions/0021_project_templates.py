"""Add private reusable project and task templates."""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

from alembic import op

revision: str = "0021_project_templates"
down_revision: str | Sequence[str] | None = "0020_user_notifications"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    uuid_type = sa.Uuid(as_uuid=True).with_variant(
        postgresql.UUID(as_uuid=True), "postgresql"
    )
    op.create_table(
        "project_templates",
        sa.Column("id", uuid_type, nullable=False),
        sa.Column("owner_id", uuid_type, nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=False),
        sa.Column("category", sa.String(length=80), nullable=False),
        sa.Column("scope", sa.String(length=1000), nullable=False),
        sa.Column("outputs", sa.JSON(), nullable=False),
        sa.Column("responsible_person", sa.String(length=120), nullable=False),
        sa.Column("work_items_json", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "length(trim(name)) > 0",
            name="ck_project_templates_name_not_blank",
        ),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_project_templates_owner_created",
        "project_templates",
        ["owner_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_project_templates_owner_created", table_name="project_templates")
    op.drop_table("project_templates")
