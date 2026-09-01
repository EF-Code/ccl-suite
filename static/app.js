const flash = document.querySelector("#flash");
const healthBadge = document.querySelector("#health-badge");
const healthDot = document.querySelector("#health-dot");
const healthText = document.querySelector("#health-text");
const healthDetail = document.querySelector("#health-detail");
const healthRefresh = document.querySelector("#health-refresh");
const userResult = document.querySelector("#user-result");
const folderResult = document.querySelector("#folder-result");
const inventoryResult = document.querySelector("#inventory-result");
const conversionResult = document.querySelector("#conversion-result");
const organizerResult = document.querySelector("#organizer-result");
const backupResult = document.querySelector("#backup-result");
const projectsList = document.querySelector("#projects-list");
const projectsRefresh = document.querySelector("#projects-refresh");
const knowledgeResult = document.querySelector("#knowledge-result");
const knowledgeFiles = document.querySelector("#knowledge-file-id");
const knowledgeSourcesList = document.querySelector("#knowledge-sources-list");
const knowledgeFilesRefresh = document.querySelector("#knowledge-files-refresh");
const workspaceContext = document.querySelector("#workspace-context");
const activeProjectName = document.querySelector("#active-project-title");
const activeProjectDetail = document.querySelector("#active-project-detail");
const activeProjectStatus = document.querySelector("#active-project-status");
const activeProjectId = document.querySelector("#active-project-id");
const confirmDialog = document.querySelector("#confirm-dialog");
const confirmTitle = document.querySelector("#confirm-title");
const confirmMessage = document.querySelector("#confirm-message");
const confirmAccept = document.querySelector("#confirm-accept");

let selectedProjectId = "";

function storedOwnerId() {
  return window.localStorage.getItem("ccl-owner-id") || "";
}

function showFlash(message, kind = "success") {
  flash.textContent = message;
  flash.className = `flash ${kind}`;
  flash.setAttribute("role", kind === "error" ? "alert" : "status");
  flash.setAttribute("aria-live", kind === "error" ? "assertive" : "polite");
  flash.hidden = false;
}

function clearFlash() {
  flash.hidden = true;
  flash.textContent = "";
}

function showResult(element, message, kind = "success") {
  element.textContent = message;
  element.className = `result-box ${kind}`;
  element.setAttribute("role", kind === "error" ? "alert" : "status");
  element.setAttribute("aria-live", kind === "error" ? "assertive" : "polite");
  element.hidden = false;
}

function setBusy(button, busy, busyLabel = "Working…") {
  if (!button) return;
  if (busy) {
    button.dataset.idleLabel = button.textContent;
    button.disabled = true;
    button.setAttribute("aria-busy", "true");
    button.textContent = busyLabel;
    return;
  }
  button.disabled = false;
  button.removeAttribute("aria-busy");
  if (button.dataset.idleLabel) {
    button.textContent = button.dataset.idleLabel;
    delete button.dataset.idleLabel;
  }
}

async function withBusy(button, busyLabel, action) {
  setBusy(button, true, busyLabel);
  try {
    return await action();
  } finally {
    setBusy(button, false);
  }
}

function setHealth(healthy, detail) {
  healthBadge.textContent = healthy ? "API online" : "API unavailable";
  healthBadge.className = `badge ${healthy ? "badge-success" : "badge-error"}`;
  healthBadge.setAttribute("aria-label", healthy ? "API online" : "API unavailable");
  healthDot.className = `health-dot ${healthy ? "health-dot-success" : "health-dot-error"}`;
  healthText.textContent = healthy ? "Service is ready" : "Service check failed";
  healthDetail.textContent = detail;
}

async function apiRequest(path, options = {}) {
  const requestHeaders = { "Content-Type": "application/json", ...(options.headers || {}) };
  const ownerId = storedOwnerId();
  if (ownerId && !requestHeaders["X-User-ID"] && !requestHeaders["x-user-id"]) {
    requestHeaders["X-User-ID"] = ownerId;
  }
  const response = await fetch(path, {
    ...options,
    headers: requestHeaders,
  });
  const contentType = response.headers.get("content-type") || "";
  const payload = contentType.includes("application/json")
    ? await response.json()
    : await response.text();
  if (!response.ok) {
    const detail = typeof payload === "object" && payload !== null ? payload.detail : payload;
    throw new Error(detail || `Request failed (${response.status})`);
  }
  return payload;
}

async function refreshHealth(button = null) {
  const action = async () => {
    try {
      const payload = await apiRequest("/health");
      setHealth(payload.status === "ok", `GET /health · ${payload.status}`);
    } catch (error) {
      setHealth(false, error.message);
    }
  };
  return button ? withBusy(button, "Checking…", action) : action();
}

function formObject(form) {
  return Object.fromEntries(new FormData(form).entries());
}

function updateProjectContext(project) {
  selectedProjectId = project.id;
  const title = project.title || project.storage_slug || "Selected project";
  activeProjectName.textContent = title;
  activeProjectDetail.textContent = `Folder: ${project.storage_slug || "—"} · Owner: ${project.owner_id || "not assigned"}`;
  activeProjectStatus.textContent = "Ready to operate";
  activeProjectStatus.className = "badge badge-success";
  activeProjectId.textContent = project.id;
  workspaceContext.classList.add("is-active");
}

function updateProjectSelectionState() {
  projectsList.querySelectorAll("[data-project-id]").forEach((button) => {
    const isSelected = button.dataset.projectId === selectedProjectId;
    button.setAttribute("aria-pressed", String(isSelected));
    button.classList.toggle("is-selected", isSelected);
    button.closest("tr")?.classList.toggle("is-selected", isSelected);
  });
}

function selectProject(project) {
  updateProjectContext(project);
  document.querySelector("#conversion-project-id").value = project.id;
  document.querySelector("#inventory-project-id").value = project.id;
  document.querySelector("#organizer-project-id").value = project.id;
  document.querySelector("#backup-project-id").value = project.id;
  document.querySelector("#project-folder-name").value = project.storage_slug;
  document.querySelector("#knowledge-project-id").value = project.id;
  document.querySelector("#knowledge-owner-id").value = project.owner_id || "";
  updateProjectSelectionState();
  void refreshKnowledgeFiles(project.id);
  void refreshKnowledgeSources(project.id);
}

function statusClass(value) {
  return String(value || "unknown").toLowerCase().replace(/[^a-z0-9_-]/g, "-");
}

function renderProjects(projects) {
  if (!projects.length) {
    projectsList.innerHTML = '<p class="empty-state">No projects registered yet. Create one above to start a workflow.</p>';
    return;
  }
  const rows = projects.map((project) => `
    <tr data-project-row="${escapeHtml(project.id)}">
      <td><span class="project-title">${escapeHtml(project.title)}</span><br><span class="project-id">${escapeHtml(project.id)}</span></td>
      <td><span class="status-pill status-${statusClass(project.status)}">${escapeHtml(project.status)}</span></td>
      <td>${escapeHtml(project.description || "—")}</td>
      <td><button class="select-project${project.id === selectedProjectId ? " is-selected" : ""}" type="button" data-project-id="${escapeHtml(project.id)}" data-project-slug="${escapeHtml(project.storage_slug)}" data-project-title="${escapeHtml(project.title)}" data-project-owner="${escapeHtml(project.owner_id || "")}" aria-pressed="${String(project.id === selectedProjectId)}" title="Use ${escapeHtml(project.title)} project">Use project</button></td>
    </tr>
  `).join("");
  projectsList.innerHTML = `
    <table class="projects-table">
      <caption>Registered project workspaces</caption>
      <thead><tr><th scope="col">Project</th><th scope="col">Status</th><th scope="col">Description</th><th scope="col">Action</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>
  `;
  projectsList.querySelectorAll("[data-project-id]").forEach((button) => {
    button.addEventListener("click", () => {
      selectProject({
        id: button.dataset.projectId,
        storage_slug: button.dataset.projectSlug,
        title: button.dataset.projectTitle,
        owner_id: button.dataset.projectOwner,
      });
      document.querySelector("#folder-setup").scrollIntoView({ behavior: "smooth", block: "center" });
      showFlash(`Project selected. Generate “${button.dataset.projectSlug}” before scanning if its storage does not exist.`);
    });
  });
  updateProjectSelectionState();
}

async function refreshProjects(button = null) {
  const action = async () => {
    try {
      const projects = await apiRequest("/projects");
      renderProjects(projects);
      return projects;
    } catch (error) {
      const message = error.message === "An authenticated user is required."
        ? "Create a development owner above to load your projects."
        : `Could not load projects: ${error.message}`;
      projectsList.innerHTML = `<p class="empty-state">${escapeHtml(message)}</p>`;
      return [];
    }
  };
  return button ? withBusy(button, "Refreshing…", action) : action();
}

function renderKnowledgeFiles(files) {
  knowledgeFiles.replaceChildren();
  const activeFiles = files.filter((file) => file.status === "active");
  if (!activeFiles.length) {
    const empty = document.createElement("option");
    empty.textContent = "No active files available for registration";
    empty.value = "";
    empty.disabled = true;
    empty.selected = true;
    knowledgeFiles.append(empty);
    document.querySelector("#knowledge-register").disabled = true;
    return;
  }
  const placeholder = document.createElement("option");
  placeholder.textContent = "Select an active project file";
  placeholder.value = "";
  placeholder.disabled = true;
  placeholder.selected = true;
  knowledgeFiles.append(placeholder);
  activeFiles.forEach((file) => {
    const option = document.createElement("option");
    option.value = file.id;
    option.textContent = `${file.name} · ${file.storage_key}`;
    knowledgeFiles.append(option);
  });
  document.querySelector("#knowledge-register").disabled = false;
}

async function refreshKnowledgeFiles(projectId = document.querySelector("#knowledge-project-id").value.trim(), button = null) {
  const action = async () => {
    if (!projectId) {
      renderKnowledgeFiles([]);
      return;
    }
    try {
      const files = await apiRequest(`/projects/${encodeURIComponent(projectId)}/files`);
      renderKnowledgeFiles(files);
    } catch (error) {
      renderKnowledgeFiles([]);
      showResult(knowledgeResult, `Could not load project files: ${error.message}`, "error");
    }
  };
  return button ? withBusy(button, "Refreshing…", action) : action();
}

function renderKnowledgeSources(sources) {
  if (!sources.length) {
    knowledgeSourcesList.innerHTML = '<p class="empty-state">No knowledge sources registered for this project.</p>';
    return;
  }
  const rows = sources.map((source) => `
    <tr>
      <td><span class="project-title">${escapeHtml(source.title)}</span><br><span class="project-id">${escapeHtml(source.file_name)}</span></td>
      <td>${escapeHtml(source.source_type)}</td>
      <td>${escapeHtml(source.sensitivity)}</td>
      <td><span class="source-status source-status-${statusClass(source.approval_status)}">${escapeHtml(source.approval_status)}</span></td>
    </tr>
  `).join("");
  knowledgeSourcesList.innerHTML = `
    <table class="knowledge-table">
      <caption>Knowledge sources for the active project</caption>
      <thead><tr><th scope="col">Source</th><th scope="col">Type</th><th scope="col">Sensitivity</th><th scope="col">Review</th></tr></thead>
      <tbody>${rows}</tbody>
    </table>
  `;
}

async function refreshKnowledgeSources(projectId = document.querySelector("#knowledge-project-id").value.trim()) {
  if (!projectId) {
    knowledgeSourcesList.innerHTML = '<p class="empty-state">Select a project to view its knowledge sources.</p>';
    return;
  }
  try {
    const sources = await apiRequest(`/projects/${encodeURIComponent(projectId)}/knowledge-sources`);
    renderKnowledgeSources(sources);
  } catch (error) {
    knowledgeSourcesList.innerHTML = `<p class="empty-state">Could not load knowledge sources: ${escapeHtml(error.message)}</p>`;
  }
}

function confirmAction(title, message, confirmLabel) {
  if (!confirmDialog || typeof confirmDialog.showModal !== "function") {
    return Promise.resolve(window.confirm(message));
  }
  confirmTitle.textContent = title;
  confirmMessage.textContent = message;
  confirmAccept.textContent = confirmLabel;
  confirmDialog.returnValue = "";
  return new Promise((resolve) => {
    confirmDialog.addEventListener("close", () => resolve(confirmDialog.returnValue === "confirm"), { once: true });
    confirmDialog.showModal();
  });
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

healthRefresh.addEventListener("click", () => { void refreshHealth(healthRefresh); });
projectsRefresh.addEventListener("click", () => { void refreshProjects(projectsRefresh); });
knowledgeFilesRefresh.addEventListener("click", () => { void refreshKnowledgeFiles(undefined, knowledgeFilesRefresh); });

document.querySelector("#knowledge-source-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  clearFlash();
  const form = event.currentTarget;
  const submitButton = form.querySelector("button[type='submit']");
  const values = formObject(form);
  const projectId = values.project_id;
  delete values.project_id;
  try {
    const source = await withBusy(submitButton, "Registering…", () => apiRequest(`/projects/${encodeURIComponent(projectId)}/knowledge-sources`, {
      method: "POST",
      body: JSON.stringify(values),
    }));
    showResult(knowledgeResult, `Registered ${source.title}\nStatus: ${source.approval_status}\nFile: ${source.file_name}`);
    showFlash("Knowledge source registered for review. It cannot feed the knowledge base until approved.");
    form.querySelector("input[name='title']").value = "";
    await refreshKnowledgeSources(projectId);
  } catch (error) {
    showResult(knowledgeResult, error.message, "error");
    showFlash(error.message, "error");
  }
});

document.querySelector("#folder-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  clearFlash();
  const form = event.currentTarget;
  try {
    const folder = await withBusy(form.querySelector("button[type='submit']"), "Generating…", () => apiRequest("/project-folders", {
      method: "POST",
      body: JSON.stringify(formObject(form)),
    }));
    showResult(folderResult, `Created ${folder.project_path}\n${folder.subdirectories.join("\n")}`);
    showFlash(`Generated the ${folder.name} project folder layout.`);
  } catch (error) {
    showResult(folderResult, error.message, "error");
    showFlash(error.message, "error");
  }
});

document.querySelector("#user-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  clearFlash();
  const form = event.currentTarget;
  try {
    const user = await withBusy(form.querySelector("button[type='submit']"), "Creating…", () => apiRequest("/users", {
      method: "POST",
      body: JSON.stringify(formObject(form)),
    }));
    document.querySelector("#owner-id").value = user.id;
    window.localStorage.setItem("ccl-owner-id", user.id);
    showResult(userResult, `Created owner ${user.external_ref}\nID: ${user.id}`);
    await refreshProjects();
    showFlash("Development owner created. Its ID was copied into the project form.");
  } catch (error) {
    showResult(userResult, error.message, "error");
    showFlash(error.message, "error");
  }
});

document.querySelector("#project-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  clearFlash();
  const form = event.currentTarget;
  try {
    const project = await withBusy(form.querySelector("button[type='submit']"), "Registering…", async () => {
      const createdProject = await apiRequest("/projects", { method: "POST", body: JSON.stringify(formObject(form)) });
      selectProject(createdProject);
      await refreshProjects();
      return createdProject;
    });
    showFlash(`Project “${project.title}” registered. Generate its “${project.storage_slug}” folder before scanning files.`);
    form.reset();
    document.querySelector("#owner-id").value = project.owner_id || "";
  } catch (error) {
    showFlash(error.message, "error");
  }
});

document.querySelector("#inventory-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  clearFlash();
  const form = event.currentTarget;
  const projectId = document.querySelector("#inventory-project-id").value.trim();
  try {
    const result = await withBusy(form.querySelector("button[type='submit']"), "Scanning…", () => apiRequest(`/projects/${encodeURIComponent(projectId)}/inventory`, {
      method: "POST",
    }));
    showResult(inventoryResult, `Scanned ${result.files_scanned} file(s)\nDuplicate groups: ${result.duplicate_groups} (${result.duplicate_files} file(s))\nJSON: ${result.json_manifest}\nCSV: ${result.csv_manifest}`);
    showFlash("Inventory manifests created inside the project root.");
  } catch (error) {
    const message = error.message === "Project storage was not found."
      ? "Project storage was not found. Generate the selected project's folder layout before scanning."
      : error.message;
    showResult(inventoryResult, message, "error");
    showFlash(message, "error");
    if (error.message === "Project storage was not found.") {
      document.querySelector("#folder-setup").scrollIntoView({ behavior: "smooth", block: "center" });
    }
  }
});

function backupProjectId() {
  const projectId = document.querySelector("#backup-project-id").value.trim();
  if (!projectId) throw new Error("Select a project before using backup and recovery.");
  return projectId;
}

function backupId() {
  const value = document.querySelector("#backup-id").value.trim();
  if (!value) throw new Error("Create or select a backup before continuing.");
  return value;
}

function backupSummary(backup) {
  return `${backup.id} · ${backup.status} · ${backup.file_count} file(s) · ${backup.total_bytes} bytes\n` +
    `Archive SHA-256: ${backup.archive_checksum_sha256}\n` +
    `Manifest SHA-256: ${backup.manifest_checksum_sha256}`;
}

document.querySelector("#backup-create").addEventListener("click", async (event) => {
  clearFlash();
  try {
    const projectId = backupProjectId();
    const backup = await withBusy(event.currentTarget, "Creating…", () => apiRequest(`/projects/${encodeURIComponent(projectId)}/backups`, {
      method: "POST",
      body: "{}",
    }));
    document.querySelector("#backup-id").value = backup.id;
    showResult(backupResult, `Backup created and verified.\n${backupSummary(backup)}`);
    showFlash("Project backup created and verified against its manifest.");
  } catch (error) {
    showResult(backupResult, error.message, "error");
    showFlash(error.message, "error");
  }
});

document.querySelector("#backup-list").addEventListener("click", async (event) => {
  clearFlash();
  try {
    const projectId = backupProjectId();
    const backups = await withBusy(event.currentTarget, "Loading…", () => apiRequest(`/projects/${encodeURIComponent(projectId)}/backups`));
    if (!backups.length) {
      showResult(backupResult, "No backups recorded for this project.");
      showFlash("No project backups are available yet.");
      return;
    }
    document.querySelector("#backup-id").value = backups[0].id;
    showResult(backupResult, backups.map(backupSummary).join("\n\n"));
    showFlash(`Loaded ${backups.length} project backup(s). The newest backup is selected.`);
  } catch (error) {
    showResult(backupResult, error.message, "error");
    showFlash(error.message, "error");
  }
});

document.querySelector("#backup-verify").addEventListener("click", async (event) => {
  clearFlash();
  try {
    const projectId = backupProjectId();
    const id = backupId();
    const result = await withBusy(event.currentTarget, "Verifying…", () => apiRequest(`/projects/${encodeURIComponent(projectId)}/backups/${encodeURIComponent(id)}/verify`, {
      method: "POST",
      body: "{}",
    }));
    showResult(backupResult, `Integrity verified: ${result.entries_verified} entries, ${result.files_verified} file(s), ${result.bytes_verified} bytes\n${backupSummary(result.backup)}`);
    showFlash("Backup archive and manifest verified successfully.");
  } catch (error) {
    showResult(backupResult, error.message, "error");
    showFlash(error.message, "error");
  }
});

document.querySelector("#backup-restore").addEventListener("click", async (event) => {
  clearFlash();
  try {
    const projectId = backupProjectId();
    const id = backupId();
    const destination = document.querySelector("#backup-destination").value.trim();
    if (!destination) throw new Error("Enter a new restore destination.");
    const confirmed = await confirmAction(
      "Restore a new safe copy?",
      `The selected backup will be copied to “${destination}”. The original project will remain unchanged.`,
      "Restore copy",
    );
    if (!confirmed) {
      showFlash("Restore cancelled.");
      return;
    }
    const result = await withBusy(event.currentTarget, "Restoring…", () => apiRequest(`/projects/${encodeURIComponent(projectId)}/backups/${encodeURIComponent(id)}/restore`, {
      method: "POST",
      body: JSON.stringify({ destination_path: destination }),
    }));
    showResult(backupResult, `Restored ${result.files_restored} file(s) and ${result.bytes_restored} bytes\nDestination: ${result.destination_path}\nArchive SHA-256: ${result.archive_checksum_sha256}\nManifest SHA-256: ${result.manifest_checksum_sha256}`);
    showFlash("Backup restored to a new destination; the original was preserved.");
  } catch (error) {
    showResult(backupResult, error.message, "error");
    showFlash(error.message, "error");
  }
});

document.querySelector("#conversion-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  clearFlash();
  const form = event.currentTarget;
  const values = formObject(form);
  const projectId = values.project_id;
  delete values.project_id;
  try {
    const result = await withBusy(form.querySelector("button[type='submit']"), "Converting…", () => apiRequest(`/projects/${encodeURIComponent(projectId)}/conversions`, {
      method: "POST",
      body: JSON.stringify(values),
    }));
    showResult(conversionResult, `Converted ${result.source_path} → ${result.destination_path}\n${result.source_format.toUpperCase()} → ${result.destination_format.toUpperCase()} · ${result.bytes_written} bytes`);
    showFlash("Conversion completed without replacing the source or destination.");
  } catch (error) {
    showResult(conversionResult, error.message, "error");
    showFlash(error.message, "error");
  }
});

function organizerProjectId() {
  const projectId = document.querySelector("#organizer-project-id").value.trim();
  if (!projectId) throw new Error("Select a project before using the organiser.");
  return projectId;
}

function planSummary(plan) {
  const actions = plan.actions.length
    ? plan.actions.map((action) => `[${action.status}] ${action.source} → ${action.destination}`).join("\n")
    : "No files are waiting in incoming/.";
  return `Plan: ${plan.plan_path}\n${actions}`;
}

document.querySelector("#organizer-preview").addEventListener("click", async (event) => {
  clearFlash();
  try {
    const projectId = organizerProjectId();
    const plan = await withBusy(event.currentTarget, "Previewing…", () => apiRequest(`/projects/${encodeURIComponent(projectId)}/organization/plan`, {
      method: "POST",
    }));
    showResult(organizerResult, planSummary(plan));
    showFlash("Dry-run plan created. No files were moved.");
  } catch (error) {
    showResult(organizerResult, error.message, "error");
    showFlash(error.message, "error");
  }
});

document.querySelector("#organizer-apply").addEventListener("click", async (event) => {
  clearFlash();
  try {
    const projectId = organizerProjectId();
    const quarantine = document.querySelector("#quarantine-conflicts").checked;
    const confirmed = await confirmAction(
      "Apply the organisation plan?",
      `Eligible files in the active project will be moved into working/ folders. Conflicts will be protected${quarantine ? " and quarantined" : ""}, and a rollback journal will be saved.`,
      "Apply safe moves",
    );
    if (!confirmed) {
      showFlash("Organisation apply cancelled.");
      return;
    }
    const result = await withBusy(event.currentTarget, "Applying…", () => apiRequest(`/projects/${encodeURIComponent(projectId)}/organization/apply`, {
      method: "POST",
      body: JSON.stringify({ quarantine_conflicts: quarantine }),
    }));
    document.querySelector("#journal-path").value = result.journal_path;
    showResult(organizerResult, `Applied ${result.applied_count} of ${result.action_count} action(s)\nConflicts: ${result.conflict_count}\nJournal: ${result.journal_path}` + (result.quarantine_journal_path ? `\nQuarantine journal: ${result.quarantine_journal_path}` : ""));
    showFlash("Safe organisation completed and the rollback journal was saved.");
  } catch (error) {
    showResult(organizerResult, error.message, "error");
    showFlash(error.message, "error");
  }
});

document.querySelector("#organizer-rollback").addEventListener("click", async (event) => {
  clearFlash();
  try {
    const projectId = organizerProjectId();
    const journalPath = document.querySelector("#journal-path").value.trim();
    const confirmed = await confirmAction(
      "Roll back the organisation journal?",
      `The active project's recorded moves will be reversed from “${journalPath}” when the journal passes its hash checks.`,
      "Roll back",
    );
    if (!confirmed) {
      showFlash("Organisation rollback cancelled.");
      return;
    }
    const result = await withBusy(event.currentTarget, "Rolling back…", () => apiRequest(`/projects/${encodeURIComponent(projectId)}/organization/rollback`, {
      method: "POST",
      body: JSON.stringify({ journal_path: journalPath }),
    }));
    showResult(organizerResult, `Restored ${result.restored_count} file(s) from ${result.journal_path}.`);
    showFlash("Organisation rollback completed.");
  } catch (error) {
    showResult(organizerResult, error.message, "error");
    showFlash(error.message, "error");
  }
});

void refreshHealth();
if (storedOwnerId()) {
  void refreshProjects();
} else {
  projectsList.innerHTML = '<p class="empty-state">Create a development owner above to load your projects.</p>';
}
