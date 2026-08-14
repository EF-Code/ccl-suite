from __future__ import annotations

from datetime import datetime
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from database import get_db
from logger import logger
from models import Project, User

MAX_REQUEST_BODY_BYTES = 1_048_576

app = FastAPI(title="CCL AI Suite", version="0.1.0")


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


@app.get("/health", tags=["system"])
async def health() -> dict[str, str]:
    return {"status": "ok"}

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
    if not project.title:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="title cannot be blank",
        )

    try:
        if db.get(User, project.owner_id) is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Project owner was not found.",
            )

        created_project = Project(
            owner_id=project.owner_id,
            name=project.title,
            description=project.description,
        )
        db.add(created_project)
        db.commit()
        db.refresh(created_project)
    except HTTPException:
        raise
    except IntegrityError:
        db.rollback()
        logger.error("Project creation failed because of a database constraint.")
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Project could not be created.",
        )
    except SQLAlchemyError:
        db.rollback()
        logger.error("Project creation failed because the database was unavailable.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database temporarily unavailable.",
        )

    return ProjectResponse.from_model(created_project)

@app.get("/projects", response_model=list[ProjectResponse], tags=["projects"])
async def list_projects(db: Session = Depends(get_db)) -> list[ProjectResponse]:
    try:
        projects = db.scalars(
            select(Project).order_by(Project.created_at, Project.id)
        ).all()
    except SQLAlchemyError:
        logger.error("Project listing failed because the database was unavailable.")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database temporarily unavailable.",
        )

    return [ProjectResponse.from_model(project) for project in projects]
