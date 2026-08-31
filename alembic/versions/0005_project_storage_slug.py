"""Add immutable, unique project storage slugs.

Revision ID: 0005_project_storage_slug
Revises: 0004_project_backups
Create Date: 2026-08-31
"""

from __future__ import annotations

import re
import unicodedata
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "0005_project_storage_slug"
down_revision: str | Sequence[str] | None = "0004_project_backups"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _normalize_project_name(value: str) -> str:
    ascii_value = (
        unicodedata.normalize("NFKD", value.strip())
        .encode("ascii", "ignore")
        .decode("ascii")
    )
    normalized = re.sub(r"[^A-Za-z0-9]+", "-", ascii_value).strip("-").lower()
    return normalized[:64] or "project"


def upgrade() -> None:
    op.add_column(
        "projects",
        sa.Column("storage_slug", sa.String(length=64), nullable=True),
    )

    connection = op.get_bind()
    projects = sa.table(
        "projects",
        sa.column("id", sa.Uuid(as_uuid=True)),
        sa.column("name", sa.String(length=100)),
        sa.column("storage_slug", sa.String(length=64)),
    )
    rows = connection.execute(
        sa.select(projects.c.id, projects.c.name).order_by(projects.c.id)
    ).all()
    used: set[str] = set()
    for project_id, name in rows:
        base = _normalize_project_name(name)
        slug = base
        suffix_length = 8
        identifier = str(project_id).replace("-", "")
        while slug in used:
            suffix = identifier[:suffix_length]
            slug = f"{base[: 63 - len(suffix)].rstrip('-')}-{suffix}"
            suffix_length += 1
        used.add(slug)
        connection.execute(
            projects.update()
            .where(projects.c.id == project_id)
            .values(storage_slug=slug)
        )

    with op.batch_alter_table("projects") as batch_op:
        batch_op.alter_column(
            "storage_slug",
            existing_type=sa.String(length=64),
            nullable=False,
        )
        batch_op.create_unique_constraint(
            "uq_projects_storage_slug",
            ["storage_slug"],
        )


def downgrade() -> None:
    with op.batch_alter_table("projects") as batch_op:
        batch_op.drop_constraint("uq_projects_storage_slug", type_="unique")
        batch_op.drop_column("storage_slug")
