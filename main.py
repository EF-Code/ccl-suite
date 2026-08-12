from uuid import uuid4

from fastapi import Depends, FastAPI, HTTPException, Request, status
from pydantic import BaseModel, ConfigDict, Field

MAX_REQUEST_BODY_BYTES = 1_048_576

app = FastAPI(title="CCL AI Suite", version="0.1.0")

projects: list[dict[str, str]] = []


class ProjectCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    title: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=500)


class ProjectResponse(ProjectCreate):
    id: str


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
async def create_project(project: ProjectCreate) -> ProjectResponse:
    created_project = {
        "id": str(uuid4()),
        "title": project.title.strip(),
        "description": project.description.strip(),
    }
    if not created_project["title"]:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="title cannot be blank",
        )

    projects.append(created_project)
    return ProjectResponse(**created_project)

@app.get("/projects", response_model=list[ProjectResponse], tags=["projects"])
async def list_projects() -> list[ProjectResponse]:
    return [ProjectResponse(**project) for project in projects]
