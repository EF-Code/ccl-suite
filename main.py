from uuid import uuid4

from fastapi import FastAPI, HTTPException, status
from pydantic import BaseModel, Field

app = FastAPI (
        title="CCL AI Suite",
        version="0.1.0",
        )

projects: list[dict[str, str]] = []


class ProjectCreate(BaseModel):
    title: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=500)


class ProjectResponse(ProjectCreate):
    id:str


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}

@app.post("/projects", status_code=status.HTTP_201_CREATED)
def create_project(project: ProjectCreate) -> ProjectResponse:
    created_project = {
            "id": str(uuid4()),
            "title": project.title.strip(),
            "description": project.description.strip(),
            }
    if not created_project["title"]:
        raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail="title cannot be blank"
            )
        
        projects.append(created_project)
        return ProjectResponse(**created_project)

@app.get("/projects")
def list_projects() -> list[ProjectResponse]:
    return [ProjectResponse(**project) for project in projects]

        

