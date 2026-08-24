"""Add searchable file metadata and immutable inventory history.

Revision ID: 0002_file_record_tracking
Revises: 0001_initial_schema
Create Date: 2026-08-24
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0002_file_record_tracking"
down_revision: Union[str, Sequence[str], None] = "0001_initial_schema"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    files_columns = [
        sa.Column("name", sa.String(length=255), server_default=sa.text("''"), nullable=False),
        sa.Column("extension", sa.String(length=32), server_default=sa.text("''"), nullable=False),
        sa.Column(
            "modified_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.String(length=24),
            server_default=sa.text("'active'"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
    ]
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("files", recreate="always") as batch_op:
            batch_op.drop_constraint("uq_files_storage_key", type_="unique")
            batch_op.alter_column(
                "storage_key",
                existing_type=sa.String(length=255),
                type_=sa.String(length=512),
                existing_nullable=False,
            )
            for column in files_columns:
                batch_op.add_column(column)
            batch_op.create_check_constraint(
                "ck_files_status",
                "status IN ('active', 'missing', 'archived')",
            )
            batch_op.create_unique_constraint(
                "uq_files_project_storage_key",
                ["project_id", "storage_key"],
            )
    else:
        op.drop_constraint("uq_files_storage_key", "files", type_="unique")
        op.alter_column(
            "files",
            "storage_key",
            existing_type=sa.String(length=255),
            type_=sa.String(length=512),
            existing_nullable=False,
        )
        for column in files_columns:
            op.add_column("files", column)
        op.create_check_constraint(
            "ck_files_status",
            "files",
            "status IN ('active', 'missing', 'archived')",
        )
        op.create_unique_constraint(
            "uq_files_project_storage_key",
            "files",
            ["project_id", "storage_key"],
        )
    op.create_index("ix_files_project_status", "files", ["project_id", "status"])

    op.create_table(
        "file_history",
        sa.Column("id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("file_id", sa.Uuid(as_uuid=True), nullable=False),
        sa.Column("event_code", sa.String(length=24), nullable=False),
        sa.Column("storage_key", sa.String(length=512), nullable=False),
        sa.Column("name", sa.String(length=255), server_default=sa.text("''"), nullable=False),
        sa.Column("extension", sa.String(length=32), server_default=sa.text("''"), nullable=False),
        sa.Column("media_type", sa.String(length=127), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("checksum_sha256", sa.String(length=64), nullable=False),
        sa.Column("modified_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column(
            "observed_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.CheckConstraint("size_bytes >= 0", name="ck_file_history_size_non_negative"),
        sa.CheckConstraint(
            "length(checksum_sha256) = 64",
            name="ck_file_history_checksum_sha256_length",
        ),
        sa.CheckConstraint(
            "status IN ('active', 'missing', 'archived')",
            name="ck_file_history_status",
        ),
        sa.ForeignKeyConstraint(["file_id"], ["files.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_file_history_file_observed_at",
        "file_history",
        ["file_id", "observed_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_file_history_file_observed_at", table_name="file_history")
    op.drop_table("file_history")
    op.drop_index("ix_files_project_status", table_name="files")
    if op.get_bind().dialect.name == "sqlite":
        with op.batch_alter_table("files", recreate="always") as batch_op:
            batch_op.drop_constraint("uq_files_project_storage_key", type_="unique")
            batch_op.drop_constraint("ck_files_status", type_="check")
            for column_name in ("updated_at", "status", "modified_at", "extension", "name"):
                batch_op.drop_column(column_name)
            batch_op.alter_column(
                "storage_key",
                existing_type=sa.String(length=512),
                type_=sa.String(length=255),
                existing_nullable=False,
            )
            batch_op.create_unique_constraint("uq_files_storage_key", ["storage_key"])
    else:
        op.drop_constraint("uq_files_project_storage_key", "files", type_="unique")
        op.drop_constraint("ck_files_status", "files", type_="check")
        for column_name in ("updated_at", "status", "modified_at", "extension", "name"):
            op.drop_column("files", column_name)
        op.alter_column(
            "files",
            "storage_key",
            existing_type=sa.String(length=512),
            type_=sa.String(length=255),
            existing_nullable=False,
        )
        op.create_unique_constraint("uq_files_storage_key", "files", ["storage_key"])
