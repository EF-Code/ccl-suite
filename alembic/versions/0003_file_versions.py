"""Add immutable version metadata linked to file records.

Revision ID: 0003_file_versions
Revises: 0002_file_record_tracking
Create Date: 2026-08-26
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0003_file_versions"
down_revision: Union[str, Sequence[str], None] = "0002_file_record_tracking"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "file_versions",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("file_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("storage_key", sa.String(length=512), nullable=False),
        sa.Column("media_type", sa.String(length=127), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("checksum_sha256", sa.String(length=64), nullable=False),
        sa.Column("modified_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_original", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "version_number > 0",
            name="ck_file_versions_version_positive",
        ),
        sa.CheckConstraint("size_bytes >= 0", name="ck_file_versions_size_non_negative"),
        sa.CheckConstraint(
            "length(checksum_sha256) = 64",
            name="ck_file_versions_checksum_sha256_length",
        ),
        sa.ForeignKeyConstraint(["file_id"], ["files.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "file_id",
            "version_number",
            name="uq_file_versions_file_version",
        ),
    )
    op.create_index(
        "ix_file_versions_file_created_at",
        "file_versions",
        ["file_id", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_file_versions_file_created_at", table_name="file_versions")
    op.drop_table("file_versions")
