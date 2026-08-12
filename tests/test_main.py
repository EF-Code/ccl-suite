import asyncio

import httpx

from main import MAX_REQUEST_BODY_BYTES, app, projects


def request(method: str, path: str, **kwargs: object) -> httpx.Response:
    """Send one request directly to the ASGI application."""

    async def send() -> httpx.Response:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            return await client.request(method, path, **kwargs)

    return asyncio.run(send())


def setup_function() -> None:
    projects.clear()


def test_health_reports_ok() -> None:
    response = request("GET", "/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_create_then_list_projects() -> None:
    created = request(
        "POST",
        "/projects",
        json={"title": "First CCL Project", "description": "API test"},
    )
    listed = request("GET", "/projects")

    assert created.status_code == 201
    assert created.json()["title"] == "First CCL Project"
    assert listed.status_code == 200
    assert len(listed.json()) == 1


def test_rejects_malformed_project_data() -> None:
    response = request("POST", "/projects", content=b'{"title":')

    assert response.status_code == 422


def test_rejects_unknown_project_fields() -> None:
    response = request("POST", "/projects", json={"title": "Valid", "owner": "unknown"})

    assert response.status_code == 422


def test_rejects_oversized_request_body() -> None:
    response = request("POST", "/projects", content=b"x" * (MAX_REQUEST_BODY_BYTES + 1))

    assert response.status_code == 413
    assert response.json() == {"detail": "Request body is too large."}
