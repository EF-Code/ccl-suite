"""Opt-in Playwright smoke tests for the local operations dashboard.

These tests intentionally run against a live API process.  Set
``RUN_BROWSER_TESTS=1`` and optionally ``DASHBOARD_BASE_URL`` before running
them.  The API should use an isolated development database and project root.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path
from uuid import uuid4

import pytest


pytestmark = pytest.mark.browser

if os.getenv("RUN_BROWSER_TESTS") != "1":
    pytest.skip(
        "Set RUN_BROWSER_TESTS=1 to run the live dashboard workflow.",
        allow_module_level=True,
    )

playwright = pytest.importorskip("playwright.sync_api")
from playwright.sync_api import Page, expect, sync_playwright


BASE_URL = os.getenv("DASHBOARD_BASE_URL", "http://127.0.0.1:8000").rstrip("/")


def installed_browser(playwright_api: object) -> str | None:
    """Choose the Playwright browser when present, then a system Chromium."""

    system_browser = shutil.which("google-chrome") or shutil.which("chromium")
    if system_browser:
        return system_browser
    expected = Path(playwright_api.chromium.executable_path)  # type: ignore[attr-defined]
    if expected.is_file():
        return expected.as_posix()
    return None


def confirm_protected_action(page: Page) -> None:
    """Confirm the dashboard's explicit guardrail for protected actions."""

    page.locator("#confirm-dialog").wait_for(state="visible")
    page.locator("#confirm-accept").click()


def open_workspace(page: Page, label: str) -> None:
    """Open one desktop workspace from the persistent product navigation."""

    page.locator(".app-sidebar").get_by_role(
        "button", name=label, exact=True
    ).click()


@pytest.fixture
def dashboard_page() -> Page:
    """Open one isolated browser page and close it after the workflow."""

    with sync_playwright() as playwright_api:
        executable = installed_browser(playwright_api)
        if executable is None:
            pytest.skip("No Chromium-compatible executable is installed.")
        browser = playwright_api.chromium.launch(
            headless=True,
            executable_path=executable,
        )
        page = browser.new_page()
        page.set_default_timeout(10_000)
        browser_errors: list[str] = []
        page.on(
            "console",
            lambda message: browser_errors.append(message.text)
            if message.type == "error"
            else None,
        )
        page.on("pageerror", lambda error: browser_errors.append(str(error)))
        try:
            yield page
        finally:
            browser.close()
        assert browser_errors == []


def test_dashboard_runs_project_file_workflow(dashboard_page: Page) -> None:
    """Exercise the dashboard from health check through rollback."""

    page = dashboard_page
    page.goto(BASE_URL, wait_until="networkidle")

    assert page.title() == "CCL AI Suite | Operations"
    expect(page.locator("#health-badge")).to_have_text("API online")
    expect(page.locator("#health-text")).to_have_text("Service is ready")
    open_workspace(page, "Setup")

    suffix = uuid4().hex[:10]
    owner_ref = f"browser-owner-{suffix}"
    project_title = f"Browser Workflow {suffix}"

    user_form = page.locator("#user-form")
    user_form.locator("input[name='external_ref']").fill(owner_ref)
    user_form.get_by_role("button", name="Create development owner").click()
    page.locator("#user-result").wait_for(state="visible")
    owner_id = page.locator("#owner-id").input_value()
    assert owner_id
    assert owner_ref in page.locator("#user-result").inner_text()

    project_form = page.locator("#project-form")
    project_form.locator("input[name='title']").fill(project_title)
    project_form.locator("textarea[name='description']").fill(
        "Browser workflow smoke test"
    )
    assert project_form.locator("input[name='owner_id']").input_value() == owner_id
    project_form.get_by_role("button", name="Register project").click()

    project_row = page.locator(".projects-table tbody tr").filter(has_text=project_title)
    project_row.wait_for(state="visible")
    project_button = project_row.get_by_role("button", name="Use project")
    project_id = project_button.get_attribute("data-project-id")
    project_button.click()
    assert project_id
    expect(page.locator("#active-project-title")).to_have_text(project_title)
    expect(page.locator("#active-project-status")).to_have_text("Ready to operate")

    folder_form = page.locator("#folder-form")
    expected_slug = project_title.lower().replace(" ", "-")
    assert folder_form.locator("input[name='project_name']").input_value() == expected_slug
    folder_form.get_by_role("button", name="Generate folder layout").click()
    folder_result = page.locator("#folder-result")
    folder_result.wait_for(state="visible")
    assert f"Created {expected_slug}" in folder_result.inner_text()

    open_workspace(page, "Operations")
    page.get_by_role("tab", name="Inventory").click()
    assert page.locator("#inventory-project-id").input_value() == project_id
    inventory_form = page.locator("#inventory-form")
    inventory_form.get_by_role("button", name="Scan project files").click()
    inventory_result = page.locator("#inventory-result")
    inventory_result.wait_for(state="visible")
    expect(inventory_result).to_contain_text("Scanned 0 file(s)")
    expect(inventory_result).to_contain_text("JSON: manifest.json")

    open_workspace(page, "Recovery")
    page.locator("#backup-create").click()
    backup_result = page.locator("#backup-result")
    backup_result.wait_for(state="visible")
    expect(backup_result).to_contain_text("Backup created and verified")
    backup_id = page.locator("#backup-id").input_value()
    assert backup_id

    page.locator("#backup-verify").click()
    expect(backup_result).to_contain_text("Integrity verified")

    restore_destination = f"restored/browser-{suffix}"
    page.locator("#backup-destination").fill(restore_destination)
    page.locator("#backup-restore").click()
    confirm_protected_action(page)
    expect(backup_result).to_contain_text("Restored")
    expect(backup_result).to_contain_text(restore_destination)

    open_workspace(page, "Operations")
    page.get_by_role("tab", name="Organize").click()
    assert page.locator("#organizer-project-id").input_value() == project_id
    page.locator("#organizer-preview").click()
    organizer_result = page.locator("#organizer-result")
    organizer_result.wait_for(state="visible")
    expect(organizer_result).to_contain_text("No files are waiting in incoming/.")

    page.locator("#organizer-apply").click()
    confirm_protected_action(page)
    expect(organizer_result).to_contain_text("Applied 0 of 0 action(s)")
    expect(organizer_result).to_contain_text("Journal: organization-journal.json")

    page.locator("#organizer-rollback").click()
    confirm_protected_action(page)
    expect(organizer_result).to_contain_text("Restored 0 file(s)")


def test_dashboard_registers_a_pending_knowledge_source(dashboard_page: Page) -> None:
    """Exercise the source-register workflow through the live dashboard."""

    page = dashboard_page
    page.goto(BASE_URL, wait_until="networkidle")
    open_workspace(page, "Setup")

    suffix = uuid4().hex[:10]
    owner_ref = f"knowledge-browser-owner-{suffix}"
    project_title = f"Knowledge Browser {suffix}"

    user_form = page.locator("#user-form")
    user_form.locator("input[name='external_ref']").fill(owner_ref)
    user_form.get_by_role("button", name="Create development owner").click()
    page.locator("#user-result").wait_for(state="visible")
    owner_id = page.locator("#owner-id").input_value()

    project_form = page.locator("#project-form")
    project_form.locator("input[name='title']").fill(project_title)
    project_form.get_by_role("button", name="Register project").click()
    project_row = page.locator(".projects-table tbody tr").filter(has_text=project_title)
    project_row.wait_for(state="visible")
    project_row.get_by_role("button", name="Use project").click()
    project_id = page.locator("#knowledge-project-id").input_value()

    folder_form = page.locator("#folder-form")
    folder_form.get_by_role("button", name="Generate folder layout").click()
    page.locator("#folder-result").wait_for(state="visible")

    file_response = page.request.post(
        f"{BASE_URL}/projects/{project_id}/files",
        data={
            "storage_key": "incoming/company-rules.txt",
            "media_type": "text/plain",
            "size_bytes": 42,
            "checksum_sha256": "b" * 64,
        },
    )
    assert file_response.status == 201
    file_id = file_response.json()["id"]

    open_workspace(page, "Knowledge")
    page.locator("#knowledge-files-refresh").click()
    page.locator(f"#knowledge-file-id option[value='{file_id}']").wait_for(state="attached")
    page.locator("#knowledge-file-id").select_option(file_id)
    expect(page.locator("#knowledge-register")).to_be_enabled()
    assert page.locator("#knowledge-owner-id").input_value() == owner_id

    page.locator("#knowledge-source-form input[name='title']").fill("Company rules")
    page.locator("#knowledge-source-form").get_by_role(
        "button", name="Register source for review"
    ).click()
    knowledge_result = page.locator("#knowledge-result")
    knowledge_result.wait_for(state="visible")
    expect(knowledge_result).to_contain_text("Status: pending")
    expect(page.locator(".knowledge-table tbody tr")).to_contain_text("Company rules")
    expect(page.locator(".knowledge-table tbody tr")).to_contain_text("pending")


def test_dashboard_answers_from_cited_knowledge(dashboard_page: Page) -> None:
    """Exercise the grounded-answer UI with an approved, ingested source."""

    page = dashboard_page
    page.goto(BASE_URL, wait_until="networkidle")
    open_workspace(page, "Setup")

    suffix = uuid4().hex[:10]
    owner_ref = f"answer-browser-owner-{suffix}"
    project_title = f"Answer Browser {suffix}"

    user_form = page.locator("#user-form")
    user_form.locator("input[name='external_ref']").fill(owner_ref)
    user_form.get_by_role("button", name="Create development owner").click()
    page.locator("#user-result").wait_for(state="visible")
    owner_id = page.locator("#owner-id").input_value()

    project_form = page.locator("#project-form")
    project_form.locator("input[name='title']").fill(project_title)
    project_form.get_by_role("button", name="Register project").click()
    project_row = page.locator(".projects-table tbody tr").filter(has_text=project_title)
    project_row.wait_for(state="visible")
    project_row.get_by_role("button", name="Use project").click()
    project_id = page.locator("#knowledge-project-id").input_value()

    folder_form = page.locator("#folder-form")
    folder_form.get_by_role("button", name="Generate folder layout").click()
    page.locator("#folder-result").wait_for(state="visible")

    supervisor_response = page.request.post(
        f"{BASE_URL}/users",
        data={"external_ref": f"answer-browser-supervisor-{suffix}", "role": "supervisor"},
    )
    assert supervisor_response.status == 201
    supervisor_id = supervisor_response.json()["id"]
    upload_response = page.request.put(
        f"{BASE_URL}/projects/{project_id}/uploads/incoming/company-rules.md",
        headers={"X-User-ID": owner_id, "Content-Type": "text/markdown"},
        data="# Restore\n\nVerify file hashes before restoring a file. Keep the original intact.",
    )
    assert upload_response.status == 201
    file_id = upload_response.json()["file_id"]

    open_workspace(page, "Knowledge")
    page.locator("#knowledge-files-refresh").click()
    page.locator(f"#knowledge-file-id option[value='{file_id}']").wait_for(state="attached")
    page.locator("#knowledge-file-id").select_option(file_id)
    page.locator("#knowledge-source-form input[name='title']").fill("Restore SOP")
    page.locator("#knowledge-source-form").get_by_role(
        "button", name="Register source for review"
    ).click()
    page.locator("#knowledge-result").wait_for(state="visible")

    source_response = page.request.get(
        f"{BASE_URL}/projects/{project_id}/knowledge-sources",
        headers={"X-User-ID": owner_id},
    )
    assert source_response.status == 200
    source_id = source_response.json()[0]["id"]
    approved = page.request.post(
        f"{BASE_URL}/projects/{project_id}/knowledge-sources/{source_id}/review",
        headers={"X-User-ID": supervisor_id},
        data={"decision": "approved"},
    )
    assert approved.status == 200
    ingested = page.request.post(
        f"{BASE_URL}/projects/{project_id}/knowledge-sources/{source_id}/ingest",
        headers={"X-User-ID": supervisor_id},
    )
    assert ingested.status == 201

    page.get_by_role("tab", name="Answer").click()
    page.locator("#knowledge-answer-query").fill(
        "How do we verify a file before restoring it?"
    )
    page.locator("#knowledge-answer-submit").click()
    answer_result = page.locator("#knowledge-answer-result")
    answer_result.wait_for(state="visible")
    expect(answer_result).to_contain_text("answered")
    expect(answer_result).to_contain_text("Verify file hashes before restoring a file.")
    expect(answer_result).to_contain_text("Evidence rail")
