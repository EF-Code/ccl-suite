"""Normalized SQLAlchemy models for the CCL Suite foundation.

The schema stores opaque references and operational metadata.  It deliberately
does not model passwords, access tokens, file contents, request bodies, or
free-form personal profiles.
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
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
    created_backups: Mapped[list[Backup]] = relationship(
        back_populates="created_by",
        foreign_keys=lambda: [Backup.created_by_id],
    )
    owned_knowledge_sources: Mapped[list[KnowledgeSource]] = relationship(
        back_populates="owner",
        foreign_keys=lambda: [KnowledgeSource.owner_id],
    )
    created_knowledge_sources: Mapped[list[KnowledgeSource]] = relationship(
        back_populates="created_by",
        foreign_keys=lambda: [KnowledgeSource.created_by_id],
    )
    reviewed_knowledge_sources: Mapped[list[KnowledgeSource]] = relationship(
        back_populates="reviewed_by",
        foreign_keys=lambda: [KnowledgeSource.reviewed_by_id],
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
    knowledge_feedback: Mapped[list[KnowledgeFeedback]] = relationship(
        back_populates="actor",
        foreign_keys=lambda: [KnowledgeFeedback.actor_id],
    )
    knowledge_error_reports: Mapped[list[KnowledgeErrorReport]] = relationship(
        back_populates="actor",
        foreign_keys=lambda: [KnowledgeErrorReport.actor_id],
    )
    created_research_reviews: Mapped[list[ResearchReview]] = relationship(
        back_populates="created_by",
        foreign_keys=lambda: [ResearchReview.created_by_id],
    )
    approved_research_reviews: Mapped[list[ResearchReview]] = relationship(
        back_populates="approved_by",
        foreign_keys=lambda: [ResearchReview.approved_by_id],
    )
    verified_research_claims: Mapped[list[ResearchReviewClaim]] = relationship(
        back_populates="verified_by",
        foreign_keys=lambda: [ResearchReviewClaim.verified_by_id],
    )
    research_review_events: Mapped[list[ResearchReviewEvent]] = relationship(
        back_populates="actor",
        foreign_keys=lambda: [ResearchReviewEvent.actor_id],
    )


class Project(Base):
    """A user-owned unit containing intake metadata and workflow definitions."""

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
    storage_slug: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    description: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    category: Mapped[str] = mapped_column(String(80), nullable=False, default="general")
    scope: Mapped[str] = mapped_column(String(1000), nullable=False, default="")
    deadline: Mapped[date | None] = mapped_column(Date, nullable=True)
    outputs: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    responsible_person: Mapped[str] = mapped_column(String(120), nullable=False, default="")
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
    backups: Mapped[list[Backup]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    knowledge_sources: Mapped[list[KnowledgeSource]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    ingestion_runs: Mapped[list[IngestionRun]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    document_chunks: Mapped[list[DocumentChunk]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    knowledge_feedback: Mapped[list[KnowledgeFeedback]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    knowledge_error_reports: Mapped[list[KnowledgeErrorReport]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )
    research_reviews: Mapped[list[ResearchReview]] = relationship(
        back_populates="project", cascade="all, delete-orphan"
    )


class Backup(Base):
    """Metadata for an immutable project archive stored outside project data."""

    __tablename__ = "backups"
    __table_args__ = (
        Index("ix_backups_project_created_at", "project_id", "created_at"),
        Index("ix_backups_project_status", "project_id", "status"),
        CheckConstraint("archive_size_bytes >= 0", name="ck_backups_archive_size_non_negative"),
        CheckConstraint("file_count >= 0", name="ck_backups_file_count_non_negative"),
        CheckConstraint("total_bytes >= 0", name="ck_backups_total_bytes_non_negative"),
        CheckConstraint(
            "length(archive_checksum_sha256) = 64",
            name="ck_backups_archive_checksum_sha256_length",
        ),
        CheckConstraint(
            "length(manifest_checksum_sha256) = 64",
            name="ck_backups_manifest_checksum_sha256_length",
        ),
        CheckConstraint(
            "status IN ('created', 'verified', 'restored')",
            name="ck_backups_status",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    created_by_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    artifact_key: Mapped[str] = mapped_column(String(512), nullable=False, unique=True)
    manifest_key: Mapped[str] = mapped_column(String(512), nullable=False, unique=True)
    archive_size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    file_count: Mapped[int] = mapped_column(Integer, nullable=False)
    total_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    archive_checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    manifest_checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="created")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    restored_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    project: Mapped[Project] = relationship(back_populates="backups")
    created_by: Mapped[User | None] = relationship(
        back_populates="created_backups",
        foreign_keys=[created_by_id],
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
    knowledge_sources: Mapped[list[KnowledgeSource]] = relationship(
        back_populates="file", cascade="all, delete-orphan"
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


class KnowledgeSource(Base):
    """Approved-document metadata for the future company knowledge base.

    This table intentionally references a persisted file instead of storing
    document text.  Text extraction and retrieval are later stages and may
    consume only records returned by the approved-source query helper.
    """

    __tablename__ = "knowledge_sources"
    __table_args__ = (
        UniqueConstraint(
            "project_id",
            "file_id",
            name="uq_knowledge_sources_project_file",
        ),
        Index(
            "ix_knowledge_sources_project_status",
            "project_id",
            "approval_status",
        ),
        Index(
            "ix_knowledge_sources_owner_status",
            "owner_id",
            "approval_status",
        ),
        CheckConstraint(
            "source_type IN ('sop', 'prompt_bank', 'style_guide', 'project_rule')",
            name="ck_knowledge_sources_source_type",
        ),
        CheckConstraint(
            "sensitivity IN ('public', 'internal', 'confidential', 'restricted')",
            name="ck_knowledge_sources_sensitivity",
        ),
        CheckConstraint(
            "approval_status IN ('pending', 'approved', 'rejected')",
            name="ck_knowledge_sources_approval_status",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    file_id: Mapped[UUID] = mapped_column(
        ForeignKey("files.id", ondelete="CASCADE"), nullable=False
    )
    owner_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_by_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_by_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    source_type: Mapped[str] = mapped_column(String(32), nullable=False)
    sensitivity: Mapped[str] = mapped_column(String(16), nullable=False)
    approval_status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="pending"
    )
    rejection_reason: Mapped[str | None] = mapped_column(String(255), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    project: Mapped[Project] = relationship(back_populates="knowledge_sources")
    file: Mapped[File] = relationship(back_populates="knowledge_sources")
    owner: Mapped[User] = relationship(
        back_populates="owned_knowledge_sources",
        foreign_keys=[owner_id],
    )
    created_by: Mapped[User | None] = relationship(
        back_populates="created_knowledge_sources",
        foreign_keys=[created_by_id],
    )
    reviewed_by: Mapped[User | None] = relationship(
        back_populates="reviewed_knowledge_sources",
        foreign_keys=[reviewed_by_id],
    )

    ingestion_runs: Mapped[list[IngestionRun]] = relationship(
        back_populates="source", cascade="all, delete-orphan"
    )
    document_chunks: Mapped[list[DocumentChunk]] = relationship(
        back_populates="source", cascade="all, delete-orphan"
    )


class IngestionRun(Base):
    """One bounded extraction and chunking attempt for an approved source."""

    __tablename__ = "ingestion_runs"
    __table_args__ = (
        Index("ix_ingestion_runs_project_created_at", "project_id", "created_at"),
        Index("ix_ingestion_runs_source_created_at", "source_id", "created_at"),
        CheckConstraint(
            "length(source_checksum_sha256) = 64",
            name="ck_ingestion_runs_source_checksum_sha256_length",
        ),
        CheckConstraint("chunk_count >= 0", name="ck_ingestion_runs_chunk_count_non_negative"),
        CheckConstraint(
            "status IN ('running', 'completed', 'failed')",
            name="ck_ingestion_runs_status",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    source_id: Mapped[UUID] = mapped_column(
        ForeignKey("knowledge_sources.id", ondelete="CASCADE"), nullable=False
    )
    source_checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="running")
    chunk_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    error_message: Mapped[str | None] = mapped_column(String(512), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    project: Mapped[Project] = relationship(back_populates="ingestion_runs")
    source: Mapped[KnowledgeSource] = relationship(back_populates="ingestion_runs")
    chunks: Mapped[list[DocumentChunk]] = relationship(
        back_populates="ingestion_run",
        cascade="all, delete-orphan",
        order_by="DocumentChunk.chunk_index",
    )


class DocumentChunk(Base):
    """A bounded source-linked chunk and its derived retrieval vector."""

    __tablename__ = "document_chunks"
    __table_args__ = (
        UniqueConstraint(
            "ingestion_run_id",
            "chunk_index",
            name="uq_document_chunks_ingestion_index",
        ),
        Index(
            "ix_document_chunks_project_source_index",
            "project_id",
            "source_id",
            "chunk_index",
        ),
        Index("ix_document_chunks_ingestion_index", "ingestion_run_id", "chunk_index"),
        CheckConstraint("chunk_index >= 0", name="ck_document_chunks_index_non_negative"),
        CheckConstraint("line_start > 0", name="ck_document_chunks_line_start_positive"),
        CheckConstraint("line_end >= line_start", name="ck_document_chunks_line_range"),
        CheckConstraint(
            "character_count > 0",
            name="ck_document_chunks_character_count_positive",
        ),
        CheckConstraint("word_count > 0", name="ck_document_chunks_word_count_positive"),
        CheckConstraint(
            "length(checksum_sha256) = 64",
            name="ck_document_chunks_checksum_sha256_length",
        ),
        CheckConstraint(
            "(embedding_json IS NULL AND embedding_model IS NULL AND embedding_dimensions IS NULL) "
            "OR (embedding_json IS NOT NULL AND embedding_model IS NOT NULL AND embedding_dimensions > 0)",
            name="ck_document_chunks_embedding_metadata",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    ingestion_run_id: Mapped[UUID] = mapped_column(
        ForeignKey("ingestion_runs.id", ondelete="CASCADE"), nullable=False
    )
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    source_id: Mapped[UUID] = mapped_column(
        ForeignKey("knowledge_sources.id", ondelete="CASCADE"), nullable=False
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    heading: Mapped[str | None] = mapped_column(String(512), nullable=True)
    location: Mapped[str] = mapped_column(String(512), nullable=False)
    line_start: Mapped[int] = mapped_column(Integer, nullable=False)
    line_end: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    character_count: Mapped[int] = mapped_column(Integer, nullable=False)
    word_count: Mapped[int] = mapped_column(Integer, nullable=False)
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    embedding: Mapped[list[float] | None] = mapped_column(
        JSON(none_as_null=True),
        name="embedding_json",
        nullable=True,
    )
    embedding_model: Mapped[str | None] = mapped_column(String(64), nullable=True)
    embedding_dimensions: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )

    ingestion_run: Mapped[IngestionRun] = relationship(back_populates="chunks")
    project: Mapped[Project] = relationship(back_populates="document_chunks")
    source: Mapped[KnowledgeSource] = relationship(back_populates="document_chunks")


class Workflow(Base):
    """Versioned workflow definition attached to one project."""

    __tablename__ = "workflows"
    __table_args__ = (
        UniqueConstraint("project_id", "name", "version", name="uq_workflows_project_name_version"),
        Index("ix_workflows_project_status", "project_id", "status"),
        CheckConstraint("version > 0", name="ck_workflows_version_positive"),
        CheckConstraint("length(trim(name)) > 0", name="ck_workflows_name_not_blank"),
        CheckConstraint(
            "state IN ('ready', 'in_progress', 'review', 'changes_required', 'approved', 'archived')",
            name="ck_workflows_state",
        ),
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
    state: Mapped[str] = mapped_column(String(24), nullable=False, default="ready")
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
    tool_runs: Mapped[list[WorkflowToolRun]] = relationship(
        back_populates="workflow", cascade="all, delete-orphan"
    )
    actions: Mapped[list[WorkflowAction]] = relationship(
        back_populates="workflow", cascade="all, delete-orphan"
    )
    agent_handoffs: Mapped[list[AgentHandoff]] = relationship(
        back_populates="workflow", cascade="all, delete-orphan"
    )


class Approval(Base):
    """A review decision for one workflow version."""

    __tablename__ = "approvals"
    __table_args__ = (
        Index("ix_approvals_workflow_status", "workflow_id", "status"),
        Index("ix_approvals_action_id", "action_id"),
        CheckConstraint(
            "status IN ('pending', 'approved', 'rejected', 'cancelled')",
            name="ck_approvals_status",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    workflow_id: Mapped[UUID] = mapped_column(
        ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False
    )
    action_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("workflow_actions.id", ondelete="SET NULL"), nullable=True
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


class WorkflowToolRun(Base):
    """One bounded, traceable read-only tool request from a workflow."""

    __tablename__ = "workflow_tool_runs"
    __table_args__ = (
        Index("ix_workflow_tool_runs_project_created_at", "project_id", "created_at"),
        Index("ix_workflow_tool_runs_workflow_created_at", "workflow_id", "created_at"),
        CheckConstraint(
            "status IN ('succeeded', 'failed', 'blocked')",
            name="ck_workflow_tool_runs_status",
        ),
        CheckConstraint("attempt_count > 0", name="ck_workflow_tool_runs_attempt_positive"),
        CheckConstraint(
            "max_attempts > 0 AND max_attempts <= 3",
            name="ck_workflow_tool_runs_max_attempts",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    workflow_id: Mapped[UUID] = mapped_column(
        ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False
    )
    requested_by_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    trace_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    tool_name: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False)
    input_summary: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    output_summary: Mapped[str] = mapped_column(String(1000), nullable=False, default="")
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    workflow: Mapped[Workflow] = relationship(back_populates="tool_runs")


class WorkflowAction(Base):
    """A high-impact action intent that cannot execute before approval."""

    __tablename__ = "workflow_actions"
    __table_args__ = (
        UniqueConstraint(
            "workflow_id",
            "idempotency_key",
            name="uq_workflow_actions_workflow_idempotency",
        ),
        Index("ix_workflow_actions_project_status", "project_id", "status"),
        CheckConstraint(
            "action_code IN ('send', 'delete', 'replace', 'publish', 'archive', 'approve')",
            name="ck_workflow_actions_code",
        ),
        CheckConstraint(
            "status IN ('pending_approval', 'approved', 'rejected', 'cancelled', 'executed')",
            name="ck_workflow_actions_status",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    workflow_id: Mapped[UUID] = mapped_column(
        ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False
    )
    requested_by_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    executed_by_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    action_code: Mapped[str] = mapped_column(String(16), nullable=False)
    target_ref: Mapped[str] = mapped_column(String(255), nullable=False)
    reason: Mapped[str] = mapped_column(String(500), nullable=False)
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="pending_approval")
    result_summary: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    executed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    workflow: Mapped[Workflow] = relationship(back_populates="actions")


class AgentHandoff(Base):
    """One bounded specialist-agent handoff attached to a workflow trace."""

    __tablename__ = "agent_handoffs"
    __table_args__ = (
        Index("ix_agent_handoffs_project_created_at", "project_id", "created_at"),
        Index("ix_agent_handoffs_workflow_created_at", "workflow_id", "created_at"),
        CheckConstraint(
            "status IN ('completed', 'blocked', 'failed')",
            name="ck_agent_handoffs_status",
        ),
        CheckConstraint(
            "length(trim(source_agent)) > 0",
            name="ck_agent_handoffs_source_agent_not_blank",
        ),
        CheckConstraint(
            "source_agent IN ('orchestrator', 'intake', 'research', 'knowledge', 'quality_control')",
            name="ck_agent_handoffs_source_agent_allowlist",
        ),
        CheckConstraint(
            "length(trim(target_agent)) > 0",
            name="ck_agent_handoffs_target_agent_not_blank",
        ),
        CheckConstraint(
            "target_agent IN ('intake', 'research', 'knowledge', 'quality_control')",
            name="ck_agent_handoffs_target_agent_allowlist",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    workflow_id: Mapped[UUID] = mapped_column(
        ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False
    )
    requested_by_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    trace_id: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    source_agent: Mapped[str] = mapped_column(String(32), nullable=False)
    target_agent: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False)
    input_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False, default="")
    input_summary: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    output_summary: Mapped[str] = mapped_column(String(500), nullable=False, default="")
    blocked_reason: Mapped[str | None] = mapped_column(String(128), nullable=True)
    result: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    workflow: Mapped[Workflow] = relationship(back_populates="agent_handoffs")


class ResearchReview(Base):
    """Persisted evidence package that can move through human review."""

    __tablename__ = "research_reviews"
    __table_args__ = (
        Index("ix_research_reviews_project_status", "project_id", "status"),
        CheckConstraint(
            "status IN ('needs_review', 'changes_requested', 'verified', 'approved')",
            name="ck_research_reviews_status",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    created_by_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    approved_by_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    source_title: Mapped[str] = mapped_column(String(200), nullable=False)
    source_reference: Mapped[str] = mapped_column(String(512), nullable=False)
    source_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    target_scope: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="needs_review")
    approved_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    project: Mapped[Project] = relationship(back_populates="research_reviews")
    created_by: Mapped[User | None] = relationship(
        back_populates="created_research_reviews",
        foreign_keys=[created_by_id],
    )
    approved_by: Mapped[User | None] = relationship(
        back_populates="approved_research_reviews",
        foreign_keys=[approved_by_id],
    )
    claims: Mapped[list[ResearchReviewClaim]] = relationship(
        back_populates="review", cascade="all, delete-orphan"
    )
    events: Mapped[list[ResearchReviewEvent]] = relationship(
        back_populates="review", cascade="all, delete-orphan"
    )


class ResearchReviewClaim(Base):
    """One source-backed claim retained inside a human review package."""

    __tablename__ = "research_review_claims"
    __table_args__ = (
        UniqueConstraint(
            "review_id", "claim_id", name="uq_research_review_claims_review_claim"
        ),
        Index("ix_research_review_claims_review_status", "review_id", "status"),
        CheckConstraint(
            "status IN ('needs_review', 'changes_requested', 'verified')",
            name="ck_research_review_claims_status",
        ),
        CheckConstraint(
            "classification IN ('factual', 'heading', 'instruction', 'opinion', 'creative')",
            name="ck_research_review_claims_classification",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    review_id: Mapped[UUID] = mapped_column(
        ForeignKey("research_reviews.id", ondelete="CASCADE"), nullable=False
    )
    claim_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    claim: Mapped[str] = mapped_column(String(500), nullable=False)
    classification: Mapped[str] = mapped_column(String(16), nullable=False)
    source_title: Mapped[str] = mapped_column(String(200), nullable=False)
    source_reference: Mapped[str] = mapped_column(String(512), nullable=False)
    source_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    passage: Mapped[str] = mapped_column(Text, nullable=False)
    scope: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="needs_review")
    correction_note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    corrected_claim: Mapped[str | None] = mapped_column(String(500), nullable=True)
    corrected_scope: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    verified_by_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    verified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )

    review: Mapped[ResearchReview] = relationship(back_populates="claims")
    verified_by: Mapped[User | None] = relationship(
        back_populates="verified_research_claims",
        foreign_keys=[verified_by_id],
    )


class ResearchReviewEvent(Base):
    """Append-only human review history for one review package."""

    __tablename__ = "research_review_events"
    __table_args__ = (
        Index("ix_research_review_events_review_created_at", "review_id", "created_at"),
        CheckConstraint(
            "action IN ('submitted', 'correction_requested', 'verified', 'approved', 'exported')",
            name="ck_research_review_events_action",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    review_id: Mapped[UUID] = mapped_column(
        ForeignKey("research_reviews.id", ondelete="CASCADE"), nullable=False
    )
    claim_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), nullable=True)
    actor_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    action: Mapped[str] = mapped_column(String(32), nullable=False)
    note: Mapped[str | None] = mapped_column(String(500), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )

    review: Mapped[ResearchReview] = relationship(back_populates="events")
    actor: Mapped[User | None] = relationship(
        back_populates="research_review_events",
        foreign_keys=[actor_id],
    )


class KnowledgeFeedback(Base):
    """Structured answer feedback without questions or evidence content."""

    __tablename__ = "knowledge_feedback"
    __table_args__ = (
        Index("ix_knowledge_feedback_project_created_at", "project_id", "created_at"),
        CheckConstraint(
            "rating IN ('helpful', 'not_helpful')",
            name="ck_knowledge_feedback_rating",
        ),
        CheckConstraint(
            "answer_status IN ('answered', 'refused')",
            name="ck_knowledge_feedback_answer_status",
        ),
        CheckConstraint(
            "citation_count >= 0 AND citation_count <= 3",
            name="ck_knowledge_feedback_citation_count",
        ),
        CheckConstraint(
            "reason IS NULL OR reason IN "
            "('accurate', 'clear', 'missing_evidence', 'wrong_source', 'other')",
            name="ck_knowledge_feedback_reason",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    actor_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    rating: Mapped[str] = mapped_column(String(16), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(32), nullable=True)
    answer_status: Mapped[str] = mapped_column(String(16), nullable=False)
    citation_count: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )

    project: Mapped[Project] = relationship(back_populates="knowledge_feedback")
    actor: Mapped[User | None] = relationship(
        back_populates="knowledge_feedback",
        foreign_keys=[actor_id],
    )


class KnowledgeErrorReport(Base):
    """Structured knowledge UI error report without raw request payloads."""

    __tablename__ = "knowledge_error_reports"
    __table_args__ = (
        Index(
            "ix_knowledge_error_reports_project_created_at",
            "project_id",
            "created_at",
        ),
        CheckConstraint(
            "surface IN ('search', 'answer')",
            name="ck_knowledge_error_reports_surface",
        ),
        CheckConstraint(
            "category IN "
            "('wrong_answer', 'missing_evidence', 'wrong_source', 'technical_error', 'other')",
            name="ck_knowledge_error_reports_category",
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid4)
    project_id: Mapped[UUID] = mapped_column(
        ForeignKey("projects.id", ondelete="CASCADE"), nullable=False
    )
    actor_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    surface: Mapped[str] = mapped_column(String(16), nullable=False)
    category: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utc_now
    )

    project: Mapped[Project] = relationship(back_populates="knowledge_error_reports")
    actor: Mapped[User | None] = relationship(
        back_populates="knowledge_error_reports",
        foreign_keys=[actor_id],
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
    "AgentHandoff",
    "Approval",
    "Backup",
    "DocumentChunk",
    "File",
    "FileHistory",
    "FileVersion",
    "IngestionRun",
    "KnowledgeErrorReport",
    "KnowledgeFeedback",
    "KnowledgeSource",
    "Project",
    "ResearchReview",
    "ResearchReviewClaim",
    "ResearchReviewEvent",
    "SecurityEvent",
    "User",
    "Workflow",
]
