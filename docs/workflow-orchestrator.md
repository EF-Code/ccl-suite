# Workflow Orchestrator

The Workflow Orchestrator moves one active project through a small, explicit
control loop: define a versioned workflow, request a decision, and retain the
resulting approval record. It is intentionally bounded; it does not invent
tasks, run background agents, or change project files.

## Project-scoped flow

```text
active project
      |
      v
versioned definition  -->  approval request  -->  approved / rejected / cancelled
```

Every read and mutation is checked against the active project's owner or an
administrator/supervisor boundary. A workflow or approval from another
project is returned as not found, so callers cannot use an opaque identifier
to cross the project boundary.

## API surface

- `POST /projects/{project_id}/workflows` creates a draft workflow definition.
- `GET /projects/{project_id}/workflows` lists definitions for the project.
- `POST /workflows/{workflow_id}/approvals` creates a pending approval request.
- `GET /workflows/{workflow_id}/approvals` lists the approval trail.
- `POST /approvals/{approval_id}/decision` records one final decision.

Workflow creation and approval requests require `workflow.manage`.
Approval decisions require `approval.decide`. Optional actor fields are bound
to the authenticated `X-User-ID`; a caller cannot submit another user's ID.

## Decision rules

- New workflow definitions start as `draft`.
- Approval requests start as `pending`.
- A pending approval can be decided once as `approved`, `rejected`, or
  `cancelled`.
- Repeated decisions return a conflict response and leave the original record
  unchanged.
- The decision code is a short operator-facing reason code; request bodies and
  source documents are not copied into the audit record.

## Dashboard behavior

The Workflows workspace is project-aware and exposes:

- a lifecycle rail for definition, request, and decision stages;
- a compact workflow-definition form with a version field;
- approval-trail cards with pending/decided status badges;
- guarded approve, reject, and cancel actions;
- an optional decision code retained beside the approval outcome.

Selecting another project clears the prior workflow state and reloads only the
new project's definitions and approval records. The FastAPI-served static
artifact is regenerated from the Vite build after frontend changes.

## Verification

The backend suite covers creation, optional actor binding, one-time decisions,
and cross-project denial. The browser smoke suite covers project selection,
workflow creation, approval request creation, and an approval decision in the
dashboard.
