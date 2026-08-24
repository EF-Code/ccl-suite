"""Pydantic request and response contracts for the database-backed API."""

from __future__ import annotations

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from models import Approval, File, Project, SecurityEvent, User, Workflow


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
    "ConversionCreate",
    "ConversionResponse",
    "FolderGenerateCreate",
    "FolderGenerateResponse",
    "FileCreate",
    "FileHistoryResponse",
    "FileResponse",
    "InventoryRecordResponse",
    "InventoryResponse",
    "OrganizationActionResponse",
    "OrganizationApplyCreate",
    "OrganizationApplyResponse",
    "OrganizationPlanResponse",
    "OrganizationRollbackCreate",
    "OrganizationRollbackResponse",
    "ProjectCreate",
    "ProjectResponse",
    "SecurityEventCreate",
    "SecurityEventResponse",
    "UserCreate",
    "UserResponse",
    "WorkflowCreate",
    "WorkflowResponse",
]
