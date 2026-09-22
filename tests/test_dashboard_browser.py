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
from playwright.sync_api import Page, TimeoutError as PlaywrightTimeoutError, expect, sync_playwright


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
    expect(answer_result).to_contain_text("grounded-answer-v1")
    expect(answer_result).to_contain_text("extractive")
    expect(answer_result).to_contain_text("Verify file hashes before restoring a file.")
    expect(answer_result).to_contain_text("Evidence rail")
    feedback_panel = page.locator("#knowledge-feedback-panel")
    expect(feedback_panel).to_be_visible()
    page.locator("#knowledge-feedback-helpful").click()
    expect(page.locator("#knowledge-feedback-status")).to_contain_text("recorded")
    page.locator("#knowledge-error-category").select_option("wrong_source")
    page.locator("#knowledge-report-error").click()
    expect(page.locator("#knowledge-error-status")).to_contain_text("Report received")


def test_dashboard_exposes_knowledge_scope_filters(dashboard_page: Page) -> None:
    """Keep the searchable source and sensitivity scopes visible in the UI."""

    page = dashboard_page
    page.goto(BASE_URL, wait_until="networkidle")
    open_workspace(page, "Knowledge")

    page.get_by_role("tab", name="Search").click()
    expect(page.locator("#knowledge-search-source-type")).to_be_visible()
    expect(page.locator("#knowledge-search-sensitivity")).to_be_visible()
    expect(page.locator("#knowledge-search-source-type option")).to_have_count(5)
    expect(page.locator("#knowledge-search-sensitivity option")).to_have_count(5)

    page.get_by_role("tab", name="Answer").click()
    expect(page.locator("#knowledge-answer-source-type")).to_be_visible()
    expect(page.locator("#knowledge-answer-sensitivity")).to_be_visible()


def test_dashboard_runs_research_claim_and_scope_workflow(dashboard_page: Page) -> None:
    """Exercise the bounded research preview without approving or exporting it."""

    page = dashboard_page
    page.goto(BASE_URL, wait_until="networkidle")
    open_workspace(page, "Setup")

    suffix = uuid4().hex[:10]
    owner_ref = f"research-browser-owner-{suffix}"
    project_title = f"Research Browser {suffix}"

    user_form = page.locator("#user-form")
    user_form.locator("input[name='external_ref']").fill(owner_ref)
    user_form.get_by_role("button", name="Create development owner").click()
    page.locator("#user-result").wait_for(state="visible")
    owner_id = page.locator("#owner-id").input_value()
    assert owner_id

    project_form = page.locator("#project-form")
    project_form.locator("input[name='title']").fill(project_title)
    project_form.get_by_role("button", name="Register project").click()
    project_row = page.locator(".projects-table tbody tr").filter(has_text=project_title)
    project_row.wait_for(state="visible")
    project_row.get_by_role("button", name="Use project").click()
    expect(page.locator("#active-project-title")).to_have_text(project_title)

    open_workspace(page, "Research")
    page.locator("#research-source-title").fill("Vehicle field study")
    page.locator("#research-source-reference").fill("local://vehicle-field-study")
    page.locator("#research-source-date").fill("2026-09-16")
    page.locator("#research-source-model-year").fill("2024")
    page.locator("#research-source-engine").fill("hybrid")
    page.locator("#research-source-market").fill("Nigeria")
    page.locator("#research-source-text").fill(
        "# Vehicle facts\nThe vehicle uses a hybrid engine in the 2024 model year.\n"
        "The vehicle is safe.\nThe vehicle is not safe.\n"
        "Verify the source date before citing it."
    )
    page.locator("#research-extract-submit").click()
    claims_result = page.locator("#research-claims-result")
    claims_result.wait_for(state="visible")
    expect(claims_result).to_contain_text("factual")
    expect(claims_result).to_contain_text("needs review")
    expect(claims_result).to_contain_text("The vehicle uses a hybrid engine")

    page.locator("#research-claim-id").select_option(index=1)
    page.locator("#research-target-model-year").fill("2024")
    page.locator("#research-target-engine").fill("hybrid")
    page.locator("#research-target-market").fill("Nigeria")
    page.locator("#research-scope-submit").click()
    scope_result = page.locator("#research-scope-result")
    scope_result.wait_for(state="visible")
    expect(scope_result).to_contain_text("applicable")
    expect(scope_result).to_contain_text("All requested scope fields match")

    page.locator("#research-register-submit").click()
    register_result = page.locator("#research-register-result")
    register_result.wait_for(state="visible")
    expect(register_result).to_contain_text("warning")
    expect(page.locator("#research-register-warnings [data-warning-code='conflict']")).to_have_count(2)
    expect(register_result).to_contain_text("need review")

    page.locator("#research-submit-review").click()
    review_panel = page.locator("#research-human-review")
    expect(review_panel).to_contain_text("needs review")
    verify_buttons = review_panel.get_by_role("button", name="Mark verified")
    while True:
        page.wait_for_timeout(100)
        if verify_buttons.count() == 0:
            break
        button = verify_buttons.first
        try:
            expect(button).to_be_enabled()
            button.click()
        except PlaywrightTimeoutError:
            if verify_buttons.count() == 0:
                break
            raise
    expect(review_panel).to_contain_text("5/5 claims verified")
    page.locator("#research-approve-review").click()
    page.locator("#confirm-accept").click()
    expect(review_panel).to_contain_text("approved")
    expect(review_panel.get_by_role("button", name="CSV")).to_be_visible()
    expect(review_panel.get_by_role("button", name="JSON")).to_be_visible()
    expect(review_panel.get_by_role("button", name="Markdown")).to_be_visible()

    page.locator("#research-clear-preview").click()
    expect(page.locator("#research-claims-result")).to_contain_text("No claims yet")
    expect(page.locator("#research-scope-result")).to_be_hidden()
    expect(page.locator("#research-register-result")).to_be_hidden()


def test_dashboard_runs_workflow_definition_and_approval(dashboard_page: Page) -> None:
    """Exercise the project-scoped workflow and approval control plane."""

    page = dashboard_page
    page.goto(BASE_URL, wait_until="networkidle")
    open_workspace(page, "Setup")

    suffix = uuid4().hex[:10]
    owner_ref = f"workflow-browser-owner-{suffix}"
    project_title = f"Workflow Browser {suffix}"

    user_form = page.locator("#user-form")
    user_form.locator("input[name='external_ref']").fill(owner_ref)
    user_form.get_by_role("button", name="Create development owner").click()
    page.locator("#user-result").wait_for(state="visible")

    project_form = page.locator("#project-form")
    project_form.locator("input[name='title']").fill(project_title)
    project_form.get_by_role("button", name="Register project").click()
    project_row = page.locator(".projects-table tbody tr").filter(has_text=project_title)
    project_row.wait_for(state="visible")
    project_row.get_by_role("button", name="Use project").click()
    expect(page.locator("#active-project-title")).to_have_text(project_title)

    open_workspace(page, "Workflows")
    workflow_panel = page.locator("#workflow-orchestrator")
    expect(workflow_panel).to_be_visible()
    page.locator("#workflow-name").fill("Publish campaign package")
    page.locator("#workflow-version").fill("1")
    page.locator("#workflow-submit").click()

    workflow_card = page.locator("#workflow-list [data-workflow-id]").first
    workflow_card.wait_for(state="visible")
    expect(workflow_card).to_contain_text("Publish campaign package")
    expect(workflow_card.locator("[data-workflow-status='draft']")).to_be_visible()

    workflow_card.get_by_role("button", name="Request approval").click()
    approval = workflow_card.locator("[data-approval-id]").first
    approval.wait_for(state="visible")
    expect(approval.locator("[data-approval-status='pending']")).to_be_visible()
    approval.locator("input").fill("reviewed")
    approval.get_by_role("button", name="Approve").click()
    confirm_protected_action(page)
    expect(approval.locator("[data-approval-status='approved']")).to_be_visible()
    expect(workflow_panel.locator("[data-workflow-stage='decide']")).to_contain_text("Outcome recorded")


def test_dashboard_overview_surfaces_active_project_control(dashboard_page: Page) -> None:
    """Keep the reference-inspired overview tied to real project state."""

    page = dashboard_page
    page.goto(BASE_URL, wait_until="networkidle")
    open_workspace(page, "Setup")

    suffix = uuid4().hex[:10]
    owner_ref = f"overview-browser-owner-{suffix}"
    project_title = f"Overview Browser {suffix}"

    user_form = page.locator("#user-form")
    user_form.locator("input[name='external_ref']").fill(owner_ref)
    user_form.get_by_role("button", name="Create development owner").click()
    page.locator("#user-result").wait_for(state="visible")

    project_form = page.locator("#project-form")
    project_form.locator("input[name='title']").fill(project_title)
    project_form.get_by_role("button", name="Register project").click()
    project_row = page.locator(".projects-table tbody tr").filter(has_text=project_title)
    project_row.wait_for(state="visible")
    project_row.get_by_role("button", name="Use project").click()

    open_workspace(page, "Overview")
    overview = page.locator("#overview-dashboard")
    expect(overview).to_be_visible()
    expect(overview.locator("#overview-title")).to_have_text("Keep every project moving.")
    expect(overview.locator(".overview-project-card")).to_contain_text(project_title)
    expect(overview.locator(".overview-workflow-card")).to_contain_text("Project delivery path")
    expect(overview.locator(".overview-actions-card")).to_contain_text("Move the work forward")
