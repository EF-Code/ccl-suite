"""Normalized SQLAlchemy models for the CCL Suite foundation.

The schema stores opaque references and operational metadata.  It deliberately
does not model passwords, access tokens, file contents, request bodies, or
free-form personal profiles.
"""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
    Uuid,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp for application-side defaults."""

    return datetime.now(timezone.utc)


class User(Base):
    """Minimal application identity record.

    ``external_ref`` is an opaque identifier supplied by a trusted identity
    boundary.  Passwords, tokens, email addresses, and profile data remain
    outside this database.
    """

    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    external_ref: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    role: Mapped[str] = mapped_column(String(32), nullable=False, default="member")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    projects: Mapped[list[Project]] = relationship(back_populates="owner")
    uploaded_files: Mapped[list[File]] = relationship(
        back_populates="uploaded_by",
        foreign_keys=lambda: [File.uploaded_by_id],
    )
    created_workflows: Mapped[list[Workflow]] = relationship(
        back_populates="created_by",
        foreign_keys=lambda: [Workflow.created_by_id],
    )
    requested_approvals: Mapped[list[Approval]] = relationship(
        back_populates="requested_by",
        foreign_keys=lambda: [Approval.requested_by_id],
    )
    decided_approvals: Mapped[list[Approval]] = relationship(
        back_populates="approved_by",
        foreign_keys=lambda: [Approval.approved_by_id],
    )
    security_events: Mapped[list[SecurityEvent]] = relationship(
        back_populates="actor",
        foreign_keys=lambda: [SecurityEvent.actor_id],
    )


class Project(Base):
    """A user-owned unit containing files and workflow definitions."""

    __tablename__ = "projects"
    __table_args__ = (
        Index("ix_projects_owner_status", "owner_id", "status"),
        CheckConstraint("length(trim(name)) > 0", name="ck_projects_name_not_blank"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    owner_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    owner: Mapped[User] = relationship(back_populates="projects")
    files: Mapped[list[File]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    workflows: Mapped[list[Workflow]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )


class File(Base):
    """Metadata for an object stored outside the relational database.

    The file contents remain on the approved filesystem.  This record stores
    searchable metadata, the latest integrity hash, and lifecycle state.
    """

    __tablename__ = "files"
    __table_args__ = (
        Index("ix_files_project_created_at", "project_id", "created_at"),
        Index("ix_files_project_status", "project_id", "status"),
        UniqueConstraint(
            "project_id",
            "storage_key",
            name="uq_files_project_storage_key",
        ),
        CheckConstraint("size_bytes >= 0", name="ck_files_size_non_negative"),
        CheckConstraint(
            "length(checksum_sha256) = 64", name="ck_files_checksum_sha256_length"
        ),
        CheckConstraint(
            "status IN ('active', 'missing', 'archived')",
            name="ck_files_status",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    uploaded_by_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    extension: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    media_type: Mapped[str] = mapped_column(String(127), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    modified_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    project: Mapped[Project] = relationship(back_populates="files")
    uploaded_by: Mapped[User | None] = relationship(
        back_populates="uploaded_files",
        foreign_keys=[uploaded_by_id],
    )
    history: Mapped[list[FileHistory]] = relationship(
        back_populates="file", cascade="all, delete-orphan", order_by="FileHistory.observed_at"
    )
    versions: Mapped[list[FileVersion]] = relationship(
        back_populates="file",
        cascade="all, delete-orphan",
        order_by="FileVersion.version_number",
    )


class FileHistory(Base):
    """Immutable metadata snapshots observed during inventory scans."""

    __tablename__ = "file_history"
    __table_args__ = (
        Index("ix_file_history_file_observed_at", "file_id", "observed_at"),
        CheckConstraint("size_bytes >= 0", name="ck_file_history_size_non_negative"),
        CheckConstraint(
            "length(checksum_sha256) = 64",
            name="ck_file_history_checksum_sha256_length",
        ),
        CheckConstraint(
            "status IN ('active', 'missing', 'archived')",
            name="ck_file_history_status",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    file_id: Mapped[UUID] = mapped_column(
        ForeignKey("files.id", ondelete="CASCADE"), nullable=False
    )
    event_code: Mapped[str] = mapped_column(String(24), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    extension: Mapped[str] = mapped_column(String(32), nullable=False, default="")
    media_type: Mapped[str] = mapped_column(String(127), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    modified_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    observed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )

    file: Mapped[File] = relationship(back_populates="history")


class FileVersion(Base):
    """Immutable metadata for one version of a project file."""

    __tablename__ = "file_versions"
    __table_args__ = (
        UniqueConstraint(
            "file_id",
            "version_number",
            name="uq_file_versions_file_version",
        ),
        Index("ix_file_versions_file_created_at", "file_id", "created_at"),
        CheckConstraint(
            "version_number > 0",
            name="ck_file_versions_version_positive",
        ),
        CheckConstraint("size_bytes >= 0", name="ck_file_versions_size_non_negative"),
        CheckConstraint(
            "length(checksum_sha256) = 64",
            name="ck_file_versions_checksum_sha256_length",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    file_id: Mapped[UUID] = mapped_column(
        ForeignKey("files.id", ondelete="CASCADE"), nullable=False
    )
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    media_type: Mapped[str] = mapped_column(String(127), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    modified_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    is_original: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )

    file: Mapped[File] = relationship(back_populates="versions")


class Workflow(Base):
    """Versioned workflow definition attached to one project."""

    __tablename__ = "workflows"
    __table_args__ = (
        UniqueConstraint("project_id", "name", "version", name="uq_workflows_project_name_version"),
        Index("ix_workflows_project_status", "project_id", "status"),
        CheckConstraint("version > 0", name="ck_workflows_version_positive"),
        CheckConstraint("length(trim(name)) > 0", name="ck_workflows_name_not_blank"),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    created_by_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="draft")
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    project: Mapped[Project] = relationship(back_populates="workflows")
    created_by: Mapped[User | None] = relationship(
        back_populates="created_workflows",
        foreign_keys=[created_by_id],
    )
    approvals: Mapped[list[Approval]] = relationship(
        back_populates="workflow", cascade="all, delete-orphan"
    )


class Approval(Base):
    """A review decision for one workflow version."""

    __tablename__ = "approvals"
    __table_args__ = (
        Index("ix_approvals_workflow_status", "workflow_id", "status"),
        CheckConstraint(
            "status IN ('pending', 'approved', 'rejected', 'cancelled')",
            name="ck_approvals_status",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    workflow_id: Mapped[UUID] = mapped_column(
        ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False
    )
    requested_by_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    approved_by_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    decision_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    requested_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    decided_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    workflow: Mapped[Workflow] = relationship(back_populates="approvals")
    requested_by: Mapped[User | None] = relationship(
        back_populates="requested_approvals",
        foreign_keys=[requested_by_id],
    )
    approved_by: Mapped[User | None] = relationship(
        back_populates="decided_approvals",
        foreign_keys=[approved_by_id],
    )


class SecurityEvent(Base):
    """Small, structured security audit record without raw request payloads."""

    __tablename__ = "security_events"
    __table_args__ = (
        Index("ix_security_events_actor_occurred_at", "actor_id", "occurred_at"),
        Index("ix_security_events_code_occurred_at", "event_code", "occurred_at"),
        CheckConstraint(
            "outcome IN ('success', 'failure', 'denied')",
            name="ck_security_events_outcome",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    actor_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    event_code: Mapped[str] = mapped_column(String(64), nullable=False)
    outcome: Mapped[str] = mapped_column(String(16), nullable=False)
    resource_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    resource_ref: Mapped[str | None] = mapped_column(String(128), nullable=True)
    request_ref: Mapped[str | None] = mapped_column(String(128), nullable=True)
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )

    actor: Mapped[User | None] = relationship(
        back_populates="security_events",
        foreign_keys=[actor_id],
    )


__all__ = [
    "Approval",
    "File",
    "FileHistory",
    "FileVersion",
    "Project",
    "SecurityEvent",
    "User",
    "Workflow",
]
