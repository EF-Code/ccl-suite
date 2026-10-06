# User guide

Use the dashboard for normal project work. The current Compose demonstration
uses synthetic or sanitized data; do not upload real client or employee
records unless the organization has approved the environment and its data
handling rules.

## Sign in and choose a project

Sign in with the invitation-created account. If you forget your password,
choose **Forgot password?** and use the one-time link sent to the configured
mail service; local Compose captures it in Mailpit. Reset links expire after
30 minutes, can be used once, and revoke existing sessions when completed.
Select the project you are authorized to work on from the active-project
control. If the list is empty, ask an administrator or supervisor to register
a project or invite you to the appropriate workflow. Sign out when finished,
especially on a shared device.

## Your work and project team

Use **My Work** to review account-backed tasks assigned to you across projects.
Search by task, project, or details; filter by status; and open a project from
the task row. Older tasks may still show a legacy assignee label. That label is
preserved until a manager explicitly reassigns the task to an account.

Project membership controls access and is separate from assignment. A project
manager can add an invited account to the active project; the owner, an
administrator, or a supervisor can also grant the manager role. Only active,
assignable project members can receive tasks. Before removing a member, move or
clear their open assignments; completed work remains in the project history.

Open **Discuss** on a workboard task to read its project-scoped discussion.
Members with task-management access can add an update; interns can read but not
post. Comments are retained as project history and cannot be edited or deleted.
Each new comment creates an audit event that records the task and actor, not the
comment text.

## File operations

In Setup, register a project and generate its standard folder layout. In
Operations, upload approved files and run Inventory to record file metadata,
checksums, and duplicate candidates. Review an organization plan before
applying it; use its rollback operation if the recorded move needs to be
undone. Conversion, version restore, and backup restore preserve the source
and refuse to replace an existing destination.

Keep files inside the active project's approved storage. The interface scopes
operations to the selected project, and the API independently checks access.

## Knowledge and research

Register an active project file as a knowledge source. New sources begin in
`pending`; an authorized supervisor or administrator must review them before
ingestion. Search and answers use approved sources and show source citations.
The current answer path is bounded and extractive; it does not call an
external language-model provider.

Research tools provide a claim preview, scope checks, and evidence warnings.
They do not silently certify facts. Review each claim and its source, request
corrections where needed, mark evidence verified only after checking it, and
use the explicit approval and export controls when the package is ready.

## Workflows and approvals

Create or open the project's workflow, review its current state, and inspect
the action intent before requesting approval. A requester cannot approve their
own request. A separate authorized approver records the decision. Execute only
actions shown as approved and review the resulting trace; a recorded plan or
agent handoff is not proof that an external business action occurred.

## Monitoring and reporting

The Security workspace shows activity within the signed-in role's scope.
Authorized users can evaluate alert rules and review the previous completed
Monday-to-Sunday UTC operations report. Alert evaluation is user-triggered in
this release, not a continuously running monitor. Report counts are operational
records, not hours worked or AI-generated conclusions.
