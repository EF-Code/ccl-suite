# User guide

Use the dashboard for normal project work. The current Compose demonstration
uses synthetic or sanitized data; do not upload real client or employee
records unless the organization has approved the environment and its data
handling rules.

## Sign in and choose a project

Sign in with the invitation-created account. Select the project you are
authorized to work on from the active-project control. If the list is empty,
ask an administrator or supervisor to register a project or invite you to the
appropriate workflow. Sign out when finished, especially on a shared device.

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
