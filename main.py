from __future__ import annotations

from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import TypeVar
from uuid import UUID, uuid4

from fastapi import Depends, FastAPI, HTTPException, Query, Request, status
from pydantic import BaseModel
from fastapi.responses import HTMLResponse, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from api_schemas import (
    ApprovalCreate,
    ApprovalDecisionRequest,
    ApprovalResponse,
    BackupCreate,
    BackupResponse,
    BackupRestoreCreate,
    BackupRestoreResponse,
    BackupVerifyResponse,
    ConversionCreate,
    ConversionResponse,
    DocumentChunkResponse,
    FileCreate,
    FileHistoryResponse,
    FileRestoreCreate,
    FileRestoreResponse,
    FileResponse,
    FileVersionResponse,
    FolderGenerateCreate,
    FolderGenerateResponse,
    InventoryRecordResponse,
    InventoryResponse,
    IngestionResponse,
    KnowledgeSourceCreate,
    KnowledgeSourceDecision,
    KnowledgeSourceResponse,
    OrganizationActionResponse,
    OrganizationApplyCreate,
    OrganizationApplyResponse,
    OrganizationPlanResponse,
    OrganizationRollbackCreate,
    OrganizationRollbackResponse,
    PermissionMatrixResponse,
    ProjectCreate,
    ProjectResponse,
    SemanticSearchRequest,
    SemanticSearchResponse,
    SemanticSearchResult,
    SecurityEventCreate,
    SecurityEventResponse,
    UserCreate,
    UserResponse,
    UploadResponse,
    UploadPolicyResponse,
    WorkflowCreate,
    WorkflowResponse,
)
from config import ENVIRONMENT
from database import get_db
from document_ingestion import ChunkDraft, DocumentProcessingError, prepare_document
from file_converter import (
    ConversionDestinationExistsError,
    ConversionError,
    UnsafeConversionPathError,
    UnsupportedFormatError,
    convert_file,
)
from file_inventory import (
    DEFAULT_PROJECT_ROOT,
    FileRecord,
    resolve_approved_root,
    safe_relative_path,
    scan_files,
    write_manifests,
)
from file_backups import (
    BackupArtifact,
    BackupArtifactError,
    BackupDestinationExistsError,
    BackupIntegrityError,
    BackupPathError,
    BackupSourceError,
    BackupStoragePaths,
    DEFAULT_BACKUP_ROOT,
    backup_storage_paths,
    create_backup,
    remove_backup_artifacts,
    restore_backup,
    verify_backup,
)
from file_records import (
    build_file_history_statement,
    build_file_search_statement,
    build_file_versions_statement,
    sync_inventory_records,
    validate_storage_key,
)
from file_restore import (
    RestoreDestinationExistsError,
    RestoreError,
    RestoreSourceUnavailableError,
    UnsafeRestorePathError,
    restore_version_content,
)
from file_uploads import (
    UploadDestinationExistsError,
    UploadResult,
    UploadTooLargeError,
    UploadValidationError,
    UploadWriteError,
    store_upload,
    upload_policy,
)
from file_organizer import (
    OrganizationPlan,
    apply_plan,
    build_plan,
    quarantine_conflicts,
    rollback_journal,
    write_plan,
)
from folder_generator import create_project_folder, normalize_project_name
from knowledge_sources import build_approved_knowledge_sources_statement
from logger import logger
from models import (
    Approval,
    Backup,
    DocumentChunk,
    File,
    FileVersion,
    IngestionRun,
    KnowledgeSource,
    Project,
    SecurityEvent,
    User,
    Workflow,
    utc_now,
)
from permissions import ROLES, canonical_role, permission_matrix, role_can
from semantic_search import (
    EMBEDDING_DIMENSIONS,
    EMBEDDING_MODEL,
    EmbeddingError,
    MIN_SEARCH_SCORE,
    build_chunk_embedding_text,
    cosine_similarity,
    embed_text,
    validate_embedding,
)

MAX_REQUEST_BODY_BYTES = 1_048_576
STATIC_DIR = Path(__file__).resolve().parent / "static"

app = FastAPI(title="CCL AI Suite", version="0.1.0")
Entity = TypeVar("Entity")
PROJECT_ROOT = DEFAULT_PROJECT_ROOT
BACKUP_ROOT = DEFAULT_BACKUP_ROOT


class HealthResponse(BaseModel):
    status: str


@app.get("/", include_in_schema=False)
async def web_app() -> HTMLResponse:
    """Serve the browser prototype for the current API operations."""

    return HTMLResponse((STATIC_DIR / "index.html").read_text(encoding="utf-8"))


@app.get("/static/styles.css", include_in_schema=False)
async def web_styles() -> Response:
    """Serve the prototype stylesheet."""

    return Response(
        (STATIC_DIR / "styles.css").read_text(encoding="utf-8"),
        media_type="text/css",
    )


@app.get("/static/app.js", include_in_schema=False)
async def web_script() -> Response:
    """Serve the prototype browser logic."""

    return Response(
        (STATIC_DIR / "app.js").read_text(encoding="utf-8"),
        media_type="application/javascript",
    )


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
        logger.error("%s write failed because of a database constraint.", resource_name)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"{resource_name} could not be saved.",
        )
    except SQLAlchemyError:
        db.rollback()
        logger.error("%s write failed because the database was unavailable.", resource_name)
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


def _record_access_denial(db: Session, request: Request, actor: User, permission: str) -> None:
    """Record a denied authorization decision without request payload data."""

    logger.warning(
        "Denied %s for role %s on %s",
        permission,
        actor.role,
        request.url.path,
    )
    try:
        db.add(
            SecurityEvent(
                actor_id=actor.id,
                event_code="access.denied",
                outcome="denied",
                resource_type="permission",
                resource_ref=request.url.path[:128],
            )
        )
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        logger.error("Access denial could not be recorded.")


def authenticated_actor_id(
    db: Session,
    request: Request,
    actor: User,
    claimed_actor_id: UUID | None,
    field_name: str,
) -> UUID:
    """Bind optional caller identity fields to the authenticated actor."""

    if claimed_actor_id is not None and claimed_actor_id != actor.id:
        _record_access_denial(db, request, actor, f"identity.{field_name}")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"{field_name} must match the authenticated user.",
        )
    return actor.id


def require_permission(permission: str):
    """Build a dependency that enforces one role permission.

    The local development fallback uses the first provisioned user when no
    ``X-User-ID`` header is supplied, preserving the prototype workflow. A
    production deployment must always provide the header.
    """

    async def dependency(request: Request, db: Session = Depends(get_db)) -> User:
        raw_actor_id = request.headers.get("x-user-id")
        actor: User | None = None
        if raw_actor_id:
            try:
                actor_id = UUID(raw_actor_id)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="X-User-ID must be a valid user identifier.",
                )
            actor = require_record(db, User, actor_id, "User was not found.")
        elif ENVIRONMENT.lower() == "development":
            actor = db.scalar(select(User).order_by(User.created_at, User.id))

        if actor is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="An authenticated user is required.",
            )
        if not role_can(actor.role, permission):
            _record_access_denial(db, request, actor, permission)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to perform this action.",
            )
        return actor

    return dependency


def project_storage_root(project: Project) -> Path:
    """Resolve one database project to its approved filesystem directory."""

    approved_projects_root = resolve_approved_root(PROJECT_ROOT)
    return resolve_approved_root(approved_projects_root / project.storage_slug)


def backup_storage_for_record(backup: Backup) -> BackupStoragePaths:
    """Resolve a persisted backup through generated keys, never raw path text."""

    storage = backup_storage_paths(BACKUP_ROOT, backup.project_id, backup.id)
    if (
        storage.artifact_key != backup.artifact_key
        or storage.manifest_key != backup.manifest_key
    ):
        raise BackupIntegrityError("Backup metadata does not match generated storage paths.")
    return storage


def require_project_backup(
    db: Session,
    project_id: UUID,
    backup_id: UUID,
) -> tuple[Project, Backup]:
    """Load a backup only when it belongs to the requested project."""

    project = require_record(db, Project, project_id, "Project was not found.")
    backup = require_record(db, Backup, backup_id, "Backup was not found.")
    if backup.project_id != project_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Backup was not found.")
    return project, backup


def project_relative_path(root: Path, candidate: str, label: str) -> Path:
    """Resolve one user-supplied project-relative path without traversal."""

    path = Path(candidate)
    if path.is_absolute() or any(part in {".", ".."} for part in path.parts):
        raise ValueError(f"{label} must be a relative path without dot segments.")
    candidate_path = root / path
    if candidate_path.is_symlink():
        raise ValueError(f"{label} must not be a symlink.")
    resolved = candidate_path.resolve(strict=False)
    safe_relative_path(root, resolved)
    return resolved


def organization_plan_response(
    project_id: UUID,
    plan: OrganizationPlan,
    plan_path: Path,
) -> OrganizationPlanResponse:
    """Translate an internal organiser plan without exposing host paths."""

    root = Path(plan.root)
    return OrganizationPlanResponse(
        project_id=project_id,
        plan_path=safe_relative_path(root, plan_path).as_posix(),
        created_at=datetime.fromisoformat(plan.created_at),
        actions=[
            OrganizationActionResponse(
                source=action.source,
                destination=action.destination,
                status=action.status,
                reason=action.reason,
                sha256=action.sha256,
            )
            for action in plan.actions
        ],
    )


def inventory_record_response(record: FileRecord) -> InventoryRecordResponse:
    """Translate one scanner record into the API response contract."""

    return InventoryRecordResponse(
        relative_path=record.relative_path,
        name=record.name,
        extension=record.extension,
        mime_type=record.mime_type,
        size_bytes=record.size_bytes,
        modified_at=datetime.fromisoformat(record.modified_at),
        sha256=record.sha256,
        extension_mime_match=record.extension_mime_match,
    )


def record_rejected_upload(
    db: Session,
    project_id: UUID,
    storage_key: str,
    reason: str,
    actor_id: UUID,
) -> None:
    """Log a rejected upload without storing its request body."""

    logger.warning("Rejected upload for project %s: %s", project_id, reason)
    try:
        db.add(
            SecurityEvent(
                actor_id=actor_id,
                event_code="file.upload.rejected",
                outcome="denied",
                resource_type="file",
                resource_ref=storage_key[:128] or "unknown",
            )
        )
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        logger.error("Rejected upload could not be recorded for project %s.", project_id)


def record_backup_event(
    db: Session,
    actor_id: UUID,
    backup_id: UUID,
    event_code: str,
    outcome: str,
) -> None:
    """Record one backup lifecycle event without storing destination paths or bodies."""

    try:
        db.add(
            SecurityEvent(
                actor_id=actor_id,
                event_code=event_code,
                outcome=outcome,
                resource_type="backup",
                resource_ref=str(backup_id),
            )
        )
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        logger.error("Backup security event could not be recorded for %s.", backup_id)


def record_knowledge_source_event(
    db: Session,
    actor_id: UUID,
    source_id: UUID,
    event_code: str,
    outcome: str,
) -> None:
    """Record a source lifecycle event without document text or paths."""

    try:
        db.add(
            SecurityEvent(
                actor_id=actor_id,
                event_code=event_code,
                outcome=outcome,
                resource_type="knowledge_source",
                resource_ref=str(source_id),
            )
        )
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        logger.error(
            "Knowledge-source security event could not be recorded for %s.",
            source_id,
        )


def cleanup_failed_upload(upload_result: UploadResult | None) -> None:
    """Remove an upload when its metadata transaction cannot be completed."""

    if upload_result is None:
        return
    try:
        upload_result.destination.unlink(missing_ok=True)
    except OSError:
        logger.error("Failed upload cleanup could not remove its destination.")


def cleanup_failed_backup(artifact: BackupArtifact | None) -> None:
    """Remove newly-created backup artifacts after a failed API transaction."""

    if artifact is None:
        return
    try:
        remove_backup_artifacts(artifact.storage)
    except (BackupArtifactError, BackupPathError, OSError):
        logger.error("Failed backup cleanup could not remove its generated artifacts.")


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


@app.get("/permissions", response_model=PermissionMatrixResponse, tags=["users"])
async def list_permissions() -> PermissionMatrixResponse:
    """Return the static role-permission matrix used by authorization checks."""

    return PermissionMatrixResponse(roles=permission_matrix())


@app.get("/upload-policy", response_model=UploadPolicyResponse, tags=["files"])
async def get_upload_policy() -> UploadPolicyResponse:
    """Return the allowlisted upload types and size limit."""

    return UploadPolicyResponse(**upload_policy())


@app.post(
    "/project-folders",
    response_model=FolderGenerateResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["file-automation"],
    dependencies=[
        Depends(reject_oversized_requests),
        Depends(require_permission("project.create")),
    ],
)
async def generate_project_folder(
    request: FolderGenerateCreate,
) -> FolderGenerateResponse:
    """Create one standard project folder below the configured root."""

    try:
        folders = create_project_folder(request.project_name, PROJECT_ROOT)
    except FileExistsError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Project folder already exists.",
        )
    except PermissionError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="The configured projects root is not available for writing.",
        )
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    except OSError:
        logger.error("Project folder creation failed.")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Project folder could not be created.",
        )

    return FolderGenerateResponse(
        name=folders.name,
        project_path=safe_relative_path(folders.root, folders.project).as_posix(),
        subdirectories=[
            safe_relative_path(folders.root, path).as_posix()
            for path in folders.subdirectories
        ],
    )


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
    if canonical_role(user.role) not in ROLES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="User role is not supported.",
        )
    created_user = persist_record(
        db,
        User(external_ref=user.external_ref, role=user.role),
        "User",
    )
    return UserResponse.model_validate(created_user)


@app.get("/users/{user_id}", response_model=UserResponse, tags=["users"])
async def get_user(user_id: UUID, db: Session = Depends(get_db)) -> UserResponse:
    """Return one development user by its opaque identifier."""

    require_development_provisioning()
    user = require_record(db, User, user_id, "User was not found.")
    return UserResponse.model_validate(user)


@app.post(
    "/projects",
    response_model=ProjectResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["projects"],
    dependencies=[
        Depends(reject_oversized_requests),
        Depends(require_permission("project.create")),
    ],
)
async def create_project(
    project: ProjectCreate, db: Session = Depends(get_db)
) -> ProjectResponse:
    owner = require_record(db, User, project.owner_id, "Project owner was not found.")
    try:
        storage_slug = normalize_project_name(project.title)
    except (TypeError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc
    if db.scalar(select(Project.id).where(Project.storage_slug == storage_slug)):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "A project already uses this storage folder. "
                "Choose a title that produces a different folder name."
            ),
        )
    created_project = persist_record(
        db,
        Project(
            owner_id=owner.id,
            name=project.title,
            storage_slug=storage_slug,
            description=project.description,
        ),
        "Project",
    )
    return ProjectResponse.from_model(created_project)


@app.get(
    "/projects",
    response_model=list[ProjectResponse],
    tags=["projects"],
    dependencies=[Depends(require_permission("project.read"))],
)
async def list_projects(db: Session = Depends(get_db)) -> list[ProjectResponse]:
    projects = list_records(
        db,
        select(Project).order_by(Project.created_at, Project.id),
    )
    return [ProjectResponse.from_model(project) for project in projects]


def require_project_knowledge_source(
    db: Session,
    project_id: UUID,
    source_id: UUID,
) -> tuple[Project, KnowledgeSource]:
    """Load a source only when it belongs to the requested project."""

    project = require_record(db, Project, project_id, "Project was not found.")
    source = require_record(db, KnowledgeSource, source_id, "Knowledge source was not found.")
    if source.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Knowledge source was not found.",
        )
    return project, source


def require_approved_knowledge_source(
    db: Session,
    project_id: UUID,
    source_id: UUID,
) -> tuple[Project, KnowledgeSource]:
    """Load one source only when approval and active-file checks both pass."""

    project = require_record(db, Project, project_id, "Project was not found.")
    try:
        source = db.scalar(
            build_approved_knowledge_sources_statement(project_id).where(
                KnowledgeSource.id == source_id
            )
        )
    except SQLAlchemyError:
        logger.error("Approved knowledge-source lookup failed.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database temporarily unavailable.",
        )
    if source is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Approved knowledge source was not found.",
        )
    return project, source


def record_failed_ingestion(
    db: Session,
    project_id: UUID,
    source_id: UUID,
    source_checksum_sha256: str,
    error_message: str,
) -> None:
    """Persist a bounded failure record without storing source content."""

    try:
        db.add(
            IngestionRun(
                project_id=project_id,
                source_id=source_id,
                source_checksum_sha256=source_checksum_sha256,
                status="failed",
                error_message=error_message[:512],
            )
        )
        db.commit()
    except SQLAlchemyError:
        db.rollback()
        logger.error("Document-ingestion failure could not be recorded for %s.", source_id)


def ingestion_response(
    ingestion_run: IngestionRun,
    chunks: list[DocumentChunk],
) -> IngestionResponse:
    """Translate one completed ingestion and its source-linked chunks."""

    return IngestionResponse(
        id=ingestion_run.id,
        project_id=ingestion_run.project_id,
        source_id=ingestion_run.source_id,
        source_checksum_sha256=ingestion_run.source_checksum_sha256,
        status=ingestion_run.status,
        chunk_count=ingestion_run.chunk_count,
        error_message=ingestion_run.error_message,
        created_at=ingestion_run.created_at,
        completed_at=ingestion_run.completed_at,
        chunks=[DocumentChunkResponse.model_validate(chunk) for chunk in chunks],
    )


def persist_document_ingestion(
    db: Session,
    project_id: UUID,
    source_id: UUID,
    source_title: str,
    source_checksum_sha256: str,
    chunks: tuple[ChunkDraft, ...],
) -> tuple[IngestionRun, list[DocumentChunk]]:
    """Persist a completed extraction and all of its deterministic chunks."""

    ingestion_run = IngestionRun(
        project_id=project_id,
        source_id=source_id,
        source_checksum_sha256=source_checksum_sha256,
        status="completed",
        chunk_count=len(chunks),
        completed_at=utc_now(),
    )
    persisted_chunks: list[DocumentChunk] = []
    for chunk in chunks:
        try:
            embedding = list(
                embed_text(
                    build_chunk_embedding_text(
                        source_title,
                        chunk.heading,
                        chunk.content,
                    )
                )
            )
        except EmbeddingError as exc:
            logger.error("Document chunk could not be indexed for source %s.", source_id)
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="Document could not be indexed safely.",
            ) from exc
        persisted_chunks.append(
            DocumentChunk(
                project_id=project_id,
                source_id=source_id,
                chunk_index=chunk.chunk_index,
                title=source_title,
                heading=chunk.heading,
                location=chunk.location,
                line_start=chunk.line_start,
                line_end=chunk.line_end,
                content=chunk.content,
                character_count=chunk.character_count,
                word_count=chunk.word_count,
                checksum_sha256=chunk.checksum_sha256,
                embedding=embedding,
                embedding_model=EMBEDDING_MODEL,
                embedding_dimensions=EMBEDDING_DIMENSIONS,
            )
        )
    ingestion_run.chunks = persisted_chunks
    try:
        db.add(ingestion_run)
        db.commit()
        db.refresh(ingestion_run)
    except IntegrityError:
        db.rollback()
        logger.error("Document-ingestion records violated a database constraint.")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Document ingestion could not be saved.",
        )
    except SQLAlchemyError:
        db.rollback()
        logger.error("Document-ingestion records could not be saved.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database temporarily unavailable.",
        )
    return ingestion_run, list(ingestion_run.chunks)


@app.post(
    "/projects/{project_id}/knowledge-sources/{source_id}/ingest",
    response_model=IngestionResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["knowledge-base"],
    dependencies=[Depends(reject_oversized_requests)],
)
async def ingest_knowledge_source(
    project_id: UUID,
    source_id: UUID,
    actor: User = Depends(require_permission("knowledge.ingest")),
    db: Session = Depends(get_db),
) -> IngestionResponse:
    """Extract and chunk one approved source as untrusted data."""

    project, source = require_approved_knowledge_source(db, project_id, source_id)
    expected_checksum = source.file.checksum_sha256.lower()
    try:
        root = project_storage_root(project)
        source_path = project_relative_path(root, source.file.storage_key, "Source file")
        prepared = prepare_document(
            source_path,
            storage_key=source.file.storage_key,
            media_type=source.file.media_type,
        )
        if prepared.document.checksum_sha256 != expected_checksum:
            raise DocumentProcessingError(
                "Source file changed since its inventory was recorded."
            )
    except (FileNotFoundError, NotADirectoryError) as exc:
        db.rollback()
        record_failed_ingestion(
            db,
            project_id,
            source_id,
            expected_checksum,
            "Project storage was not found.",
        )
        record_knowledge_source_event(
            db,
            actor.id,
            source_id,
            "knowledge_source.ingestion_failed",
            "failure",
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project storage was not found.",
        ) from exc
    except PermissionError as exc:
        db.rollback()
        record_failed_ingestion(
            db,
            project_id,
            source_id,
            expected_checksum,
            "Project storage is not available for ingestion.",
        )
        record_knowledge_source_event(
            db,
            actor.id,
            source_id,
            "knowledge_source.ingestion_failed",
            "failure",
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Project storage is not available for ingestion.",
        ) from exc
    except (DocumentProcessingError, OSError, ValueError) as exc:
        db.rollback()
        record_failed_ingestion(
            db,
            project_id,
            source_id,
            expected_checksum,
            str(exc),
        )
        record_knowledge_source_event(
            db,
            actor.id,
            source_id,
            "knowledge_source.ingestion_failed",
            "failure",
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Document could not be ingested safely.",
        ) from exc

    ingestion_run, chunks = persist_document_ingestion(
        db,
        project_id,
        source_id,
        source.title,
        prepared.document.checksum_sha256,
        prepared.chunks,
    )
    record_knowledge_source_event(
        db,
        actor.id,
        source_id,
        "knowledge_source.ingested",
        "success",
    )
    return ingestion_response(ingestion_run, chunks)


@app.post(
    "/projects/{project_id}/knowledge-sources",
    response_model=KnowledgeSourceResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["knowledge-base"],
    dependencies=[
        Depends(reject_oversized_requests),
    ],
)
async def register_knowledge_source(
    project_id: UUID,
    source_request: KnowledgeSourceCreate,
    actor: User = Depends(require_permission("knowledge.register")),
    db: Session = Depends(get_db),
) -> KnowledgeSourceResponse:
    """Register one active project file for review without accepting its text."""

    require_record(db, Project, project_id, "Project was not found.")
    file_record = require_record(db, File, source_request.file_id, "File was not found.")
    if file_record.project_id != project_id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File was not found.",
        )
    if file_record.status != "active":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only active files can be registered as knowledge sources.",
        )
    owner = require_record(db, User, source_request.owner_id, "Knowledge-source owner was not found.")
    if db.scalar(
        select(KnowledgeSource.id).where(
            KnowledgeSource.project_id == project_id,
            KnowledgeSource.file_id == source_request.file_id,
        )
    ):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This file is already registered as a knowledge source.",
        )

    source = persist_record(
        db,
        KnowledgeSource(
            project_id=project_id,
            file_id=file_record.id,
            owner_id=owner.id,
            created_by_id=actor.id,
            title=source_request.title,
            source_type=source_request.source_type,
            sensitivity=source_request.sensitivity,
            approval_status="pending",
        ),
        "Knowledge source",
    )
    record_knowledge_source_event(
        db,
        actor.id,
        source.id,
        "knowledge_source.registered",
        "success",
    )
    return KnowledgeSourceResponse.from_model(source)


@app.get(
    "/projects/{project_id}/knowledge-sources",
    response_model=list[KnowledgeSourceResponse],
    tags=["knowledge-base"],
    dependencies=[Depends(require_permission("knowledge.read"))],
)
async def list_project_knowledge_sources(
    project_id: UUID,
    db: Session = Depends(get_db),
) -> list[KnowledgeSourceResponse]:
    """List source metadata for one project, including review state."""

    require_record(db, Project, project_id, "Project was not found.")
    sources = list_records(
        db,
        select(KnowledgeSource)
        .where(KnowledgeSource.project_id == project_id)
        .order_by(KnowledgeSource.created_at, KnowledgeSource.id),
    )
    return [KnowledgeSourceResponse.from_model(source) for source in sources]


@app.post(
    "/projects/{project_id}/knowledge-sources/{source_id}/review",
    response_model=KnowledgeSourceResponse,
    tags=["knowledge-base"],
    dependencies=[
        Depends(reject_oversized_requests),
    ],
)
async def review_knowledge_source(
    project_id: UUID,
    source_id: UUID,
    decision: KnowledgeSourceDecision,
    actor: User = Depends(require_permission("knowledge.approve")),
    db: Session = Depends(get_db),
) -> KnowledgeSourceResponse:
    """Approve or reject a source before any future ingestion can consume it."""

    _project, source = require_project_knowledge_source(db, project_id, source_id)
    if decision.decision == "rejected" and not decision.reason:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="A rejection reason is required.",
        )
    if decision.decision == "approved" and source.file.status != "active":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Only active files can be approved as knowledge sources.",
        )

    source.approval_status = decision.decision
    source.reviewed_by_id = actor.id
    source.reviewed_at = utc_now()
    source.rejection_reason = decision.reason if decision.decision == "rejected" else None
    try:
        db.commit()
        db.refresh(source)
    except SQLAlchemyError:
        db.rollback()
        logger.error("Knowledge-source review could not be saved for %s.", source_id)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database temporarily unavailable.",
        )

    record_knowledge_source_event(
        db,
        actor.id,
        source.id,
        f"knowledge_source.{decision.decision}",
        "success",
    )
    return KnowledgeSourceResponse.from_model(source)


@app.post(
    "/projects/{project_id}/backups",
    response_model=BackupResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["backups"],
    dependencies=[Depends(reject_oversized_requests)],
)
async def create_project_backup(
    project_id: UUID,
    _backup_request: BackupCreate | None = None,
    actor: User = Depends(require_permission("backup.create")),
    db: Session = Depends(get_db),
) -> BackupResponse:
    """Create, re-verify, and persist one project backup."""

    project = require_record(db, Project, project_id, "Project was not found.")
    artifact: BackupArtifact | None = None
    try:
        artifact = create_backup(
            project_storage_root(project),
            BACKUP_ROOT,
            project_id,
            uuid4(),
        )
        verification = verify_backup(
            artifact.storage,
            expected_archive_checksum=artifact.archive_checksum_sha256,
            expected_manifest_checksum=artifact.manifest_checksum_sha256,
            expected_project_ref=project_id,
        )
        backup = Backup(
            id=artifact.storage.backup_id,
            project_id=project_id,
            created_by_id=actor.id,
            artifact_key=artifact.artifact_key,
            manifest_key=artifact.manifest_key,
            archive_size_bytes=artifact.archive_size_bytes,
            file_count=verification.file_count,
            total_bytes=verification.bytes_verified,
            archive_checksum_sha256=verification.archive_checksum_sha256,
            manifest_checksum_sha256=verification.manifest_checksum_sha256,
            status="verified",
            verified_at=utc_now(),
        )
        db.add(backup)
        db.commit()
        db.refresh(backup)
    except (FileNotFoundError, NotADirectoryError):
        db.rollback()
        cleanup_failed_backup(artifact)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project storage was not found.",
        )
    except PermissionError:
        db.rollback()
        cleanup_failed_backup(artifact)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Project or backup storage is not available.",
        )
    except IntegrityError:
        db.rollback()
        cleanup_failed_backup(artifact)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Project backup could not be saved.",
        )
    except SQLAlchemyError:
        db.rollback()
        cleanup_failed_backup(artifact)
        logger.error("Project backup metadata could not be saved for %s.", project_id)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database temporarily unavailable.",
        )
    except (BackupSourceError, BackupArtifactError, BackupPathError, OSError):
        db.rollback()
        cleanup_failed_backup(artifact)
        logger.error("Project backup creation failed for %s.", project_id)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Project backup could not be created safely.",
        )

    record_backup_event(db, actor.id, backup.id, "backup.created", "success")
    return BackupResponse.model_validate(backup)


@app.get(
    "/projects/{project_id}/backups",
    response_model=list[BackupResponse],
    tags=["backups"],
    dependencies=[Depends(require_permission("backup.read"))],
)
async def list_project_backups(
    project_id: UUID,
    db: Session = Depends(get_db),
) -> list[BackupResponse]:
    """List only the backup metadata belonging to one project."""

    require_record(db, Project, project_id, "Project was not found.")
    backups = list_records(
        db,
        select(Backup)
        .where(Backup.project_id == project_id)
        .order_by(Backup.created_at.desc(), Backup.id),
    )
    return [BackupResponse.model_validate(backup) for backup in backups]


@app.post(
    "/projects/{project_id}/backups/{backup_id}/verify",
    response_model=BackupVerifyResponse,
    tags=["backups"],
    dependencies=[
        Depends(reject_oversized_requests),
    ],
)
async def verify_project_backup(
    project_id: UUID,
    backup_id: UUID,
    actor: User = Depends(require_permission("backup.verify")),
    db: Session = Depends(get_db),
) -> BackupVerifyResponse:
    """Recheck a persisted backup archive and update its verification time."""

    _project, backup = require_project_backup(db, project_id, backup_id)
    try:
        verification = verify_backup(
            backup_storage_for_record(backup),
            expected_archive_checksum=backup.archive_checksum_sha256,
            expected_manifest_checksum=backup.manifest_checksum_sha256,
            expected_project_ref=project_id,
        )
    except BackupIntegrityError:
        record_backup_event(db, actor.id, backup.id, "backup.verification_failed", "failure")
        logger.warning("Backup integrity verification failed for %s.", backup_id)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Backup failed integrity verification.",
        )
    except BackupArtifactError:
        record_backup_event(db, actor.id, backup.id, "backup.verification_failed", "failure")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Backup artifact was not found.",
        )
    except (BackupPathError, FileNotFoundError, NotADirectoryError, OSError):
        record_backup_event(db, actor.id, backup.id, "backup.verification_failed", "failure")
        logger.error("Backup storage could not be verified for %s.", backup_id)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Backup could not be verified safely.",
        )

    backup.status = "verified"
    backup.verified_at = utc_now()
    try:
        db.commit()
        db.refresh(backup)
    except SQLAlchemyError:
        db.rollback()
        logger.error("Backup verification metadata could not be saved for %s.", backup_id)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database temporarily unavailable.",
        )
    record_backup_event(db, actor.id, backup.id, "backup.verified", "success")
    return BackupVerifyResponse(
        project_id=project_id,
        backup=BackupResponse.model_validate(backup),
        entries_verified=verification.entries_verified,
        files_verified=verification.file_count,
        bytes_verified=verification.bytes_verified,
    )


@app.post(
    "/projects/{project_id}/backups/{backup_id}/restore",
    response_model=BackupRestoreResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["backups"],
    dependencies=[
        Depends(reject_oversized_requests),
    ],
)
async def restore_project_backup(
    project_id: UUID,
    backup_id: UUID,
    restore_request: BackupRestoreCreate,
    actor: User = Depends(require_permission("backup.restore")),
    db: Session = Depends(get_db),
) -> BackupRestoreResponse:
    """Restore a verified project backup to a new path below project storage."""

    _project, backup = require_project_backup(db, project_id, backup_id)
    try:
        result = restore_backup(
            backup_storage_for_record(backup),
            PROJECT_ROOT,
            restore_request.destination_path,
            expected_archive_checksum=backup.archive_checksum_sha256,
            expected_manifest_checksum=backup.manifest_checksum_sha256,
            expected_project_ref=project_id,
        )
    except BackupDestinationExistsError:
        record_backup_event(db, actor.id, backup.id, "backup.restore_failed", "failure")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Restore destination already exists.",
        )
    except BackupIntegrityError:
        record_backup_event(db, actor.id, backup.id, "backup.restore_failed", "failure")
        logger.warning("Project backup integrity check failed for %s.", backup_id)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Backup failed integrity verification.",
        )
    except BackupPathError:
        record_backup_event(db, actor.id, backup.id, "backup.restore_failed", "failure")
        logger.warning("Rejected backup restore path for %s.", backup_id)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Restore destination must remain inside project storage.",
        )
    except BackupArtifactError:
        record_backup_event(db, actor.id, backup.id, "backup.restore_failed", "failure")
        logger.error("Project backup artifact could not be restored for %s.", backup_id)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Project backup could not be restored safely.",
        )
    except (FileNotFoundError, NotADirectoryError):
        record_backup_event(db, actor.id, backup.id, "backup.restore_failed", "failure")
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project or backup storage was not found.",
        )
    except PermissionError:
        record_backup_event(db, actor.id, backup.id, "backup.restore_failed", "failure")
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Project storage is not available for restoration.",
        )
    except OSError:
        record_backup_event(db, actor.id, backup.id, "backup.restore_failed", "failure")
        logger.error("Project backup restore failed for %s.", backup_id)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Project backup could not be restored safely.",
        )

    backup.status = "restored"
    backup.restored_at = utc_now()
    try:
        db.commit()
        db.refresh(backup)
    except SQLAlchemyError:
        db.rollback()
        logger.error("Backup restore metadata could not be saved for %s.", backup_id)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database temporarily unavailable.",
        )
    record_backup_event(db, actor.id, backup.id, "backup.restored", "success")
    return BackupRestoreResponse(
        project_id=project_id,
        backup_id=backup_id,
        destination_path=result.destination_relative.as_posix(),
        entries_restored=result.entries_restored,
        files_restored=result.file_count,
        bytes_restored=result.bytes_restored,
        archive_checksum_sha256=result.archive_checksum_sha256,
        manifest_checksum_sha256=result.manifest_checksum_sha256,
    )


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
    request: Request,
    actor: User = Depends(require_permission("file.upload")),
    db: Session = Depends(get_db),
) -> FileResponse:
    require_record(db, Project, project_id, "Project was not found.")
    uploaded_by_id = authenticated_actor_id(
        db,
        request,
        actor,
        file_metadata.uploaded_by_id,
        "uploaded_by_id",
    )
    try:
        storage_key = validate_storage_key(file_metadata.storage_key)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))

    created_file = persist_record(
        db,
        File(
            project_id=project_id,
            uploaded_by_id=uploaded_by_id,
            storage_key=storage_key,
            name=file_metadata.name or Path(storage_key).name,
            extension=file_metadata.extension or Path(storage_key).suffix.lower(),
            media_type=file_metadata.media_type,
            size_bytes=file_metadata.size_bytes,
            checksum_sha256=file_metadata.checksum_sha256.lower(),
        ),
        "File metadata",
    )
    return FileResponse.model_validate(created_file)


@app.put(
    "/projects/{project_id}/uploads/{storage_key:path}",
    response_model=UploadResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["files"],
    dependencies=[Depends(reject_oversized_requests)],
)
async def upload_project_file(
    project_id: UUID,
    storage_key: str,
    request: Request,
    actor: User = Depends(require_permission("file.upload")),
    db: Session = Depends(get_db),
) -> UploadResponse:
    """Stream one allow-listed file into project storage and index its metadata."""

    project = require_record(db, Project, project_id, "Project was not found.")
    upload_result: UploadResult | None = None
    try:
        raw_content_length = request.headers.get("content-length")
        content_length = int(raw_content_length) if raw_content_length is not None else None
        root = project_storage_root(project)
        upload_result = await store_upload(
            root,
            storage_key,
            request.headers.get("content-type"),
            request.stream(),
            content_length=content_length,
        )
        record = FileRecord(
            relative_path=upload_result.storage_key,
            name=upload_result.name,
            extension=upload_result.extension,
            mime_type=upload_result.media_type,
            size_bytes=upload_result.size_bytes,
            modified_at=upload_result.modified_at.isoformat(),
            sha256=upload_result.checksum_sha256,
            extension_mime_match=True,
        )
        sync_result = sync_inventory_records(
            db,
            project_id,
            [record],
            approved_root=root,
        )
        if sync_result.records:
            sync_result.records[0].uploaded_by_id = actor.id
        db.commit()
    except UploadDestinationExistsError as exc:
        db.rollback()
        record_rejected_upload(db, project_id, storage_key, str(exc), actor.id)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Upload destination already exists.",
        )
    except UploadTooLargeError as exc:
        db.rollback()
        record_rejected_upload(db, project_id, storage_key, str(exc), actor.id)
        raise HTTPException(
            status_code=status.HTTP_413_CONTENT_TOO_LARGE,
            detail="Uploaded file exceeds the maximum allowed size.",
        )
    except UploadValidationError as exc:
        db.rollback()
        record_rejected_upload(db, project_id, storage_key, str(exc), actor.id)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Upload was rejected by the file safety policy.",
        )
    except (FileNotFoundError, NotADirectoryError):
        db.rollback()
        cleanup_failed_upload(upload_result)
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project storage was not found.",
        )
    except PermissionError:
        db.rollback()
        cleanup_failed_upload(upload_result)
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Project storage is not available for uploads.",
        )
    except (IntegrityError, SQLAlchemyError):
        db.rollback()
        cleanup_failed_upload(upload_result)
        logger.error("Upload metadata could not be saved for project %s.", project_id)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Upload metadata could not be saved.",
        )
    except (OSError, UploadWriteError, ValueError):
        db.rollback()
        cleanup_failed_upload(upload_result)
        logger.error("Upload failed for project %s.", project_id)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Upload could not be stored safely.",
        )

    if upload_result is None or not sync_result.records:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Upload metadata was not created.",
        )
    file_record = sync_result.records[0]
    return UploadResponse(
        project_id=project_id,
        file_id=file_record.id,
        storage_key=upload_result.storage_key,
        name=upload_result.name,
        extension=upload_result.extension,
        media_type=upload_result.media_type,
        size_bytes=upload_result.size_bytes,
        checksum_sha256=upload_result.checksum_sha256,
        status=file_record.status,
    )


@app.get(
    "/projects/{project_id}/files",
    response_model=list[FileResponse],
    tags=["files"],
    dependencies=[Depends(require_permission("file.read"))],
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


@app.get(
    "/projects/{project_id}/files/search",
    response_model=list[FileResponse],
    tags=["files"],
    dependencies=[Depends(require_permission("file.read"))],
)
async def search_project_files(
    project_id: UUID,
    query: str | None = Query(default=None, max_length=255),
    checksum_sha256: str | None = Query(
        default=None,
        min_length=64,
        max_length=64,
        pattern=r"^[0-9a-fA-F]{64}$",
    ),
    media_type: str | None = Query(default=None, max_length=127),
    file_status: str | None = Query(default=None, alias="status", max_length=24),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
) -> list[FileResponse]:
    """Search only the metadata belonging to one project."""

    require_record(db, Project, project_id, "Project was not found.")
    try:
        statement = build_file_search_statement(
            project_id,
            query=query,
            checksum_sha256=checksum_sha256,
            media_type=media_type,
            file_status=file_status,
            limit=limit,
            offset=offset,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    files = list_records(db, statement)
    return [FileResponse.model_validate(file_metadata) for file_metadata in files]


@app.get(
    "/projects/{project_id}/files/{file_id}",
    response_model=FileResponse,
    tags=["files"],
    dependencies=[Depends(require_permission("file.read"))],
)
async def get_project_file(
    project_id: UUID,
    file_id: UUID,
    db: Session = Depends(get_db),
) -> FileResponse:
    """Return one file record without exposing files from another project."""

    require_record(db, Project, project_id, "Project was not found.")
    file_record = require_record(db, File, file_id, "File was not found.")
    if file_record.project_id != project_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File was not found.")
    return FileResponse.model_validate(file_record)


@app.get(
    "/projects/{project_id}/files/{file_id}/history",
    response_model=list[FileHistoryResponse],
    tags=["files"],
    dependencies=[Depends(require_permission("file.read"))],
)
async def list_project_file_history(
    project_id: UUID,
    file_id: UUID,
    db: Session = Depends(get_db),
) -> list[FileHistoryResponse]:
    """Return immutable inventory snapshots for one project file."""

    require_record(db, Project, project_id, "Project was not found.")
    file_record = require_record(db, File, file_id, "File was not found.")
    if file_record.project_id != project_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File was not found.")
    history = list_records(db, build_file_history_statement(project_id, file_id))
    return [FileHistoryResponse.model_validate(entry) for entry in history]


@app.get(
    "/projects/{project_id}/files/{file_id}/versions",
    response_model=list[FileVersionResponse],
    tags=["files"],
    dependencies=[Depends(require_permission("file.read"))],
)
async def list_project_file_versions(
    project_id: UUID,
    file_id: UUID,
    db: Session = Depends(get_db),
) -> list[FileVersionResponse]:
    """Return numbered immutable metadata versions for one project file."""

    require_record(db, Project, project_id, "Project was not found.")
    file_record = require_record(db, File, file_id, "File was not found.")
    if file_record.project_id != project_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File was not found.")
    versions = list_records(db, build_file_versions_statement(project_id, file_id))
    return [FileVersionResponse.model_validate(version) for version in versions]


@app.post(
    "/projects/{project_id}/files/{file_id}/versions/{version_number}/restore",
    response_model=FileRestoreResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["files"],
    dependencies=[
        Depends(reject_oversized_requests),
        Depends(require_permission("file.restore")),
    ],
)
async def restore_project_file_version(
    project_id: UUID,
    file_id: UUID,
    version_number: int,
    restore_request: FileRestoreCreate,
    db: Session = Depends(get_db),
) -> FileRestoreResponse:
    """Restore one archived version to a new, non-overwriting destination."""

    project = require_record(db, Project, project_id, "Project was not found.")
    file_record = require_record(db, File, file_id, "File was not found.")
    if file_record.project_id != project_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File was not found.")
    if version_number < 1:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Version number must be positive.")
    version = db.scalar(
        select(FileVersion).where(
            FileVersion.file_id == file_id,
            FileVersion.version_number == version_number,
        )
    )
    if version is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File version was not found.")

    try:
        result = restore_version_content(
            project_storage_root(project),
            version,
            restore_request.destination_path,
        )
    except (FileNotFoundError, NotADirectoryError, RestoreSourceUnavailableError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="The requested file version is unavailable.",
        )
    except RestoreDestinationExistsError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Restore destination already exists.",
        )
    except UnsafeRestorePathError as exc:
        logger.warning("Rejected restore path for project %s: %s", project_id, exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Restore destination must remain inside project storage and differ from the original.",
        )
    except PermissionError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Project storage is not available for restoration.",
        )
    except RestoreError:
        logger.error("File version restore failed for project %s.", project_id)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="File version could not be restored safely.",
        )

    return FileRestoreResponse(
        project_id=project_id,
        file_id=file_id,
        version_number=result.version_number,
        destination_path=result.destination_relative.as_posix(),
        checksum_sha256=result.checksum_sha256,
        bytes_restored=result.bytes_restored,
    )


@app.post(
    "/projects/{project_id}/conversions",
    response_model=ConversionResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["conversions"],
    dependencies=[
        Depends(reject_oversized_requests),
        Depends(require_permission("conversion.run")),
    ],
)
async def convert_project_file(
    project_id: UUID,
    conversion: ConversionCreate,
    db: Session = Depends(get_db),
) -> ConversionResponse:
    """Convert one file within a project's approved storage directory."""

    project = require_record(db, Project, project_id, "Project was not found.")
    try:
        root = project_storage_root(project)
        result = convert_file(
            root,
            conversion.source_path,
            conversion.destination_path,
        )
    except (FileNotFoundError, NotADirectoryError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversion source or project storage was not found.",
        )
    except ConversionDestinationExistsError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Conversion destination already exists.",
        )
    except UnsupportedFormatError as exc:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=str(exc),
        )
    except UnsafeConversionPathError as exc:
        logger.warning("Rejected conversion path for project %s: %s", project_id, exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Conversion paths must remain inside the approved project storage.",
        )
    except ConversionError:
        logger.error("Conversion failed for project %s.", project_id)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="File conversion failed validation.",
        )
    except ValueError as exc:
        logger.warning("Rejected conversion request for project %s: %s", project_id, exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Conversion paths must remain inside the approved project storage.",
        )
    except PermissionError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Project storage is not available for conversion.",
        )

    return ConversionResponse(
        project_id=project_id,
        source_path=result.source_relative.as_posix(),
        destination_path=result.destination_relative.as_posix(),
        source_format=result.source_format,
        destination_format=result.destination_format,
        bytes_written=result.bytes_written,
    )


@app.post(
    "/projects/{project_id}/inventory",
    response_model=InventoryResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["file-automation"],
    dependencies=[
        Depends(reject_oversized_requests),
        Depends(require_permission("file.read")),
    ],
)
async def inventory_project_files(
    project_id: UUID,
    db: Session = Depends(get_db),
) -> InventoryResponse:
    """Scan one project folder and write confined JSON and CSV manifests."""

    project = require_record(db, Project, project_id, "Project was not found.")
    try:
        root = project_storage_root(project)
        records = scan_files(root)
        manifest_paths = {
            "manifest.json",
            "manifest.csv",
        }
        # The scanner can see manifests from an earlier run.  They are
        # generated evidence, not project assets, so keep them out of the
        # searchable file-record database and duplicate counts.
        records = [record for record in records if record.relative_path not in manifest_paths]
        json_path, csv_path = write_manifests(root, records)
        sync_result = sync_inventory_records(
            db,
            project_id,
            records,
            approved_root=root,
        )
        db.commit()
    except IntegrityError:
        db.rollback()
        logger.error("Inventory records violated a database constraint for project %s.", project_id)
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Project inventory could not be saved.",
        )
    except SQLAlchemyError:
        db.rollback()
        logger.error("Inventory records could not be saved for project %s.", project_id)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database temporarily unavailable.",
        )
    except (FileNotFoundError, NotADirectoryError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project storage was not found.",
        )
    except PermissionError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Project storage is not available for scanning.",
        )
    except (OSError, ValueError):
        logger.error("Inventory scan failed for project %s.", project_id)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Project inventory could not be created.",
        )

    hash_counts = Counter(record.sha256 for record in records)
    duplicate_counts = [count for count in hash_counts.values() if count > 1]
    return InventoryResponse(
        project_id=project_id,
        files_scanned=len(records),
        duplicate_groups=len(duplicate_counts),
        duplicate_files=sum(duplicate_counts),
        json_manifest=safe_relative_path(root, json_path).as_posix(),
        csv_manifest=safe_relative_path(root, csv_path).as_posix(),
        records=[inventory_record_response(record) for record in records],
        records_persisted=len(sync_result.records),
        history_events=sync_result.history_events,
        versions_created=sync_result.versions_created,
    )


@app.post(
    "/projects/{project_id}/organization/plan",
    response_model=OrganizationPlanResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["file-automation"],
    dependencies=[
        Depends(reject_oversized_requests),
        Depends(require_permission("file.read")),
    ],
)
async def preview_project_organization(
    project_id: UUID,
    db: Session = Depends(get_db),
) -> OrganizationPlanResponse:
    """Build and persist a no-mutation organisation plan."""

    project = require_record(db, Project, project_id, "Project was not found.")
    try:
        root = project_storage_root(project)
        plan = build_plan(root)
        plan_path = write_plan(plan)
    except (FileNotFoundError, NotADirectoryError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project incoming directory was not found.",
        )
    except PermissionError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Project storage is not available for organising.",
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except OSError:
        logger.error("Organisation planning failed for project %s.", project_id)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Organisation plan could not be created.",
        )

    return organization_plan_response(project_id, plan, plan_path)


@app.post(
    "/projects/{project_id}/organization/apply",
    response_model=OrganizationApplyResponse,
    status_code=status.HTTP_201_CREATED,
    tags=["file-automation"],
    dependencies=[
        Depends(reject_oversized_requests),
        Depends(require_permission("file.organize")),
    ],
)
async def apply_project_organization(
    project_id: UUID,
    request: OrganizationApplyCreate,
    db: Session = Depends(get_db),
) -> OrganizationApplyResponse:
    """Apply conflict-free moves and optionally quarantine conflicts."""

    project = require_record(db, Project, project_id, "Project was not found.")
    try:
        root = project_storage_root(project)
        plan = build_plan(root)
        plan_path = write_plan(plan)
        journal_path = apply_plan(plan)
        quarantine_journal_path: Path | None = None
        conflict_count = sum(action.status == "conflict" for action in plan.actions)
        if request.quarantine_conflicts and conflict_count:
            quarantine_journal_path = quarantine_conflicts(plan)
    except (FileNotFoundError, NotADirectoryError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project incoming directory was not found.",
        )
    except PermissionError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Project storage is not available for organising.",
        )
    except (FileExistsError, ValueError) as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except OSError:
        logger.error("Organisation apply failed for project %s.", project_id)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Organisation could not be applied safely.",
        )

    return OrganizationApplyResponse(
        project_id=project_id,
        plan_path=safe_relative_path(root, plan_path).as_posix(),
        action_count=len(plan.actions),
        applied_count=sum(action.status == "planned" for action in plan.actions),
        conflict_count=conflict_count,
        journal_path=safe_relative_path(root, journal_path).as_posix(),
        quarantine_journal_path=(
            safe_relative_path(root, quarantine_journal_path).as_posix()
            if quarantine_journal_path is not None
            else None
        ),
    )


@app.post(
    "/projects/{project_id}/organization/rollback",
    response_model=OrganizationRollbackResponse,
    tags=["file-automation"],
    dependencies=[
        Depends(reject_oversized_requests),
        Depends(require_permission("file.organize")),
    ],
)
async def rollback_project_organization(
    project_id: UUID,
    request: OrganizationRollbackCreate,
    db: Session = Depends(get_db),
) -> OrganizationRollbackResponse:
    """Roll back one previously written organisation journal."""

    project = require_record(db, Project, project_id, "Project was not found.")
    try:
        root = project_storage_root(project)
        journal_path = project_relative_path(root, request.journal_path, "Journal path")
        restored_count = rollback_journal(root, journal_path)
    except (FileNotFoundError, NotADirectoryError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Project storage or journal was not found.",
        )
    except PermissionError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Project storage is not available for rollback.",
        )
    except FileExistsError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Rollback would overwrite an existing source file.",
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))
    except OSError:
        logger.error("Organisation rollback failed for project %s.", project_id)
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Organisation rollback could not be completed.",
        )

    return OrganizationRollbackResponse(
        project_id=project_id,
        journal_path=safe_relative_path(root, journal_path).as_posix(),
        restored_count=restored_count,
    )


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
    request: Request,
    actor: User = Depends(require_permission("workflow.manage")),
    db: Session = Depends(get_db),
) -> WorkflowResponse:
    require_record(db, Project, project_id, "Project was not found.")
    created_by_id = authenticated_actor_id(
        db,
        request,
        actor,
        workflow.created_by_id,
        "created_by_id",
    )

    created_workflow = persist_record(
        db,
        Workflow(
            project_id=project_id,
            created_by_id=created_by_id,
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
    dependencies=[Depends(require_permission("workflow.manage"))],
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
    request: Request,
    actor: User = Depends(require_permission("workflow.manage")),
    db: Session = Depends(get_db),
) -> ApprovalResponse:
    require_record(db, Workflow, workflow_id, "Workflow was not found.")
    requested_by_id = authenticated_actor_id(
        db,
        request,
        actor,
        approval.requested_by_id,
        "requested_by_id",
    )

    created_approval = persist_record(
        db,
        Approval(
            workflow_id=workflow_id,
            requested_by_id=requested_by_id,
        ),
        "Approval",
    )
    return ApprovalResponse.model_validate(created_approval)


@app.get(
    "/workflows/{workflow_id}/approvals",
    response_model=list[ApprovalResponse],
    tags=["approvals"],
    dependencies=[Depends(require_permission("workflow.manage"))],
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
    request: Request,
    actor: User = Depends(require_permission("approval.decide")),
    db: Session = Depends(get_db),
) -> ApprovalResponse:
    approval = require_record(db, Approval, approval_id, "Approval was not found.")
    if approval.status != "pending":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Approval has already been decided.",
        )
    approved_by_id = authenticated_actor_id(
        db,
        request,
        actor,
        decision.approved_by_id,
        "approved_by_id",
    )

    approval.status = decision.status
    approval.approved_by_id = approved_by_id
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
    event: SecurityEventCreate,
    request: Request,
    actor: User = Depends(require_permission("security.write")),
    db: Session = Depends(get_db),
) -> SecurityEventResponse:
    actor_id = authenticated_actor_id(db, request, actor, event.actor_id, "actor_id")

    created_event = persist_record(
        db,
        SecurityEvent(
            actor_id=actor_id,
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
    dependencies=[Depends(require_permission("security.read"))],
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
