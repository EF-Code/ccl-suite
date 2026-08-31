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

    expected = Path(playwright_api.chromium.executable_path)  # type: ignore[attr-defined]
    if expected.is_file():
        return expected.as_posix()
    return shutil.which("google-chrome") or shutil.which("chromium")


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
    project_row.get_by_role("button", name="Use project").click()
    project_id = page.locator("#inventory-project-id").input_value()
    assert project_id
    assert page.locator("#organizer-project-id").input_value() == project_id

    folder_form = page.locator("#folder-form")
    expected_slug = project_title.lower().replace(" ", "-")
    assert folder_form.locator("input[name='project_name']").input_value() == expected_slug
    folder_form.get_by_role("button", name="Generate folder layout").click()
    folder_result = page.locator("#folder-result")
    folder_result.wait_for(state="visible")
    assert f"Created {expected_slug}" in folder_result.inner_text()

    inventory_form = page.locator("#inventory-form")
    inventory_form.get_by_role("button", name="Scan project files").click()
    inventory_result = page.locator("#inventory-result")
    inventory_result.wait_for(state="visible")
    expect(inventory_result).to_contain_text("Scanned 0 file(s)")
    expect(inventory_result).to_contain_text("JSON: manifest.json")

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
    expect(backup_result).to_contain_text("Restored")
    expect(backup_result).to_contain_text(restore_destination)

    page.locator("#organizer-preview").click()
    organizer_result = page.locator("#organizer-result")
    organizer_result.wait_for(state="visible")
    expect(organizer_result).to_contain_text("No files are waiting in incoming/.")

    page.locator("#organizer-apply").click()
    expect(organizer_result).to_contain_text("Applied 0 of 0 action(s)")
    expect(organizer_result).to_contain_text("Journal: organization-journal.json")

    page.locator("#organizer-rollback").click()
    expect(organizer_result).to_contain_text("Restored 0 file(s)")
