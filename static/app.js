const flash = document.querySelector("#flash");
const healthBadge = document.querySelector("#health-badge");
const healthDot = document.querySelector("#health-dot");
const healthText = document.querySelector("#health-text");
const healthDetail = document.querySelector("#health-detail");
const userResult = document.querySelector("#user-result");
const folderResult = document.querySelector("#folder-result");
const inventoryResult = document.querySelector("#inventory-result");
const conversionResult = document.querySelector("#conversion-result");
const organizerResult = document.querySelector("#organizer-result");
const projectsList = document.querySelector("#projects-list");

function showFlash(message, kind = "success") {
  flash.textContent = message;
  flash.className = `flash ${kind}`;
  flash.hidden = false;
}

function clearFlash() {
  flash.hidden = true;
  flash.textContent = "";
}

function showResult(element, message, kind = "success") {
  element.textContent = message;
  element.className = `result-box ${kind}`;
  element.hidden = false;
}

function setHealth(healthy, detail) {
  healthBadge.textContent = healthy ? "API online" : "API unavailable";
  healthBadge.className = `badge ${healthy ? "badge-success" : "badge-error"}`;
  healthDot.className = `health-dot ${healthy ? "health-dot-success" : "health-dot-error"}`;
  healthText.textContent = healthy ? "Service is ready" : "Service check failed";
  healthDetail.textContent = detail;
}

async function apiRequest(path, options = {}) {
  const response = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
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

async function refreshHealth() {
  try {
    const payload = await apiRequest("/health");
    setHealth(payload.status === "ok", `GET /health · ${payload.status}`);
  } catch (error) {
    setHealth(false, error.message);
  }
}

function formObject(form) {
  return Object.fromEntries(new FormData(form).entries());
}

function setProjectId(projectId) {
  document.querySelector("#conversion-project-id").value = projectId;
  document.querySelector("#inventory-project-id").value = projectId;
  document.querySelector("#organizer-project-id").value = projectId;
}

function renderProjects(projects) {
  if (!projects.length) {
    projectsList.innerHTML = '<p class="empty-state">No projects registered yet.</p>';
    return;
  }
  const rows = projects.map((project) => `
    <tr>
      <td><span class="project-title">${escapeHtml(project.title)}</span><br><span class="project-id">${escapeHtml(project.id)}</span></td>
      <td>${escapeHtml(project.status)}</td>
      <td>${escapeHtml(project.description || "—")}</td>
      <td><button class="select-project" type="button" data-project-id="${escapeHtml(project.id)}">Use project</button></td>
    </tr>
  `).join("");
  projectsList.innerHTML = `
    <table class="projects-table">
      <thead><tr><th>Project</th><th>Status</th><th>Description</th><th></th></tr></thead>
      <tbody>${rows}</tbody>
    </table>
  `;
  projectsList.querySelectorAll("[data-project-id]").forEach((button) => {
    button.addEventListener("click", () => {
      setProjectId(button.dataset.projectId);
      document.querySelector("#conversion-form").scrollIntoView({ behavior: "smooth", block: "center" });
      showFlash("Project selected for inventory, conversion, and organisation.");
    });
  });
}

async function refreshProjects() {
  try {
    const projects = await apiRequest("/projects");
    renderProjects(projects);
  } catch (error) {
    projectsList.innerHTML = `<p class="empty-state">Could not load projects: ${escapeHtml(error.message)}</p>`;
  }
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

document.querySelector("#health-refresh").addEventListener("click", refreshHealth);
document.querySelector("#projects-refresh").addEventListener("click", refreshProjects);

document.querySelector("#folder-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  clearFlash();
  try {
    const folder = await apiRequest("/project-folders", {
      method: "POST",
      body: JSON.stringify(formObject(event.currentTarget)),
    });
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
    const user = await apiRequest("/users", { method: "POST", body: JSON.stringify(formObject(form)) });
    document.querySelector("#owner-id").value = user.id;
    showResult(userResult, `Created owner ${user.external_ref}\nID: ${user.id}`);
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
    const project = await apiRequest("/projects", { method: "POST", body: JSON.stringify(formObject(form)) });
    setProjectId(project.id);
    await refreshProjects();
    showFlash(`Project “${project.title}” registered. Make sure its generated folder exists before converting files.`);
    form.reset();
  } catch (error) {
    showFlash(error.message, "error");
  }
});

document.querySelector("#inventory-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  clearFlash();
  const projectId = document.querySelector("#inventory-project-id").value.trim();
  try {
    const result = await apiRequest(`/projects/${encodeURIComponent(projectId)}/inventory`, {
      method: "POST",
    });
    showResult(
      inventoryResult,
      `Scanned ${result.files_scanned} file(s)\n` +
      `Duplicate groups: ${result.duplicate_groups} (${result.duplicate_files} file(s))\n` +
      `JSON: ${result.json_manifest}\nCSV: ${result.csv_manifest}`,
    );
    showFlash("Inventory manifests created inside the project root.");
  } catch (error) {
    showResult(inventoryResult, error.message, "error");
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
    const result = await apiRequest(`/projects/${encodeURIComponent(projectId)}/conversions`, {
      method: "POST",
      body: JSON.stringify(values),
    });
    showResult(
      conversionResult,
      `Converted ${result.source_path} → ${result.destination_path}\n${result.source_format.toUpperCase()} → ${result.destination_format.toUpperCase()} · ${result.bytes_written} bytes`,
    );
    showFlash("Conversion completed without replacing the source or destination.");
  } catch (error) {
    showResult(conversionResult, error.message, "error");
    showFlash(error.message, "error");
  }
});

function organizerProjectId() {
  const projectId = document.querySelector("#organizer-project-id").value.trim();
  if (!projectId) {
    throw new Error("Select a project before using the organiser.");
  }
  return projectId;
}

function planSummary(plan) {
  const actions = plan.actions.length
    ? plan.actions.map((action) => `[${action.status}] ${action.source} → ${action.destination}`).join("\n")
    : "No files are waiting in incoming/.";
  return `Plan: ${plan.plan_path}\n${actions}`;
}

document.querySelector("#organizer-preview").addEventListener("click", async () => {
  clearFlash();
  try {
    const projectId = organizerProjectId();
    const plan = await apiRequest(`/projects/${encodeURIComponent(projectId)}/organization/plan`, {
      method: "POST",
    });
    showResult(organizerResult, planSummary(plan));
    showFlash("Dry-run plan created. No files were moved.");
  } catch (error) {
    showResult(organizerResult, error.message, "error");
    showFlash(error.message, "error");
  }
});

document.querySelector("#organizer-apply").addEventListener("click", async () => {
  clearFlash();
  try {
    const projectId = organizerProjectId();
    const quarantine = document.querySelector("#quarantine-conflicts").checked;
    const result = await apiRequest(`/projects/${encodeURIComponent(projectId)}/organization/apply`, {
      method: "POST",
      body: JSON.stringify({ quarantine_conflicts: quarantine }),
    });
    document.querySelector("#journal-path").value = result.journal_path;
    showResult(
      organizerResult,
      `Applied ${result.applied_count} of ${result.action_count} action(s)\n` +
      `Conflicts: ${result.conflict_count}\nJournal: ${result.journal_path}` +
      (result.quarantine_journal_path ? `\nQuarantine journal: ${result.quarantine_journal_path}` : ""),
    );
    showFlash("Safe organisation completed and the rollback journal was saved.");
  } catch (error) {
    showResult(organizerResult, error.message, "error");
    showFlash(error.message, "error");
  }
});

document.querySelector("#organizer-rollback").addEventListener("click", async () => {
  clearFlash();
  try {
    const projectId = organizerProjectId();
    const journalPath = document.querySelector("#journal-path").value.trim();
    const result = await apiRequest(`/projects/${encodeURIComponent(projectId)}/organization/rollback`, {
      method: "POST",
      body: JSON.stringify({ journal_path: journalPath }),
    });
    showResult(organizerResult, `Restored ${result.restored_count} file(s) from ${result.journal_path}.`);
    showFlash("Organisation rollback completed.");
  } catch (error) {
    showResult(organizerResult, error.message, "error");
    showFlash(error.message, "error");
  }
});

refreshHealth();
refreshProjects();
