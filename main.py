from __future__ import annotations

from datetime import datetime
from typing import TypeVar
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from api_schemas import (
    ApprovalCreate,
    ApprovalDecisionRequest,
    ApprovalResponse,
    FileCreate,
    FileResponse,
    ProjectCreate,
    ProjectResponse,
    SecurityEventCreate,
    SecurityEventResponse,
    UserCreate,
    UserResponse,
    WorkflowCreate,
    WorkflowResponse,
)
from config import ENVIRONMENT
from database import get_db
from logger import logger
from models import Approval, File, Project, SecurityEvent, User, Workflow, utc_now

MAX_REQUEST_BODY_BYTES = 1_048_576

app = FastAPI(title="CCL AI Suite", version="0.1.0")
Entity = TypeVar("Entity")


class HealthResponse(BaseModel):
    status: str


def require_record(
    db: Session,
    model: type[Entity],
    record_id: UUID,
    detail: str,
) -> Entity:
    """Load a record or return a safe API error."""

    try:
        record = db.get(model, record_id)
    except SQLAlchemyError:
        logger.error("Database lookup failed.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database temporarily unavailable.",
        )

    if record is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)
    return record


def persist_record(db: Session, record: Entity, resource_name: str) -> Entity:
    """Persist one record and translate database failures into safe responses."""

    try:
        db.add(record)
        db.commit()
        db.refresh(record)
    except IntegrityError:
        db.rollback()
        logger.error("%s creation failed because of a database constraint.", resource_name)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"{resource_name} could not be created.",
        )
    except SQLAlchemyError:
        db.rollback()
        logger.error("%s creation failed because the database was unavailable.", resource_name)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database temporarily unavailable.",
        )
    return record


def list_records(db: Session, statement: object) -> list[Entity]:
    """Execute a read query and return a safe error when the database is down."""

    try:
        return list(db.scalars(statement).all())  # type: ignore[arg-type]
    except SQLAlchemyError:
        logger.error("Database listing failed.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database temporarily unavailable.",
        )


def require_development_provisioning() -> None:
    """Keep the unauthenticated local user-provisioning route out of production."""

    if ENVIRONMENT.lower() != "development":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User provisioning is disabled outside development.",
        )


async def reject_oversized_requests(request: Request) -> None:
    """Reject declared request bodies larger than the application accepts."""

    content_length = request.headers.get("content-length")
    if content_length is not None:
        try:
            if int(content_length) > MAX_REQUEST_BODY_BYTES:
                raise HTTPException(
                    status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                    detail="Request body is too large.",
                )
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid Content-Length header.",
            )


@app.get("/health", response_model=HealthResponse, tags=["system"])
async def health() -> HealthResponse:
    return HealthResponse(status="ok")


@app.post(
    "/users",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["users"],
    dependencies=[Depends(reject_oversized_requests)],
)
async def create_user(
    user: UserCreate, db: Session = Depends(get_db)
) -> UserResponse:
    require_development_provisioning()
    created_user = persist_record(
        db,
        User(external_ref=user.external_ref, role=user.role),
        "User",
    )
    return UserResponse.model_validate(created_user)


@app.post(
    "/projects",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["projects"],
    dependencies=[Depends(reject_oversized_requests)],
)
async def create_project(
    project: ProjectCreate, db: Session = Depends(get_db)
) -> ProjectResponse:
    owner = require_record(db, User, project.owner_id, "Project owner was not found.")
    created_project = persist_record(
        db,
        Project(
            owner_id=owner.id,
            name=project.title,
            description=project.description,
        ),
        "Project",
    )
    return ProjectResponse.from_model(created_project)


@app.get("/projects", response_model=list[ProjectResponse], tags=["projects"])
async def list_projects(db: Session = Depends(get_db)) -> list[ProjectResponse]:
    projects = list_records(
        db,
        select(Project).order_by(Project.created_at, Project.id),
    )
    return [ProjectResponse.from_model(project) for project in projects]


@app.post(
    "/projects/{project_id}/files",
    response_model=FileResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["files"],
    dependencies=[Depends(reject_oversized_requests)],
)
async def create_file(
    project_id: UUID,
    file_metadata: FileCreate,
    db: Session = Depends(get_db),
) -> FileResponse:
    require_record(db, Project, project_id, "Project was not found.")
    if file_metadata.uploaded_by_id is not None:
        require_record(db, User, file_metadata.uploaded_by_id, "Uploader was not found.")

    created_file = persist_record(
        db,
        File(
            project_id=project_id,
            uploaded_by_id=file_metadata.uploaded_by_id,
            storage_key=file_metadata.storage_key,
            media_type=file_metadata.media_type,
            size_bytes=file_metadata.size_bytes,
            checksum_sha256=file_metadata.checksum_sha256.lower(),
        ),
        "File metadata",
    )
    return FileResponse.model_validate(created_file)


@app.get(
    "/projects/{project_id}/files",
    response_model=list[FileResponse],
    tags=["files"],
)
async def list_files(
    project_id: UUID, db: Session = Depends(get_db)
) -> list[FileResponse]:
    require_record(db, Project, project_id, "Project was not found.")
    files = list_records(
        db,
        select(File)
        .where(File.project_id == project_id)
        .order_by(File.created_at, File.id),
    )
    return [FileResponse.model_validate(file_metadata) for file_metadata in files]


@app.post(
    "/projects/{project_id}/workflows",
    response_model=WorkflowResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["workflows"],
    dependencies=[Depends(reject_oversized_requests)],
)
async def create_workflow(
    project_id: UUID,
    workflow: WorkflowCreate,
    db: Session = Depends(get_db),
) -> WorkflowResponse:
    require_record(db, Project, project_id, "Project was not found.")
    if workflow.created_by_id is not None:
        require_record(db, User, workflow.created_by_id, "Workflow creator was not found.")

    created_workflow = persist_record(
        db,
        Workflow(
            project_id=project_id,
            created_by_id=workflow.created_by_id,
            name=workflow.name,
            version=workflow.version,
        ),
        "Workflow",
    )
    return WorkflowResponse.model_validate(created_workflow)


@app.get(
    "/projects/{project_id}/workflows",
    response_model=list[WorkflowResponse],
    tags=["workflows"],
)
async def list_workflows(
    project_id: UUID, db: Session = Depends(get_db)
) -> list[WorkflowResponse]:
    require_record(db, Project, project_id, "Project was not found.")
    workflows = list_records(
        db,
        select(Workflow)
        .where(Workflow.project_id == project_id)
        .order_by(Workflow.created_at, Workflow.id),
    )
    return [WorkflowResponse.model_validate(workflow) for workflow in workflows]


@app.post(
    "/workflows/{workflow_id}/approvals",
    response_model=ApprovalResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["approvals"],
    dependencies=[Depends(reject_oversized_requests)],
)
async def create_approval(
    workflow_id: UUID,
    approval: ApprovalCreate,
    db: Session = Depends(get_db),
) -> ApprovalResponse:
    require_record(db, Workflow, workflow_id, "Workflow was not found.")
    if approval.requested_by_id is not None:
        require_record(db, User, approval.requested_by_id, "Requester was not found.")

    created_approval = persist_record(
        db,
        Approval(
            workflow_id=workflow_id,
            requested_by_id=approval.requested_by_id,
        ),
        "Approval",
    )
    return ApprovalResponse.model_validate(created_approval)


@app.get(
    "/workflows/{workflow_id}/approvals",
    response_model=list[ApprovalResponse],
    tags=["approvals"],
)
async def list_approvals(
    workflow_id: UUID, db: Session = Depends(get_db)
) -> list[ApprovalResponse]:
    require_record(db, Workflow, workflow_id, "Workflow was not found.")
    approvals = list_records(
        db,
        select(Approval)
        .where(Approval.workflow_id == workflow_id)
        .order_by(Approval.requested_at, Approval.id),
    )
    return [ApprovalResponse.model_validate(approval) for approval in approvals]


@app.post(
    "/approvals/{approval_id}/decision",
    response_model=ApprovalResponse,
    tags=["approvals"],
    dependencies=[Depends(reject_oversized_requests)],
)
async def decide_approval(
    approval_id: UUID,
    decision: ApprovalDecisionRequest,
    db: Session = Depends(get_db),
) -> ApprovalResponse:
    approval = require_record(db, Approval, approval_id, "Approval was not found.")
    if approval.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Approval has already been decided.",
        )
    require_record(db, User, decision.approved_by_id, "Approver was not found.")

    approval.status = decision.status
    approval.approved_by_id = decision.approved_by_id
    approval.decision_code = decision.decision_code
    approval.decided_at = utc_now()
    updated_approval = persist_record(db, approval, "Approval")
    return ApprovalResponse.model_validate(updated_approval)


@app.post(
    "/security-events",
    response_model=SecurityEventResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["security-events"],
    dependencies=[Depends(reject_oversized_requests)],
)
async def create_security_event(
    event: SecurityEventCreate, db: Session = Depends(get_db)
) -> SecurityEventResponse:
    if event.actor_id is not None:
        require_record(db, User, event.actor_id, "Event actor was not found.")

    created_event = persist_record(
        db,
        SecurityEvent(
            actor_id=event.actor_id,
            event_code=event.event_code,
            outcome=event.outcome,
            resource_type=event.resource_type,
            resource_ref=event.resource_ref,
            request_ref=event.request_ref,
        ),
        "Security event",
    )
    return SecurityEventResponse.model_validate(created_event)


@app.get(
    "/security-events",
    response_model=list[SecurityEventResponse],
    tags=["security-events"],
)
async def list_security_events(
    limit: int = Query(default=100, ge=1, le=1000),
    db: Session = Depends(get_db),
) -> list[SecurityEventResponse]:
    events = list_records(
        db,
        select(SecurityEvent)
        .order_by(SecurityEvent.occurred_at.desc(), SecurityEvent.id)
        .limit(limit),
    )
    return [SecurityEventResponse.model_validate(event) for event in events]
