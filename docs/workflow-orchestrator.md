# Workflow Orchestrator

The Workflow Orchestrator moves one active project through a small, explicit
control loop: capture a validated intake, define a versioned workflow, connect
read-only project services, request a decision, and retain the approval record.
It is intentionally bounded; it does not invent tasks, run background agents,
or change project files.

## Project-scoped flow

```text
active project
      |
      v
validated intake --> versioned definition --> read-only tools
                                      |
                                      v
                               approval request
                                      |
                                      v
                              approved / rejected / cancelled
```

Every read and mutation is checked against the active project's owner or an
administrator/supervisor boundary. A workflow or approval from another
project is returned as not found, so callers cannot use an opaque identifier
to cross the project boundary.

## API surface

- `POST /projects/{project_id}/workflows` creates a draft workflow definition.
- `GET /projects/{project_id}/workflows` lists definitions for the project.
- `POST /workflows/{workflow_id}/state` moves a workflow through its
  allow-listed non-approval states.
- `POST /workflows/{workflow_id}/approvals` creates a pending approval request.
- `GET /workflows/{workflow_id}/approvals` lists the approval trail.
- `POST /approvals/{approval_id}/decision` records one final decision.
- `POST /workflows/{workflow_id}/tools` runs one project-scoped read-only tool
  with a maximum of three attempts and a persisted trace.
- `GET /workflows/{workflow_id}/tools` lists tool traces without returning
  persisted source text.
- `POST /workflows/{workflow_id}/actions` queues a high-impact action intent
  behind a human approval gate.
- `GET /workflows/{workflow_id}/actions` lists action intents and their linked
  approval identifiers.
- `POST /workflow-actions/{action_id}/execute` records execution only after
  the linked approval is approved.

Workflow creation and approval requests require `workflow.manage`.
Approval decisions require `approval.decide`. Protected routes resolve the
actor from the active server-side session; optional actor fields must match
that authenticated user. `X-User-ID` is accepted only by isolated tests and
does not authenticate a deployed request.

## Intake and state rules

Project intake stores category, scope, optional deadline, expected outputs, and
the responsible person. Outputs are normalized into a non-empty, duplicate-free
list before persistence so an incomplete request cannot silently become a
workflow definition.

Workflow states are explicit: `ready`, `in_progress`, `review`,
`changes_required`, `approved`, and `archived`. Valid transitions are:

- `ready` -> `in_progress` or `review`;
- `in_progress` -> `review`;
- `review` -> `changes_required` or `approved` through the approval path;
- `changes_required` -> `in_progress` or `review`;
- `approved` -> `archived` through the approval path;
- `archived` -> no further state.

Direct API requests for `approved` or `archived` are rejected. This keeps
reviewer approval as the single gate for irreversible or final states.

## Decision rules

- New workflow definitions start as `draft`.
- Approval requests start as `pending`.
- A workflow accepts only one pending approval request at a time; a duplicate
  request returns a conflict until the existing request is decided.
- A pending approval can be decided once as `approved`, `rejected`, or
  `cancelled`.
- Repeated decisions return a conflict response and leave the original record
  unchanged.
- The decision code is a short operator-facing reason code; request bodies and
  source documents are not copied into the audit record.

## Tool and action guardrails

The connected-tool surface is deliberately allow-listed:

- `files.summary` reports active file count and total bytes;
- `knowledge.search` searches approved project sources only;
- `research.summary` reports review counts by status.

Each tool call receives a trace ID, bounded retry count, status, and safe input
and output summaries. Source text is not copied into the trace record.

Trace-list endpoints accept a positive `limit` query parameter capped at 50.
This keeps dashboard reads predictable while preserving the newest records
first for operator review.

High-impact action intents are limited to `send`, `delete`, `replace`,
`publish`, `archive`, and `approve`. They are idempotent when an idempotency
key is supplied, create a linked pending approval, and cannot execute until a
reviewer approves them. Execution records the approved intent and current
workflow state; it does not perform an external destructive side effect.

## Dashboard behavior

The Workflows workspace is project-aware and exposes:

- a lifecycle rail for definition, request, and decision stages;
- a compact workflow-definition form with a version field;
- approval-trail cards with pending/decided status badges;
- guarded approve, reject, and cancel actions;
- an optional decision code retained beside the approval outcome.
- the current workflow state and only its valid next transitions;
- connected-tool controls with trace, retry, and safe-summary visibility;
- approval-gated action controls with explicit pending and execution states.

Selecting another project clears the prior workflow state and reloads only the
new project's definitions and approval records. The FastAPI-served static
artifact is regenerated from the Vite build after frontend changes.

## Verification

The backend suite covers creation, intake validation, state-transition safety,
optional actor binding, one-time decisions, bounded tools, idempotent actions,
and cross-project denial. The browser smoke suite covers project selection,
workflow creation, approval request creation, and an approval decision in the
dashboard; the accelerated workflow slice adds state, tool, and action-gate
coverage.
