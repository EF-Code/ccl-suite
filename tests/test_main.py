import asyncio
from collections.abc import AsyncIterator, Generator
from pathlib import Path
from uuid import uuid4

import httpx
import pytest
from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from database import Base, get_db
from file_converter import ConversionError
from main import (
    MAX_REQUEST_BODY_BYTES,
    app,
    list_records,
    persist_record,
    require_record,
)
from models import Project, User


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


def test_serves_stylesheet_asset() -> None:
    response = request("GET", "/static/styles.css")

    assert response.status_code == 200
    assert "text/css" in response.headers["content-type"]
    assert ".dashboard-grid" in response.text


def test_database_lookup_failure_is_translated_to_503() -> None:
    class BrokenSession:
        def get(self, model: object, record_id: object) -> object:
            raise SQLAlchemyError("database unavailable")

    with pytest.raises(HTTPException) as exc_info:
        require_record(BrokenSession(), User, uuid4(), "User missing")  # type: ignore[arg-type]

    assert exc_info.value.status_code == 503
    assert exc_info.value.detail == "Database temporarily unavailable."


def test_database_write_failures_are_translated_to_safe_errors() -> None:
    class BrokenSession:
        def __init__(self, error: Exception) -> None:
            self.error = error
            self.rolled_back = False

        def add(self, record: object) -> None:
            pass

        def commit(self) -> None:
            raise self.error

        def refresh(self, record: object) -> None:
            pass

        def rollback(self) -> None:
            self.rolled_back = True

    constraint_session = BrokenSession(
        IntegrityError("insert", {}, Exception("duplicate"))
    )
    with pytest.raises(HTTPException) as constraint_error:
        persist_record(constraint_session, User(external_ref="constraint"), "User")  # type: ignore[arg-type]
    assert constraint_error.value.status_code == 409
    assert constraint_session.rolled_back is True

    unavailable_session = BrokenSession(SQLAlchemyError("database down"))
    with pytest.raises(HTTPException) as unavailable_error:
        persist_record(unavailable_session, User(external_ref="unavailable"), "User")  # type: ignore[arg-type]
    assert unavailable_error.value.status_code == 503
    assert unavailable_error.value.detail == "Database temporarily unavailable."


def test_database_listing_failure_is_translated_to_503() -> None:
    class BrokenSession:
        def scalars(self, statement: object) -> object:
            raise SQLAlchemyError("database unavailable")

    with pytest.raises(HTTPException) as exc_info:
        list_records(BrokenSession(), object())  # type: ignore[arg-type]

    assert exc_info.value.status_code == 503


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


def test_rejects_invalid_content_length_header() -> None:
    response = request(
        "POST",
        "/projects",
        headers={"Content-Length": "not-a-number"},
        content=b"{}",
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "Invalid Content-Length header."}


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


def test_rejects_unknown_user_roles() -> None:
    response = request(
        "POST",
        "/users",
        json={"external_ref": "unsupported-role", "role": "operator"},
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "User role is not supported."}


def test_permission_matrix_endpoint_lists_roles() -> None:
    response = request("GET", "/permissions")

    assert response.status_code == 200
    assert set(response.json()["roles"]) == {
        "administrator",
        "supervisor",
        "staff",
        "intern",
    }


def test_upload_policy_endpoint_describes_allowlist() -> None:
    response = request("GET", "/upload-policy")

    assert response.status_code == 200
    assert response.json()["max_size_bytes"] == 1_048_576
    assert "text/plain" in response.json()["allowed_extensions"][".txt"]
    assert response.json()["filename_pattern"]


def test_gets_one_user_by_id() -> None:
    response = request("GET", f"/users/{TEST_OWNER_ID}")

    assert response.status_code == 200
    assert response.json()["id"] == TEST_OWNER_ID
    assert response.json()["external_ref"] == "test-owner"
    assert response.json()["role"] == "member"


def test_intern_can_read_but_cannot_create_projects() -> None:
    intern = request(
        "POST",
        "/users",
        json={"external_ref": "intern-user", "role": "intern"},
    )
    intern_id = intern.json()["id"]

    listed = request("GET", "/projects", headers={"X-User-ID": intern_id})
    denied = request(
        "POST",
        "/projects",
        headers={"X-User-ID": intern_id},
        json={"title": "Denied project", "owner_id": TEST_OWNER_ID},
    )
    events = request("GET", "/security-events")

    assert intern.status_code == 201
    assert listed.status_code == 200
    assert denied.status_code == 403
    assert any(event["event_code"] == "access.denied" for event in events.json())


def test_protected_routes_require_identity_outside_development(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr("main.ENVIRONMENT", "production")

    response = request("GET", "/projects")

    assert response.status_code == 401
    assert response.json() == {"detail": "An authenticated user is required."}


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


def test_file_endpoint_records_authenticated_uploader_when_omitted() -> None:
    project = create_project()

    response = request(
        "POST",
        f"/projects/{project['id']}/files",
        json={
            "storage_key": "projects/one/no-uploader.txt",
            "media_type": "text/plain",
            "size_bytes": 4,
            "checksum_sha256": "B" * 64,
        },
    )

    assert response.status_code == 201
    assert response.json()["uploaded_by_id"] == TEST_OWNER_ID


def test_mutating_actor_fields_cannot_be_spoofed() -> None:
    project = create_project()
    other_user = request(
        "POST",
        "/users",
        json={"external_ref": "other-actor", "role": "staff"},
    )
    assert other_user.status_code == 201
    other_id = other_user.json()["id"]
    other_headers = {"X-User-ID": other_id}

    file_response = request(
        "POST",
        f"/projects/{project['id']}/files",
        headers=other_headers,
        json={
            "storage_key": "incoming/spoofed.txt",
            "media_type": "text/plain",
            "size_bytes": 4,
            "checksum_sha256": "A" * 64,
            "uploaded_by_id": TEST_OWNER_ID,
        },
    )
    workflow_response = request(
        "POST",
        f"/projects/{project['id']}/workflows",
        headers=other_headers,
        json={"name": "Spoofed workflow", "created_by_id": TEST_OWNER_ID},
    )
    workflow = create_workflow(str(project["id"]))
    approval = request(
        "POST",
        f"/workflows/{workflow['id']}/approvals",
        json={},
    )
    decision_response = request(
        "POST",
        f"/approvals/{approval.json()['id']}/decision",
        headers=other_headers,
        json={"status": "approved", "approved_by_id": TEST_OWNER_ID},
    )
    event_response = request(
        "POST",
        "/security-events",
        headers=other_headers,
        json={
            "event_code": "spoofed.actor",
            "outcome": "success",
            "actor_id": TEST_OWNER_ID,
        },
    )

    assert file_response.status_code == 403
    assert workflow_response.status_code == 403
    assert decision_response.status_code == 403
    assert event_response.status_code == 403
    assert request("GET", "/security-events").json()[-1]["event_code"] == "access.denied"


def test_file_endpoint_rejects_storage_path_escape() -> None:
    project = create_project()

    response = request(
        "POST",
        f"/projects/{project['id']}/files",
        json={
            "storage_key": "../outside.txt",
            "media_type": "text/plain",
            "size_bytes": 4,
            "checksum_sha256": "B" * 64,
        },
    )

    assert response.status_code == 400
    assert response.json() == {
        "detail": "Storage key must remain inside the approved project root."
    }


def test_secure_upload_endpoint_indexes_file_and_logs_rejection(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    projects_root = tmp_path / "projects"
    projects_root.mkdir()
    monkeypatch.setattr("main.PROJECT_ROOT", projects_root)
    project = create_project()
    project_root = projects_root / "endpoint-project"
    project_root.mkdir()

    uploaded = request(
        "PUT",
        f"/projects/{project['id']}/uploads/incoming/notes.txt",
        content=b"hello",
        headers={"content-type": "text/plain"},
    )

    assert uploaded.status_code == 201
    assert uploaded.json()["storage_key"] == "incoming/notes.txt"
    assert uploaded.json()["size_bytes"] == 5
    assert (project_root / "incoming" / "notes.txt").read_bytes() == b"hello"
    search = request("GET", f"/projects/{project['id']}/files/search?query=notes")
    assert search.status_code == 200
    assert search.json()[0]["checksum_sha256"] == uploaded.json()["checksum_sha256"]
    assert search.json()[0]["uploaded_by_id"] == TEST_OWNER_ID

    conflict = request(
        "PUT",
        f"/projects/{project['id']}/uploads/incoming/notes.txt",
        content=b"replace",
        headers={"content-type": "text/plain"},
    )
    rejected = request(
        "PUT",
        f"/projects/{project['id']}/uploads/incoming/report.csv.exe",
        content=b"bad",
        headers={"content-type": "application/octet-stream"},
    )
    events = request("GET", "/security-events")

    assert conflict.status_code == 409
    assert rejected.status_code == 400
    assert events.status_code == 200
    assert {event["event_code"] for event in events.json()} == {"file.upload.rejected"}
    assert {event["actor_id"] for event in events.json()} == {TEST_OWNER_ID}
    events_payload = events.json()
    assert all(event["request_ref"] is None for event in events_payload)
    assert {
        event["resource_ref"]
        for event in events_payload
    } == {"incoming/notes.txt", "incoming/report.csv.exe"}


def test_project_backup_endpoint_creates_and_reverifies_archive(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    projects_root = tmp_path / "projects"
    backups_root = tmp_path / "backups"
    projects_root.mkdir()
    monkeypatch.setattr("main.PROJECT_ROOT", projects_root)
    monkeypatch.setattr("main.BACKUP_ROOT", backups_root)
    project = create_project()
    project_root = projects_root / "endpoint-project"
    project_root.mkdir()
    (project_root / "notes.txt").write_text("backup me", encoding="utf-8")

    response = request(
        "POST",
        f"/projects/{project['id']}/backups",
        json={},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["project_id"] == project["id"]
    assert payload["created_by_id"] == TEST_OWNER_ID
    assert payload["status"] == "verified"
    assert payload["file_count"] == 1
    assert (backups_root / payload["artifact_key"]).is_file()
    assert (backups_root / payload["manifest_key"]).is_file()


def test_secure_upload_rejects_oversized_body(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    projects_root = tmp_path / "projects"
    projects_root.mkdir()
    monkeypatch.setattr("main.PROJECT_ROOT", projects_root)
    project = create_project()
    (projects_root / "endpoint-project").mkdir()

    response = request(
        "PUT",
        f"/projects/{project['id']}/uploads/incoming/large.txt",
        content=b"x" * (MAX_REQUEST_BODY_BYTES + 1),
        headers={"content-type": "text/plain"},
    )

    assert response.status_code == 413
    assert not (projects_root / "endpoint-project" / "incoming" / "large.txt").exists()


def test_secure_upload_cleans_file_when_metadata_save_fails(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    projects_root = tmp_path / "projects"
    projects_root.mkdir()
    monkeypatch.setattr("main.PROJECT_ROOT", projects_root)
    project = create_project()
    project_root = projects_root / "endpoint-project"
    project_root.mkdir()

    def fail_sync(*args: object, **kwargs: object) -> object:
        raise SQLAlchemyError("database unavailable")

    monkeypatch.setattr("main.sync_inventory_records", fail_sync)
    response = request(
        "PUT",
        f"/projects/{project['id']}/uploads/incoming/notes.txt",
        content=b"hello",
        headers={"content-type": "text/plain"},
    )

    assert response.status_code == 503
    assert not (project_root / "incoming" / "notes.txt").exists()


def test_secure_upload_rejects_path_traversal_and_missing_mime(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    projects_root = tmp_path / "projects"
    projects_root.mkdir()
    monkeypatch.setattr("main.PROJECT_ROOT", projects_root)
    project = create_project()
    project_root = projects_root / "endpoint-project"
    project_root.mkdir()

    traversal = request(
        "PUT",
        f"/projects/{project['id']}/uploads/%2E%2E%2Foutside.txt",
        content=b"blocked",
        headers={"content-type": "text/plain"},
    )
    missing_mime = request(
        "PUT",
        f"/projects/{project['id']}/uploads/incoming/notes.txt",
        content=b"blocked",
    )

    assert traversal.status_code == 400
    assert missing_mime.status_code == 400
    assert not (tmp_path / "outside.txt").exists()
    assert not (project_root / "incoming" / "notes.txt").exists()


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


def test_project_conversion_endpoint_maps_missing_and_unsupported_inputs(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    projects_root = tmp_path / "projects"
    monkeypatch.setattr("main.PROJECT_ROOT", projects_root)
    project = create_project()
    project_root = projects_root / "endpoint-project"
    incoming = project_root / "incoming"
    incoming.mkdir(parents=True)
    (incoming / "records.csv").write_text("name\nalpha\n", encoding="utf-8")

    missing = request(
        "POST",
        f"/projects/{project['id']}/conversions",
        json={
            "source_path": "incoming/missing.csv",
            "destination_path": "output/missing.json",
        },
    )
    unsupported = request(
        "POST",
        f"/projects/{project['id']}/conversions",
        json={
            "source_path": "incoming/records.csv",
            "destination_path": "output/records.txt",
        },
    )

    assert missing.status_code == 404
    assert missing.json() == {"detail": "Conversion source or project storage was not found."}
    assert unsupported.status_code == 415


@pytest.mark.parametrize(
    ("error", "expected_status", "detail"),
    [
        (ConversionError("invalid content"), 422, "File conversion failed validation."),
        (ValueError("bad path"), 400, "Conversion paths must remain inside the approved project storage."),
        (PermissionError("locked"), 403, "Project storage is not available for conversion."),
    ],
)
def test_project_conversion_endpoint_maps_conversion_failures(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    error: Exception,
    expected_status: int,
    detail: str,
) -> None:
    projects_root = tmp_path / "projects"
    monkeypatch.setattr("main.PROJECT_ROOT", projects_root)
    project = create_project()
    project_root = projects_root / "endpoint-project"
    (project_root / "incoming").mkdir(parents=True)

    def fail(*args: object, **kwargs: object) -> object:
        raise error

    monkeypatch.setattr("main.convert_file", fail)
    response = request(
        "POST",
        f"/projects/{project['id']}/conversions",
        json={
            "source_path": "incoming/records.csv",
            "destination_path": "output/records.json",
        },
    )

    assert response.status_code == expected_status
    assert response.json() == {"detail": detail}


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


def test_project_folder_generation_returns_conflict_on_duplicate(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    projects_root = tmp_path / "projects"
    monkeypatch.setattr("main.PROJECT_ROOT", projects_root)

    first = request("POST", "/project-folders", json={"project_name": "Duplicate"})
    second = request("POST", "/project-folders", json={"project_name": "Duplicate"})

    assert first.status_code == 201
    assert second.status_code == 409
    assert second.json() == {"detail": "Project folder already exists."}


@pytest.mark.parametrize(
    ("error", "expected_status", "detail"),
    [
        (PermissionError("permission"), 403, "The configured projects root is not available for writing."),
        (ValueError("invalid"), 400, "invalid"),
        (OSError("write failed"), 422, "Project folder could not be created."),
    ],
)
def test_project_folder_generation_maps_creation_failures(
    monkeypatch: pytest.MonkeyPatch,
    error: Exception,
    expected_status: int,
    detail: str,
) -> None:
    def fail(*args: object, **kwargs: object) -> object:
        raise error

    monkeypatch.setattr("main.create_project_folder", fail)

    response = request("POST", "/project-folders", json={"project_name": "Failure"})

    assert response.status_code == expected_status
    assert response.json() == {"detail": detail}


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
    assert response.json()["versions_created"] == 1
    assert response.json()["json_manifest"] == "manifest.json"
    assert response.json()["csv_manifest"] == "manifest.csv"
    assert (project_root / "manifest.json").is_file()
    assert (project_root / "manifest.csv").is_file()

    search = request(
        "GET",
        f"/projects/{project['id']}/files/search?query=notes&status=active",
    )
    assert search.status_code == 200
    assert len(search.json()) == 1
    assert search.json()[0]["name"] == "notes.txt"
    assert search.json()[0]["status"] == "active"

    history = request(
        "GET",
        f"/projects/{project['id']}/files/{search.json()[0]['id']}/history",
    )
    assert history.status_code == 200
    assert [entry["event_code"] for entry in history.json()] == ["created"]

    versions = request(
        "GET",
        f"/projects/{project['id']}/files/{search.json()[0]['id']}/versions",
    )
    assert versions.status_code == 200
    assert len(versions.json()) == 1
    assert versions.json()[0]["version_number"] == 1
    assert versions.json()[0]["is_original"] is True


def test_project_inventory_endpoint_updates_file_history(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    projects_root = tmp_path / "projects"
    projects_root.mkdir()
    monkeypatch.setattr("main.PROJECT_ROOT", projects_root)
    project = create_project()
    project_root = projects_root / "endpoint-project"
    project_root.mkdir()
    (project_root / "incoming").mkdir()
    source = project_root / "incoming" / "notes.txt"
    source.write_text("first", encoding="utf-8")

    first = request("POST", f"/projects/{project['id']}/inventory")
    assert first.status_code == 201
    source.write_text("second", encoding="utf-8")
    second = request("POST", f"/projects/{project['id']}/inventory")

    assert second.status_code == 201
    assert second.json()["history_events"] == 1
    assert second.json()["versions_created"] == 1
    file_id = request(
        "GET", f"/projects/{project['id']}/files/search?query=notes"
    ).json()[0]["id"]
    history = request(
        "GET", f"/projects/{project['id']}/files/{file_id}/history"
    )
    assert [entry["event_code"] for entry in history.json()] == ["created", "updated"]
    versions = request(
        "GET", f"/projects/{project['id']}/files/{file_id}/versions"
    )
    assert versions.status_code == 200
    assert [entry["version_number"] for entry in versions.json()] == [1, 2]
    assert [entry["is_original"] for entry in versions.json()] == [True, False]
    assert versions.json()[0]["checksum_sha256"] != versions.json()[1]["checksum_sha256"]


def test_project_file_version_restore_endpoint_preserves_original(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    projects_root = tmp_path / "projects"
    projects_root.mkdir()
    monkeypatch.setattr("main.PROJECT_ROOT", projects_root)
    project = create_project()
    project_root = projects_root / "endpoint-project"
    project_root.mkdir()
    (project_root / "incoming").mkdir()
    source = project_root / "incoming" / "notes.txt"
    source.write_text("first", encoding="utf-8")

    first = request("POST", f"/projects/{project['id']}/inventory")
    assert first.status_code == 201
    source.write_text("second", encoding="utf-8")
    second = request("POST", f"/projects/{project['id']}/inventory")
    assert second.status_code == 201

    file_id = request(
        "GET", f"/projects/{project['id']}/files/search?query=notes"
    ).json()[0]["id"]
    restored = request(
        "POST",
        f"/projects/{project['id']}/files/{file_id}/versions/1/restore",
        json={"destination_path": "output/notes-v1.txt"},
    )

    assert restored.status_code == 201
    assert restored.json()["version_number"] == 1
    assert restored.json()["destination_path"] == "output/notes-v1.txt"
    assert restored.json()["bytes_restored"] == len("first")
    assert (project_root / "output" / "notes-v1.txt").read_text(encoding="utf-8") == "first"
    assert source.read_text(encoding="utf-8") == "second"

    conflict = request(
        "POST",
        f"/projects/{project['id']}/files/{file_id}/versions/1/restore",
        json={"destination_path": "output/notes-v1.txt"},
    )
    original = request(
        "POST",
        f"/projects/{project['id']}/files/{file_id}/versions/1/restore",
        json={"destination_path": "incoming/notes.txt"},
    )
    assert conflict.status_code == 409
    assert original.status_code == 400
    assert source.read_text(encoding="utf-8") == "second"


def test_project_file_search_rejects_unknown_status() -> None:
    project = create_project()

    response = request(
        "GET", f"/projects/{project['id']}/files/search?status=unknown"
    )

    assert response.status_code == 400
    assert response.json() == {"detail": "Unsupported file status."}


def test_project_file_lookup_is_project_scoped(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    projects_root = tmp_path / "projects"
    projects_root.mkdir()
    monkeypatch.setattr("main.PROJECT_ROOT", projects_root)
    project = create_project()
    project_root = projects_root / "endpoint-project"
    project_root.mkdir()
    (project_root / "incoming").mkdir()
    (project_root / "incoming" / "notes.txt").write_text("hello", encoding="utf-8")

    inventory = request("POST", f"/projects/{project['id']}/inventory")
    record_sha256 = inventory.json()["records"][0]["sha256"]
    search = request("GET", f"/projects/{project['id']}/files/search?query=notes")
    stored_file_id = search.json()[0]["id"]

    found = request("GET", f"/projects/{project['id']}/files/{stored_file_id}")
    other_project = create_project()
    hidden = request(
        "GET", f"/projects/{other_project['id']}/files/{stored_file_id}"
    )

    assert found.status_code == 200
    assert found.json()["id"] == stored_file_id
    assert record_sha256 == found.json()["checksum_sha256"]
    assert hidden.status_code == 404


def test_project_file_lookup_returns_not_found_for_unknown_file() -> None:
    project = create_project()

    response = request("GET", f"/projects/{project['id']}/files/{uuid4()}")

    assert response.status_code == 404
    assert response.json() == {"detail": "File was not found."}


def test_project_file_search_supports_checksum_type_and_pagination() -> None:
    project = create_project()
    checksums = ["1" * 64, "2" * 64, "3" * 64]
    for index, checksum in enumerate(checksums):
        created = request(
            "POST",
            f"/projects/{project['id']}/files",
            json={
                "storage_key": f"incoming/report-{index}.txt",
                "media_type": "text/plain",
                "size_bytes": index + 1,
                "checksum_sha256": checksum,
            },
        )
        assert created.status_code == 201

    checksum_search = request(
        "GET",
        f"/projects/{project['id']}/files/search?checksum_sha256={checksums[1].upper()}",
    )
    type_search = request(
        "GET",
        f"/projects/{project['id']}/files/search?media_type=text/plain&limit=2&offset=1",
    )
    invalid_checksum = request(
        "GET", f"/projects/{project['id']}/files/search?checksum_sha256=invalid"
    )

    assert checksum_search.status_code == 200
    assert len(checksum_search.json()) == 1
    assert checksum_search.json()[0]["checksum_sha256"] == checksums[1]
    assert type_search.status_code == 200
    assert len(type_search.json()) == 2
    assert invalid_checksum.status_code == 422


def test_project_file_history_is_project_scoped(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    projects_root = tmp_path / "projects"
    projects_root.mkdir()
    monkeypatch.setattr("main.PROJECT_ROOT", projects_root)
    project = create_project()
    project_root = projects_root / "endpoint-project"
    project_root.mkdir()
    (project_root / "incoming").mkdir()
    (project_root / "incoming" / "notes.txt").write_text("hello", encoding="utf-8")
    inventory = request("POST", f"/projects/{project['id']}/inventory")
    file_id = request(
        "GET", f"/projects/{project['id']}/files/search?query=notes"
    ).json()[0]["id"]
    other_project = create_project()

    history = request(
        "GET", f"/projects/{other_project['id']}/files/{file_id}/history"
    )

    assert inventory.status_code == 201
    assert history.status_code == 404


def test_project_inventory_endpoint_returns_not_found_without_storage(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    monkeypatch.setattr("main.PROJECT_ROOT", tmp_path / "projects")
    project = create_project()

    response = request("POST", f"/projects/{project['id']}/inventory")

    assert response.status_code == 404
    assert response.json() == {"detail": "Project storage was not found."}


@pytest.mark.parametrize(
    ("error", "expected_status", "detail"),
    [
        (PermissionError("locked"), 403, "Project storage is not available for scanning."),
        (ValueError("manifest path"), 422, "Project inventory could not be created."),
        (OSError("scan failed"), 422, "Project inventory could not be created."),
    ],
)
def test_project_inventory_endpoint_maps_scan_failures(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    error: Exception,
    expected_status: int,
    detail: str,
) -> None:
    project = create_project()

    monkeypatch.setattr("main.project_storage_root", lambda project: tmp_path)

    def fail(*args: object, **kwargs: object) -> object:
        raise error

    monkeypatch.setattr("main.scan_files", fail)
    response = request("POST", f"/projects/{project['id']}/inventory")

    assert response.status_code == expected_status
    assert response.json() == {"detail": detail}


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


def test_project_organization_preview_returns_not_found_without_storage(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    monkeypatch.setattr("main.PROJECT_ROOT", tmp_path / "projects")
    project = create_project()

    response = request("POST", f"/projects/{project['id']}/organization/plan")

    assert response.status_code == 404
    assert response.json() == {"detail": "Project incoming directory was not found."}


def test_project_organization_apply_returns_not_found_without_storage(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    monkeypatch.setattr("main.PROJECT_ROOT", tmp_path / "projects")
    project = create_project()

    response = request(
        "POST",
        f"/projects/{project['id']}/organization/apply",
        json={"quarantine_conflicts": False},
    )

    assert response.status_code == 404
    assert response.json() == {"detail": "Project incoming directory was not found."}


def test_project_organization_apply_can_quarantine_conflicts(
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
    (incoming / "Plan.csv").write_text("first", encoding="utf-8")
    (incoming / "plan.csv").write_text("second", encoding="utf-8")

    response = request(
        "POST",
        f"/projects/{project['id']}/organization/apply",
        json={"quarantine_conflicts": True},
    )

    assert response.status_code == 201
    assert response.json()["conflict_count"] == 1
    assert response.json()["quarantine_journal_path"] is not None


@pytest.mark.parametrize(
    ("error", "expected_status", "detail"),
    [
        (PermissionError("locked"), 403, "Project storage is not available for organising."),
        (ValueError("unsafe"), 400, "unsafe"),
        (OSError("planning failed"), 422, "Organisation plan could not be created."),
    ],
)
def test_project_organization_preview_maps_planning_failures(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    error: Exception,
    expected_status: int,
    detail: str,
) -> None:
    project = create_project()
    monkeypatch.setattr("main.project_storage_root", lambda project: tmp_path)

    def fail(*args: object, **kwargs: object) -> object:
        raise error

    monkeypatch.setattr("main.build_plan", fail)
    response = request("POST", f"/projects/{project['id']}/organization/plan")

    assert response.status_code == expected_status
    assert response.json() == {"detail": detail}


@pytest.mark.parametrize(
    ("error", "expected_status", "detail"),
    [
        (PermissionError("locked"), 403, "Project storage is not available for organising."),
        (FileExistsError("collision"), 409, "collision"),
        (OSError("apply failed"), 422, "Organisation could not be applied safely."),
    ],
)
def test_project_organization_apply_maps_apply_failures(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    error: Exception,
    expected_status: int,
    detail: str,
) -> None:
    project = create_project()
    project_root = tmp_path / "endpoint-project"
    (project_root / "incoming").mkdir(parents=True)
    (project_root / "working").mkdir()
    monkeypatch.setattr("main.project_storage_root", lambda project: project_root)

    def fail(*args: object, **kwargs: object) -> object:
        raise error

    monkeypatch.setattr("main.apply_plan", fail)
    response = request(
        "POST",
        f"/projects/{project['id']}/organization/apply",
        json={"quarantine_conflicts": False},
    )

    assert response.status_code == expected_status
    assert response.json() == {"detail": detail}


def test_project_organization_rollback_maps_missing_and_unsafe_journals(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    monkeypatch.setattr("main.PROJECT_ROOT", tmp_path / "projects")
    project = create_project()
    project_root = tmp_path / "projects" / "endpoint-project"
    (project_root / "incoming").mkdir(parents=True)
    (project_root / "working").mkdir()

    missing = request(
        "POST",
        f"/projects/{project['id']}/organization/rollback",
        json={"journal_path": "missing.json"},
    )
    unsafe = request(
        "POST",
        f"/projects/{project['id']}/organization/rollback",
        json={"journal_path": "../outside.json"},
    )

    assert missing.status_code == 404
    assert unsafe.status_code == 409


def test_project_organization_rollback_rejects_symlink_journal(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    monkeypatch.setattr("main.PROJECT_ROOT", tmp_path / "projects")
    project = create_project()
    project_root = tmp_path / "projects" / "endpoint-project"
    (project_root / "incoming").mkdir(parents=True)
    (project_root / "working").mkdir()
    target = project_root / "journal.json"
    target.write_text("{}", encoding="utf-8")
    (project_root / "journal-link.json").symlink_to(target)

    response = request(
        "POST",
        f"/projects/{project['id']}/organization/rollback",
        json={"journal_path": "journal-link.json"},
    )

    assert response.status_code == 409


@pytest.mark.parametrize(
    ("error", "expected_status", "detail"),
    [
        (PermissionError("locked"), 403, "Project storage is not available for rollback."),
        (FileExistsError("source exists"), 409, "Rollback would overwrite an existing source file."),
        (OSError("rollback failed"), 422, "Organisation rollback could not be completed."),
    ],
)
def test_project_organization_rollback_maps_rollback_failures(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    error: Exception,
    expected_status: int,
    detail: str,
) -> None:
    project = create_project()
    project_root = tmp_path / "endpoint-project"
    (project_root / "incoming").mkdir(parents=True)
    (project_root / "working").mkdir()
    monkeypatch.setattr("main.project_storage_root", lambda project: project_root)

    def fail(*args: object, **kwargs: object) -> int:
        raise error

    monkeypatch.setattr("main.rollback_journal", fail)
    response = request(
        "POST",
        f"/projects/{project['id']}/organization/rollback",
        json={"journal_path": "journal.json"},
    )

    assert response.status_code == expected_status
    assert response.json() == {"detail": detail}


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


def test_workflow_and_approval_endpoints_bind_optional_actor_ids() -> None:
    project = create_project()
    workflow = request(
        "POST",
        f"/projects/{project['id']}/workflows",
        json={"name": "Optional actors"},
    )
    approval = request(
        "POST",
        f"/workflows/{workflow.json()['id']}/approvals",
        json={},
    )
    listed = request("GET", f"/workflows/{workflow.json()['id']}/approvals")

    assert workflow.status_code == 201
    assert workflow.json()["created_by_id"] == TEST_OWNER_ID
    assert approval.status_code == 201
    assert approval.json()["requested_by_id"] == TEST_OWNER_ID
    assert listed.status_code == 200
    assert len(listed.json()) == 1


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


def test_security_event_can_omit_actor() -> None:
    response = request(
        "POST",
        "/security-events",
        json={"event_code": "system.started", "outcome": "success"},
    )

    assert response.status_code == 201
    assert response.json()["actor_id"] == TEST_OWNER_ID
