"""Create the normalized Day 4 database schema.

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-08-14
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0001_initial_schema"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("external_ref", sa.String(length=128), nullable=False),
        sa.Column("role", sa.String(length=32), server_default=sa.text("'member'"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("external_ref", name="uq_users_external_ref"),
    )

    op.create_table(
        "projects",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("owner_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.String(length=500), server_default=sa.text("''"), nullable=False),
        sa.Column("status", sa.String(length=32), server_default=sa.text("'active'"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint("length(trim(name)) > 0", name="ck_projects_name_not_blank"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_projects_owner_status", "projects", ["owner_id", "status"])

    op.create_table(
        "files",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("project_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("uploaded_by_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("storage_key", sa.String(length=255), nullable=False),
        sa.Column("media_type", sa.String(length=127), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("checksum_sha256", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint("size_bytes >= 0", name="ck_files_size_non_negative"),
        sa.CheckConstraint("length(checksum_sha256) = 64", name="ck_files_checksum_sha256_length"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["uploaded_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("storage_key", name="uq_files_storage_key"),
    )
    op.create_index("ix_files_project_created_at", "files", ["project_id", "created_at"])

    op.create_table(
        "workflows",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("project_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("created_by_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("status", sa.String(length=32), server_default=sa.text("'draft'"), nullable=False),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint("version > 0", name="ck_workflows_version_positive"),
        sa.CheckConstraint("length(trim(name)) > 0", name="ck_workflows_name_not_blank"),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "project_id",
            "name",
            "version",
            name="uq_workflows_project_name_version",
        ),
    )
    op.create_index("ix_workflows_project_status", "workflows", ["project_id", "status"])

    op.create_table(
        "approvals",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("workflow_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("requested_by_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("approved_by_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("status", sa.String(length=16), server_default=sa.text("'pending'"), nullable=False),
        sa.Column("decision_code", sa.String(length=64), nullable=True),
        sa.Column("requested_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint(
            "status IN ('pending', 'approved', 'rejected', 'cancelled')",
            name="ck_approvals_status",
        ),
        sa.ForeignKeyConstraint(["approved_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["requested_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["workflow_id"], ["workflows.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_approvals_workflow_status", "approvals", ["workflow_id", "status"])

    op.create_table(
        "security_events",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("actor_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("event_code", sa.String(length=64), nullable=False),
        sa.Column("outcome", sa.String(length=16), nullable=False),
        sa.Column("resource_type", sa.String(length=64), nullable=True),
        sa.Column("resource_ref", sa.String(length=128), nullable=True),
        sa.Column("request_ref", sa.String(length=128), nullable=True),
        sa.Column("occurred_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint(
            "outcome IN ('success', 'failure', 'denied')",
            name="ck_security_events_outcome",
        ),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_security_events_actor_occurred_at",
        "security_events",
        ["actor_id", "occurred_at"],
    )
    op.create_index(
        "ix_security_events_code_occurred_at",
        "security_events",
        ["event_code", "occurred_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_security_events_code_occurred_at", table_name="security_events")
    op.drop_index("ix_security_events_actor_occurred_at", table_name="security_events")
    op.drop_table("security_events")
    op.drop_index("ix_approvals_workflow_status", table_name="approvals")
    op.drop_table("approvals")
    op.drop_index("ix_workflows_project_status", table_name="workflows")
    op.drop_table("workflows")
    op.drop_index("ix_files_project_created_at", table_name="files")
    op.drop_table("files")
    op.drop_index("ix_projects_owner_status", table_name="projects")
    op.drop_table("projects")
    op.drop_table("users")
