import asyncio
from collections.abc import AsyncIterator, Generator
from uuid import uuid4

import httpx
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from database import Base, get_db
from main import MAX_REQUEST_BODY_BYTES, app
from models import User


TEST_ENGINE = create_engine(
    "sqlite+pysqlite:///:memory:",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(
    bind=TEST_ENGINE,
    autoflush=False,
    expire_on_commit=False,
)
TEST_OWNER_ID = ""


async def override_get_db() -> AsyncIterator[Session]:
    with TestingSessionLocal() as session:
        yield session


app.dependency_overrides[get_db] = override_get_db


@pytest.fixture(autouse=True)
def isolated_database() -> Generator[None, None, None]:
    global TEST_OWNER_ID

    Base.metadata.drop_all(TEST_ENGINE)
    Base.metadata.create_all(TEST_ENGINE)

    with TestingSessionLocal() as session:
        owner = User(external_ref="test-owner")
        session.add(owner)
        session.commit()
        TEST_OWNER_ID = str(owner.id)

    yield

    Base.metadata.drop_all(TEST_ENGINE)


def request(method: str, path: str, **kwargs: object) -> httpx.Response:
    """Send one request directly to the ASGI application."""

    async def send() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.request(method, path, **kwargs)

    return asyncio.run(send())


def test_health_reports_ok() -> None:
    response = request("GET", "/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_serves_operations_web_prototype() -> None:
    response = request("GET", "/")

    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "CCL AI Suite" in response.text
    assert "Controlled conversion" in response.text


def test_serves_web_prototype_assets() -> None:
    response = request("GET", "/static/app.js")

    assert response.status_code == 200
    assert "application/javascript" in response.headers["content-type"]
    assert "refreshHealth" in response.text


def test_create_then_list_projects() -> None:
    created = request(
        "POST",
        "/projects",
        json={
            "title": "First CCL Project",
            "description": "API test",
            "owner_id": TEST_OWNER_ID,
        },
    )
    listed = request("GET", "/projects")

    assert created.status_code == 201
    assert created.json()["title"] == "First CCL Project"
    assert created.json()["owner_id"] == TEST_OWNER_ID
    assert created.json()["status"] == "active"
    assert listed.status_code == 200
    assert len(listed.json()) == 1


def test_rejects_unknown_project_owner() -> None:
    response = request(
        "POST",
        "/projects",
        json={
            "title": "Unowned",
            "owner_id": str(uuid4()),
        },
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Project owner was not found."}


def test_requires_project_owner() -> None:
    response = request("POST", "/projects", json={"title": "Owner required"})

    assert response.status_code == 422


def test_rejects_malformed_project_data() -> None:
    response = request("POST", "/projects", content=b'{"title":')

    assert response.status_code == 422


def test_rejects_unknown_project_fields() -> None:
    response = request(
        "POST",
        "/projects",
        json={
            "title": "Valid",
            "owner_id": TEST_OWNER_ID,
            "owner": "unknown",
        },
    )

    assert response.status_code == 422


def test_rejects_oversized_request_body() -> None:
    response = request("POST", "/projects", content=b"x" * (MAX_REQUEST_BODY_BYTES + 1))

    assert response.status_code == 413
    assert response.json() == {"detail": "Request body is too large."}


def create_project() -> dict[str, object]:
    response = request(
        "POST",
        "/projects",
        json={"title": "Endpoint Project", "owner_id": TEST_OWNER_ID},
    )
    assert response.status_code == 201
    return response.json()


def create_workflow(project_id: str) -> dict[str, object]:
    response = request(
        "POST",
        f"/projects/{project_id}/workflows",
        json={"name": "Review", "created_by_id": TEST_OWNER_ID},
    )
    assert response.status_code == 201
    return response.json()


def test_provisions_development_user() -> None:
    response = request(
        "POST",
        "/users",
        json={"external_ref": "local-reviewer", "role": "reviewer"},
    )

    assert response.status_code == 201
    assert response.json()["external_ref"] == "local-reviewer"
    assert response.json()["role"] == "reviewer"


def test_gets_one_user_by_id() -> None:
    response = request("GET", f"/users/{TEST_OWNER_ID}")

    assert response.status_code == 200
    assert response.json()["id"] == TEST_OWNER_ID
    assert response.json()["external_ref"] == "test-owner"
    assert response.json()["role"] == "member"


def test_get_user_returns_not_found_for_unknown_id() -> None:
    response = request("GET", f"/users/{uuid4()}")

    assert response.status_code == 404
    assert response.json() == {"detail": "User was not found."}


def test_user_provisioning_is_disabled_outside_development(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("main.ENVIRONMENT", "production")

    response = request(
        "POST",
        "/users",
        json={"external_ref": "production-user"},
    )

    assert response.status_code == 403

    lookup_response = request("GET", f"/users/{TEST_OWNER_ID}")

    assert lookup_response.status_code == 403


def test_file_and_workflow_endpoints() -> None:
    project = create_project()
    project_id = str(project["id"])

    file_response = request(
        "POST",
        f"/projects/{project_id}/files",
        json={
            "storage_key": "projects/one/report.pdf",
            "media_type": "application/pdf",
            "size_bytes": 2048,
            "checksum_sha256": "A" * 64,
            "uploaded_by_id": TEST_OWNER_ID,
        },
    )
    listed_files = request("GET", f"/projects/{project_id}/files")

    assert file_response.status_code == 201
    assert file_response.json()["checksum_sha256"] == "a" * 64
    assert listed_files.status_code == 200
    assert len(listed_files.json()) == 1

    workflow = create_workflow(project_id)
    listed_workflows = request("GET", f"/projects/{project_id}/workflows")

    assert workflow["status"] == "draft"
    assert listed_workflows.status_code == 200
    assert len(listed_workflows.json()) == 1


def test_project_conversion_endpoint(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    projects_root = tmp_path / "projects"
    projects_root.mkdir()
    monkeypatch.setattr("main.PROJECT_ROOT", projects_root)

    project = create_project()
    project_root = projects_root / "endpoint-project"
    incoming = project_root / "incoming"
    incoming.mkdir(parents=True)
    (incoming / "records.csv").write_text("name,total\nalpha,3\n", encoding="utf-8")

    response = request(
        "POST",
        f"/projects/{project['id']}/conversions",
        json={
            "source_path": "incoming/records.csv",
            "destination_path": "output/records.json",
        },
    )

    assert response.status_code == 201
    assert response.json()["project_id"] == project["id"]
    assert response.json()["source_format"] == "csv"
    assert response.json()["destination_format"] == "json"
    assert (project_root / "output" / "records.json").is_file()


def test_project_conversion_endpoint_rejects_unsafe_path(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    projects_root = tmp_path / "projects"
    projects_root.mkdir()
    monkeypatch.setattr("main.PROJECT_ROOT", projects_root)
    project = create_project()
    project_root = projects_root / "endpoint-project"
    incoming = project_root / "incoming"
    incoming.mkdir(parents=True)
    (incoming / "records.csv").write_text("name\nalpha\n", encoding="utf-8")

    response = request(
        "POST",
        f"/projects/{project['id']}/conversions",
        json={
            "source_path": "../records.csv",
            "destination_path": "output/records.json",
        },
    )

    assert response.status_code == 400
    assert response.json() == {
        "detail": "Conversion paths must remain inside the approved project storage."
    }


def test_project_conversion_endpoint_returns_conflict_for_existing_destination(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    projects_root = tmp_path / "projects"
    projects_root.mkdir()
    monkeypatch.setattr("main.PROJECT_ROOT", projects_root)
    project = create_project()
    project_root = projects_root / "endpoint-project"
    incoming = project_root / "incoming"
    output = project_root / "output"
    incoming.mkdir(parents=True)
    output.mkdir()
    (incoming / "records.csv").write_text("name\nalpha\n", encoding="utf-8")
    (output / "records.json").write_text("keep", encoding="utf-8")

    response = request(
        "POST",
        f"/projects/{project['id']}/conversions",
        json={
            "source_path": "incoming/records.csv",
            "destination_path": "output/records.json",
        },
    )

    assert response.status_code == 409
    assert response.json() == {"detail": "Conversion destination already exists."}


def test_project_folder_generation_endpoint(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    projects_root = tmp_path / "projects"
    monkeypatch.setattr("main.PROJECT_ROOT", projects_root)

    response = request(
        "POST",
        "/project-folders",
        json={"project_name": "Browser Intake"},
    )

    assert response.status_code == 201
    assert response.json()["name"] == "browser-intake"
    assert response.json()["project_path"] == "browser-intake"
    assert (projects_root / "browser-intake" / "incoming").is_dir()
    assert (projects_root / "browser-intake" / "working").is_dir()


def test_project_inventory_endpoint_writes_manifests(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    projects_root = tmp_path / "projects"
    projects_root.mkdir()
    monkeypatch.setattr("main.PROJECT_ROOT", projects_root)
    project = create_project()
    project_root = projects_root / "endpoint-project"
    project_root.mkdir()
    (project_root / "incoming").mkdir()
    (project_root / "incoming" / "notes.txt").write_text("hello", encoding="utf-8")

    response = request("POST", f"/projects/{project['id']}/inventory")

    assert response.status_code == 201
    assert response.json()["files_scanned"] == 1
    assert response.json()["duplicate_groups"] == 0
    assert response.json()["json_manifest"] == "manifest.json"
    assert response.json()["csv_manifest"] == "manifest.csv"
    assert (project_root / "manifest.json").is_file()
    assert (project_root / "manifest.csv").is_file()


def test_project_organization_preview_apply_and_rollback(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    projects_root = tmp_path / "projects"
    projects_root.mkdir()
    monkeypatch.setattr("main.PROJECT_ROOT", projects_root)
    project = create_project()
    project_root = projects_root / "endpoint-project"
    incoming = project_root / "incoming"
    (project_root / "working").mkdir(parents=True)
    incoming.mkdir()
    source = incoming / "Quarterly Report.csv"
    source.write_text("name,total\nalpha,3\n", encoding="utf-8")

    preview = request("POST", f"/projects/{project['id']}/organization/plan")
    applied = request(
        "POST",
        f"/projects/{project['id']}/organization/apply",
        json={"quarantine_conflicts": False},
    )

    assert preview.status_code == 201
    assert preview.json()["actions"][0]["destination"] == (
        "working/spreadsheets/quarterly-report.csv"
    )
    assert applied.status_code == 201
    assert applied.json()["applied_count"] == 1
    assert (project_root / "working" / "spreadsheets" / "quarterly-report.csv").is_file()
    assert not source.exists()

    rollback = request(
        "POST",
        f"/projects/{project['id']}/organization/rollback",
        json={"journal_path": applied.json()["journal_path"]},
    )

    assert rollback.status_code == 200
    assert rollback.json()["restored_count"] == 1
    assert source.is_file()


def test_approval_can_be_decided_once() -> None:
    project = create_project()
    workflow = create_workflow(str(project["id"]))

    created = request(
        "POST",
        f"/workflows/{workflow['id']}/approvals",
        json={"requested_by_id": TEST_OWNER_ID},
    )
    decided = request(
        "POST",
        f"/approvals/{created.json()['id']}/decision",
        json={
            "status": "approved",
            "approved_by_id": TEST_OWNER_ID,
            "decision_code": "reviewed",
        },
    )
    repeated = request(
        "POST",
        f"/approvals/{created.json()['id']}/decision",
        json={"status": "rejected", "approved_by_id": TEST_OWNER_ID},
    )

    assert created.status_code == 201
    assert created.json()["status"] == "pending"
    assert decided.status_code == 200
    assert decided.json()["status"] == "approved"
    assert decided.json()["decision_code"] == "reviewed"
    assert repeated.status_code == 409


def test_security_events_are_structured_and_limited() -> None:
    created = request(
        "POST",
        "/security-events",
        json={
            "event_code": "project.created",
            "outcome": "success",
            "actor_id": TEST_OWNER_ID,
            "resource_type": "project",
            "resource_ref": "project-1",
            "request_ref": "request-1",
        },
    )
    listed = request("GET", "/security-events?limit=1")

    assert created.status_code == 201
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    assert listed.json()[0]["event_code"] == "project.created"
