"""Pydantic request and response contracts for the database-backed API."""

from __future__ import annotations

from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, model_validator

from knowledge_contract import (
    AGENT_INSTRUCTION_VERSION,
    ANSWER_CONTRACT_VERSION,
    ANSWER_MODE,
)
from models import Approval, File, KnowledgeSource, Project, SecurityEvent, User, Workflow
from research_evidence import (
    MAX_RESEARCH_CLAIMS,
    MAX_RESEARCH_CLAIM_CHARACTERS,
    MAX_RESEARCH_SOURCE_CHARACTERS,
    RESEARCH_EVIDENCE_SCHEMA_VERSION,
)


class UserCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    external_ref: str = Field(min_length=1, max_length=128)
    role: str = Field(default="member", min_length=1, max_length=32)


class UserResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    external_ref: str
    role: str
    created_at: datetime
    updated_at: datetime


class ProjectCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=500)
    owner_id: UUID


class ProjectResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    owner_id: UUID
    title: str
    storage_slug: str
    description: str
    status: str
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_model(cls, project: Project) -> ProjectResponse:
        """Translate database naming (``name``) to the API's ``title``."""

        return cls(
            id=project.id,
            owner_id=project.owner_id,
            title=project.name,
            storage_slug=project.storage_slug,
            description=project.description,
            status=project.status,
            created_at=project.created_at,
            updated_at=project.updated_at,
        )


class FileCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    storage_key: str = Field(min_length=1, max_length=512)
    name: str | None = Field(default=None, min_length=1, max_length=255)
    extension: str | None = Field(default=None, max_length=32)
    media_type: str = Field(min_length=1, max_length=127)
    size_bytes: int = Field(ge=0)
    checksum_sha256: str = Field(
        min_length=64,
        max_length=64,
        pattern=r"^[0-9a-fA-F]{64}$",
    )
    uploaded_by_id: UUID | None = None


class FileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    uploaded_by_id: UUID | None
    storage_key: str
    name: str
    extension: str
    media_type: str
    size_bytes: int
    checksum_sha256: str
    modified_at: datetime
    status: str
    created_at: datetime
    updated_at: datetime


class FileHistoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    file_id: UUID
    event_code: str
    storage_key: str
    name: str
    extension: str
    media_type: str
    size_bytes: int
    checksum_sha256: str
    modified_at: datetime
    status: str
    observed_at: datetime


class FileVersionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    file_id: UUID
    version_number: int = Field(gt=0)
    storage_key: str
    media_type: str
    size_bytes: int = Field(ge=0)
    checksum_sha256: str
    modified_at: datetime
    is_original: bool
    created_at: datetime


class KnowledgeSourceCreate(BaseModel):
    """Register file metadata without accepting document contents."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    file_id: UUID
    owner_id: UUID
    title: str = Field(min_length=1, max_length=200)
    source_type: Literal["sop", "prompt_bank", "style_guide", "project_rule"]
    sensitivity: Literal["public", "internal", "confidential", "restricted"]


class KnowledgeSourceDecision(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    decision: Literal["approved", "rejected"]
    reason: str | None = Field(default=None, min_length=1, max_length=255)


class KnowledgeSourceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    file_id: UUID
    owner_id: UUID
    created_by_id: UUID | None
    reviewed_by_id: UUID | None
    title: str
    source_type: Literal["sop", "prompt_bank", "style_guide", "project_rule"]
    sensitivity: Literal["public", "internal", "confidential", "restricted"]
    approval_status: Literal["pending", "approved", "rejected"]
    rejection_reason: str | None
    file_name: str
    file_storage_key: str
    file_checksum_sha256: str
    created_at: datetime
    reviewed_at: datetime | None
    updated_at: datetime

    @classmethod
    def from_model(cls, source: KnowledgeSource) -> KnowledgeSourceResponse:
        """Expose source metadata and portable file identity, never contents."""

        return cls(
            id=source.id,
            project_id=source.project_id,
            file_id=source.file_id,
            owner_id=source.owner_id,
            created_by_id=source.created_by_id,
            reviewed_by_id=source.reviewed_by_id,
            title=source.title,
            source_type=source.source_type,
            sensitivity=source.sensitivity,
            approval_status=source.approval_status,
            rejection_reason=source.rejection_reason,
            file_name=source.file.name,
            file_storage_key=source.file.storage_key,
            file_checksum_sha256=source.file.checksum_sha256,
            created_at=source.created_at,
            reviewed_at=source.reviewed_at,
            updated_at=source.updated_at,
        )


class DocumentChunkResponse(BaseModel):
    """One source-linked chunk prepared for a later retrieval stage."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    ingestion_run_id: UUID
    project_id: UUID
    source_id: UUID
    chunk_index: int = Field(ge=0)
    title: str
    heading: str | None
    location: str
    line_start: int = Field(gt=0)
    line_end: int = Field(ge=1)
    content: str
    character_count: int = Field(gt=0)
    word_count: int = Field(gt=0)
    checksum_sha256: str
    created_at: datetime


class IngestionResponse(BaseModel):
    """The result of one bounded extraction and chunking run."""

    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    source_id: UUID
    source_checksum_sha256: str
    status: Literal["running", "completed", "failed"]
    chunk_count: int = Field(ge=0)
    error_message: str | None
    created_at: datetime
    completed_at: datetime | None
    chunks: list[DocumentChunkResponse]


class SemanticSearchRequest(BaseModel):
    """Bounded semantic-search input with allow-listed metadata filters."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    query: str = Field(min_length=1, max_length=500)
    source_type: Literal["sop", "prompt_bank", "style_guide", "project_rule"] | None = None
    sensitivity: Literal["public", "internal", "confidential", "restricted"] | None = None
    source_id: UUID | None = None
    limit: int = Field(default=5, ge=1, le=20)


class SemanticSearchResult(BaseModel):
    """One ranked, source-attributed passage returned to a caller."""

    chunk_id: UUID
    project_id: UUID
    source_id: UUID
    score: float = Field(ge=0.0, le=1.0)
    title: str
    heading: str | None
    location: str
    line_start: int = Field(gt=0)
    line_end: int = Field(ge=1)
    content: str
    source_type: Literal["sop", "prompt_bank", "style_guide", "project_rule"]
    sensitivity: Literal["public", "internal", "confidential", "restricted"]
    file_name: str
    file_storage_key: str


class SemanticSearchResponse(BaseModel):
    """Project-scoped ranked passages for one bounded query."""

    project_id: UUID
    query: str
    embedding_model: str
    embedding_dimensions: int = Field(gt=0)
    result_count: int = Field(ge=0, le=20)
    results: list[SemanticSearchResult]


class KnowledgeAnswerRequest(BaseModel):
    """Bounded input for an evidence-grounded knowledge answer."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    query: str = Field(min_length=1, max_length=500)
    source_type: Literal["sop", "prompt_bank", "style_guide", "project_rule"] | None = None
    sensitivity: Literal["public", "internal", "confidential", "restricted"] | None = None
    source_id: UUID | None = None
    evidence_limit: int = Field(default=5, ge=1, le=8)


class KnowledgeCitation(BaseModel):
    """A bounded source citation attached to a grounded answer."""

    citation_number: int = Field(gt=0, le=3)
    chunk_id: UUID
    source_id: UUID
    score: float = Field(ge=0.0, le=1.0)
    title: str
    heading: str | None
    location: str
    line_start: int = Field(gt=0)
    line_end: int = Field(ge=1)
    file_name: str
    file_storage_key: str
    excerpt: str = Field(min_length=1, max_length=800)


class KnowledgeAnswerResponse(BaseModel):
    """A structured answer or refusal grounded in approved source excerpts."""

    contract_version: Literal[ANSWER_CONTRACT_VERSION]
    instruction_version: Literal[AGENT_INSTRUCTION_VERSION]
    answer_mode: Literal[ANSWER_MODE]
    project_id: UUID
    query: str
    status: Literal["answered", "refused"]
    answer: str = Field(min_length=1, max_length=2_500)
    refusal_reason: Literal["unsupported_query", "insufficient_evidence"] | None
    answer_engine: str
    embedding_model: str
    embedding_dimensions: int = Field(gt=0)
    retrieved_count: int = Field(ge=0, le=8)
    citation_count: int = Field(ge=0, le=3)
    citations: list[KnowledgeCitation]

    @model_validator(mode="after")
    def validate_answer_state(self) -> KnowledgeAnswerResponse:
        """Keep status, refusal, and citation fields mutually consistent."""

        if self.citation_count != len(self.citations):
            raise ValueError("citation_count must match the citations list.")
        if self.status == "answered":
            if self.refusal_reason is not None or not self.citations:
                raise ValueError("Answered responses require citations and no refusal reason.")
        elif self.refusal_reason is None or self.citations:
            raise ValueError("Refused responses require a reason and no citations.")
        return self


class ResearchScope(BaseModel):
    """Allow-listed context used to compare evidence applicability."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    model_year: int | None = Field(default=None, ge=1886, le=2100)
    engine: str | None = Field(default=None, min_length=1, max_length=120)
    market: str | None = Field(default=None, min_length=1, max_length=120)
    population: str | None = Field(default=None, min_length=1, max_length=120)
    setting: str | None = Field(default=None, min_length=1, max_length=120)
    evidence_type: str | None = Field(default=None, min_length=1, max_length=80)


class ResearchClaimExtractionRequest(BaseModel):
    """Bounded source input for the deterministic claim extractor."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    source_title: str = Field(min_length=1, max_length=200)
    source_reference: str = Field(min_length=1, max_length=512)
    source_date: date | None = None
    source_text: str = Field(min_length=1, max_length=MAX_RESEARCH_SOURCE_CHARACTERS)
    scope: ResearchScope = Field(default_factory=ResearchScope)


class ResearchClaimResponse(BaseModel):
    """One provenance-preserving claim in a validated evidence preview."""

    model_config = ConfigDict(extra="forbid")

    claim_id: UUID
    claim: str = Field(min_length=1, max_length=MAX_RESEARCH_CLAIM_CHARACTERS)
    classification: Literal["factual", "heading", "instruction", "opinion", "creative"]
    source_title: str = Field(min_length=1, max_length=200)
    source_reference: str = Field(min_length=1, max_length=512)
    source_date: date | None = None
    passage: str = Field(min_length=1, max_length=MAX_RESEARCH_SOURCE_CHARACTERS)
    scope: ResearchScope
    review_status: Literal["needs_review"]


class ResearchClaimExtractionResponse(BaseModel):
    """Validated extraction output; claims are not persisted at this stage."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[RESEARCH_EVIDENCE_SCHEMA_VERSION]
    project_id: UUID
    source_title: str = Field(min_length=1, max_length=200)
    source_reference: str = Field(min_length=1, max_length=512)
    source_date: date | None = None
    scope: ResearchScope
    claim_count: int = Field(ge=0, le=MAX_RESEARCH_CLAIMS)
    claims: list[ResearchClaimResponse] = Field(max_length=MAX_RESEARCH_CLAIMS)

    @model_validator(mode="after")
    def validate_claim_count(self) -> ResearchClaimExtractionResponse:
        """Prevent a response envelope from disagreeing with its claim list."""

        if self.claim_count != len(self.claims):
            raise ValueError("claim_count must match the claims list.")
        if any(
            (
                claim.source_title != self.source_title
                or claim.source_reference != self.source_reference
                or claim.source_date != self.source_date
                or claim.scope != self.scope
            )
            for claim in self.claims
        ):
            raise ValueError("Each claim must retain the envelope source metadata.")
        return self


class ResearchApplicabilityCheckRequest(BaseModel):
    """Validated claim plus target context for a conservative scope check."""

    model_config = ConfigDict(extra="forbid")

    claim: ResearchClaimResponse
    target_scope: ResearchScope = Field(default_factory=ResearchScope)


class ResearchApplicabilityFieldResponse(BaseModel):
    """One field-level applicability comparison."""

    model_config = ConfigDict(extra="forbid")

    field: Literal[
        "model_year",
        "engine",
        "market",
        "population",
        "setting",
        "evidence_type",
    ]
    status: Literal["match", "mismatch", "uncertain", "not_requested"]
    requested: str | None = Field(default=None, max_length=120)
    observed: str | None = Field(default=None, max_length=120)


class ResearchApplicabilityCheckResponse(BaseModel):
    """Validated scope-check output with uncertainty made explicit."""

    model_config = ConfigDict(extra="forbid")

    schema_version: Literal[RESEARCH_EVIDENCE_SCHEMA_VERSION]
    project_id: UUID
    claim_id: UUID
    claim_classification: Literal[
        "factual",
        "heading",
        "instruction",
        "opinion",
        "creative",
    ]
    status: Literal["applicable", "mismatch", "uncertain", "not_applicable"]
    reason: str = Field(min_length=1, max_length=200)
    fields: list[ResearchApplicabilityFieldResponse] = Field(max_length=6)

    @model_validator(mode="after")
    def validate_unique_fields(self) -> ResearchApplicabilityCheckResponse:
        """Keep the field report bounded and unambiguous for clients."""

        names = [field.field for field in self.fields]
        if len(names) != len(set(names)):
            raise ValueError("Applicability fields must be unique.")
        return self


class KnowledgeFeedbackCreate(BaseModel):
    """Structured answer feedback that omits the question and evidence."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    rating: Literal["helpful", "not_helpful"]
    reason: Literal[
        "accurate",
        "clear",
        "missing_evidence",
        "wrong_source",
        "other",
    ] | None = None
    answer_status: Literal["answered", "refused"]
    citation_count: int = Field(ge=0, le=3)


class KnowledgeFeedbackResponse(BaseModel):
    """Acknowledgement for one privacy-bounded answer rating."""

    id: UUID
    project_id: UUID
    rating: Literal["helpful", "not_helpful"]
    reason: Literal[
        "accurate",
        "clear",
        "missing_evidence",
        "wrong_source",
        "other",
    ] | None
    created_at: datetime


class KnowledgeErrorReportCreate(BaseModel):
    """Structured issue report without free-form request or answer text."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    surface: Literal["search", "answer"]
    category: Literal[
        "wrong_answer",
        "missing_evidence",
        "wrong_source",
        "technical_error",
        "other",
    ]


class KnowledgeErrorReportResponse(BaseModel):
    """Acknowledgement for one privacy-bounded knowledge issue report."""

    id: UUID
    project_id: UUID
    surface: Literal["search", "answer"]
    category: Literal[
        "wrong_answer",
        "missing_evidence",
        "wrong_source",
        "technical_error",
        "other",
    ]
    created_at: datetime


class FileRestoreCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    destination_path: str = Field(min_length=1, max_length=512)


class FileRestoreResponse(BaseModel):
    project_id: UUID
    file_id: UUID
    version_number: int = Field(gt=0)
    destination_path: str
    checksum_sha256: str
    bytes_restored: int = Field(ge=0)


class BackupCreate(BaseModel):
    """Optional request envelope for creating a project backup."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class BackupResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    created_by_id: UUID | None
    artifact_key: str
    manifest_key: str
    archive_size_bytes: int = Field(ge=0)
    file_count: int = Field(ge=0)
    total_bytes: int = Field(ge=0)
    archive_checksum_sha256: str
    manifest_checksum_sha256: str
    status: Literal["created", "verified", "restored"]
    created_at: datetime
    verified_at: datetime | None
    restored_at: datetime | None
    updated_at: datetime


class BackupVerifyResponse(BaseModel):
    project_id: UUID
    backup: BackupResponse
    entries_verified: int = Field(ge=0)
    files_verified: int = Field(ge=0)
    bytes_verified: int = Field(ge=0)


class BackupRestoreCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    destination_path: str = Field(min_length=1, max_length=512)


class BackupRestoreResponse(BaseModel):
    project_id: UUID
    backup_id: UUID
    destination_path: str
    entries_restored: int = Field(ge=0)
    files_restored: int = Field(ge=0)
    bytes_restored: int = Field(ge=0)
    archive_checksum_sha256: str
    manifest_checksum_sha256: str


class UploadResponse(BaseModel):
    project_id: UUID
    file_id: UUID
    storage_key: str
    name: str
    extension: str
    media_type: str
    size_bytes: int = Field(ge=0)
    checksum_sha256: str
    status: str


class PermissionMatrixResponse(BaseModel):
    roles: dict[str, list[str]]


class UploadPolicyResponse(BaseModel):
    max_size_bytes: int = Field(gt=0)
    allowed_extensions: dict[str, list[str]]
    filename_pattern: str


class ConversionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    source_path: str = Field(min_length=1, max_length=255)
    destination_path: str = Field(min_length=1, max_length=255)


class ConversionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    project_id: UUID
    source_path: str
    destination_path: str
    source_format: str
    destination_format: str
    bytes_written: int = Field(ge=0)


class FolderGenerateCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    project_name: str = Field(min_length=1, max_length=100)


class FolderGenerateResponse(BaseModel):
    name: str
    project_path: str
    subdirectories: list[str]


class InventoryRecordResponse(BaseModel):
    relative_path: str
    name: str
    extension: str
    mime_type: str
    size_bytes: int = Field(ge=0)
    modified_at: datetime
    sha256: str
    extension_mime_match: bool | None


class InventoryResponse(BaseModel):
    project_id: UUID
    files_scanned: int = Field(ge=0)
    duplicate_groups: int = Field(ge=0)
    duplicate_files: int = Field(ge=0)
    json_manifest: str
    csv_manifest: str
    records_persisted: int = Field(default=0, ge=0)
    history_events: int = Field(default=0, ge=0)
    versions_created: int = Field(default=0, ge=0)
    records: list[InventoryRecordResponse]


class OrganizationActionResponse(BaseModel):
    source: str
    destination: str
    status: Literal["planned", "conflict", "applied", "quarantined", "rolled_back"]
    reason: str
    sha256: str | None


class OrganizationPlanResponse(BaseModel):
    project_id: UUID
    plan_path: str
    created_at: datetime
    actions: list[OrganizationActionResponse]


class OrganizationApplyCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    quarantine_conflicts: bool = False


class OrganizationApplyResponse(BaseModel):
    project_id: UUID
    plan_path: str
    action_count: int = Field(ge=0)
    applied_count: int = Field(ge=0)
    conflict_count: int = Field(ge=0)
    journal_path: str
    quarantine_journal_path: str | None


class OrganizationRollbackCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    journal_path: str = Field(min_length=1, max_length=255)


class OrganizationRollbackResponse(BaseModel):
    project_id: UUID
    journal_path: str
    restored_count: int = Field(ge=0)


class WorkflowCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str = Field(min_length=1, max_length=100)
    version: int = Field(default=1, gt=0)
    created_by_id: UUID | None = None


class WorkflowResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    project_id: UUID
    created_by_id: UUID | None
    name: str
    status: str
    version: int
    created_at: datetime
    updated_at: datetime


class ApprovalCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    requested_by_id: UUID | None = None


class ApprovalDecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    status: Literal["approved", "rejected", "cancelled"]
    approved_by_id: UUID
    decision_code: str | None = Field(default=None, max_length=64)


class ApprovalResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    workflow_id: UUID
    requested_by_id: UUID | None
    approved_by_id: UUID | None
    status: str
    decision_code: str | None
    requested_at: datetime
    decided_at: datetime | None


class SecurityEventCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    event_code: str = Field(min_length=1, max_length=64)
    outcome: Literal["success", "failure", "denied"]
    actor_id: UUID | None = None
    resource_type: str | None = Field(default=None, max_length=64)
    resource_ref: str | None = Field(default=None, max_length=128)
    request_ref: str | None = Field(default=None, max_length=128)


class SecurityEventResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    actor_id: UUID | None
    event_code: str
    outcome: str
    resource_type: str | None
    resource_ref: str | None
    request_ref: str | None
    occurred_at: datetime


__all__ = [
    "ApprovalCreate",
    "ApprovalDecisionRequest",
    "ApprovalResponse",
    "BackupCreate",
    "BackupResponse",
    "BackupRestoreCreate",
    "BackupRestoreResponse",
    "BackupVerifyResponse",
    "ConversionCreate",
    "ConversionResponse",
    "DocumentChunkResponse",
    "FolderGenerateCreate",
    "FolderGenerateResponse",
    "FileCreate",
    "FileHistoryResponse",
    "FileRestoreCreate",
    "FileRestoreResponse",
    "FileVersionResponse",
    "FileResponse",
    "InventoryRecordResponse",
    "InventoryResponse",
    "IngestionResponse",
    "SemanticSearchRequest",
    "SemanticSearchResult",
    "SemanticSearchResponse",
    "KnowledgeSourceCreate",
    "KnowledgeSourceDecision",
    "KnowledgeSourceResponse",
    "OrganizationActionResponse",
    "OrganizationApplyCreate",
    "OrganizationApplyResponse",
    "OrganizationPlanResponse",
    "OrganizationRollbackCreate",
    "OrganizationRollbackResponse",
    "PermissionMatrixResponse",
    "ProjectCreate",
    "ProjectResponse",
    "SecurityEventCreate",
    "SecurityEventResponse",
    "UserCreate",
    "UserResponse",
    "UploadResponse",
    "UploadPolicyResponse",
    "WorkflowCreate",
    "WorkflowResponse",
]
