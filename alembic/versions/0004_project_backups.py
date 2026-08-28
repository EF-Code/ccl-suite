"""Add persisted project backup metadata.

Revision ID: 0004_project_backups
Revises: 0003_file_versions
Create Date: 2026-08-28
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0004_project_backups"
down_revision: Union[str, Sequence[str], None] = "0003_file_versions"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "backups",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("project_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("created_by_id", sa.Uuid(as_uuid=True), nullable=True),
        sa.Column("artifact_key", sa.String(length=512), nullable=False),
        sa.Column("manifest_key", sa.String(length=512), nullable=False),
        sa.Column("archive_size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("file_count", sa.Integer(), nullable=False),
        sa.Column("total_bytes", sa.BigInteger(), nullable=False),
        sa.Column("archive_checksum_sha256", sa.String(length=64), nullable=False),
        sa.Column("manifest_checksum_sha256", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=16), server_default=sa.text("'created'"), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("restored_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "archive_size_bytes >= 0",
            name="ck_backups_archive_size_non_negative",
        ),
        sa.CheckConstraint("file_count >= 0", name="ck_backups_file_count_non_negative"),
        sa.CheckConstraint("total_bytes >= 0", name="ck_backups_total_bytes_non_negative"),
        sa.CheckConstraint(
            "length(archive_checksum_sha256) = 64",
            name="ck_backups_archive_checksum_sha256_length",
        ),
        sa.CheckConstraint(
            "length(manifest_checksum_sha256) = 64",
            name="ck_backups_manifest_checksum_sha256_length",
        ),
        sa.CheckConstraint(
            "status IN ('created', 'verified', 'restored')",
            name="ck_backups_status",
        ),
        sa.ForeignKeyConstraint(["created_by_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["project_id"], ["projects.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("artifact_key", name="uq_backups_artifact_key"),
        sa.UniqueConstraint("manifest_key", name="uq_backups_manifest_key"),
    )
    op.create_index(
        "ix_backups_project_created_at",
        "backups",
        ["project_id", "created_at"],
    )
    op.create_index("ix_backups_project_status", "backups", ["project_id", "status"])


def downgrade() -> None:
    op.drop_index("ix_backups_project_status", table_name="backups")
    op.drop_index("ix_backups_project_created_at", table_name="backups")
    op.drop_table("backups")
