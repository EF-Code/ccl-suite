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

    storage_key: str = Field(min_length=1, max_length=255)
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
    media_type: str
    size_bytes: int
    checksum_sha256: str
    created_at: datetime


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
    "FileCreate",
    "FileResponse",
    "ProjectCreate",
    "ProjectResponse",
    "SecurityEventCreate",
    "SecurityEventResponse",
    "UserCreate",
    "UserResponse",
    "WorkflowCreate",
    "WorkflowResponse",
]
