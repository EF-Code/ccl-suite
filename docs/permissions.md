# Role permissions

The API uses a server-side role-permission matrix. The browser authenticates
with a revocable server-side session carried in the `ccl_session` cookie.
State-changing requests also require the `ccl_csrf` cookie value in the
`X-CSRF-Token` header. `X-User-ID` is not an authentication method. An AI
response is never consulted for authorization.

Identity fields on mutation requests are server-bound. Upload, workflow,
approval, and security-event records use the authenticated user as their
actor. If a caller supplies an actor field, it must match that user or the
request is rejected and recorded as `access.denied`.

## Matrix

| Role | Allowed operations |
| --- | --- |
| `administrator` | All project, work-item, file, backup, conversion, workflow, approval, security, knowledge-source, and user-management operations |
| `supervisor` | Project and work-item management, file read/upload/restore/organise, backup create/read/verify/restore, conversion, workflow, approval decisions, knowledge-source registration/review/ingestion, security-event writes, and alert management |
| `staff` | Work-item management in projects they own or are explicitly a member of, file read/upload/restore/organise, backup create/read/verify/restore, conversion, workflow, approval decisions, knowledge-source registration/read/ingestion, scoped security reads, and alert evaluation |
| `intern` | Project, work-item, and file metadata read only |

Project owners are enrolled as project managers. Project managers can add or
remove ordinary members; only the owner, an administrator, or a supervisor can
promote or remove another project manager. Membership grants project access,
but assigning a task never does. Assignments must reference an active project
member with an assignable account role; interns remain read-only and cannot be
assigned.

Work-item operations use `work_item.read` and `work_item.manage` and remain
inside the same project boundary as other project data. Removing a member is
blocked while they own open work items; reassign or unassign that work first.
Older free-text assignee labels are retained as legacy labels and must be
explicitly reassigned before they appear in an account's personal work list.
`GET /my/work-items` returns the signed-in user's account-backed assignments
across projects they can access and disables HTTP caching for that response.
Task comments use the same boundaries: `work_item.read` permits reading, while
`work_item.manage` permits posting. Comment audit events contain the task
reference and actor but never the comment text.

Only administrators can offboard invited accounts. The impact preview lists
owned projects, open assignments, and memberships before any change. A
replacement is required when ownership or open tasks need transfer and must be
an active, non-intern account. Ownership, assignments, project memberships,
session revocation, account deactivation, and their audit events are committed
atomically. Completed assignments are preserved, and reactivation does not
restore removed project memberships.

Only administrators and supervisors have `security.write`. Staff cannot create
security events or acknowledge and resolve alerts. Staff security views are
limited to their permitted actor and project scope.

The read-only matrix is available at `GET /permissions`. The API keeps the
legacy `member` and `reviewer` development values as aliases for `staff` and
`supervisor` respectively. Unknown roles receive no permissions and cannot be
created through the development provisioning route.

## Calling a protected route

```bash
curl http://127.0.0.1:8000/projects \
  -b 'ccl_session=<SESSION_COOKIE>'
```

The placeholder represents a session issued by `POST /auth/login`; retain it in
a private cookie jar rather than storing real tokens in shell history. For
state-changing requests, send both the `ccl_session` and `ccl_csrf` cookies and
copy the CSRF cookie value into `X-CSRF-Token`. The dashboard handles this
automatically. A missing, expired, revoked, or disabled-account session
receives `401`; a valid session without the required permission receives
`403`. A cross-project request outside the actor's scope is hidden as `404`.
Denials are recorded as `access.denied` security events without storing request
payloads.

Backup lifecycle routes use the separate `backup.read`, `backup.create`,
`backup.verify`, and `backup.restore` permissions. Successful and failed
backup operations record only the backup identifier and authenticated actor in
security events.

Knowledge-source routes use `knowledge.read`, `knowledge.register`,
`knowledge.approve`, and `knowledge.ingest`. Interns cannot access the
register or ingest documents. Registration records only file metadata and
always starts in `pending`; approval is required before ingestion may consume
a source. Semantic search uses `knowledge.read` and adds a project boundary:
staff may retrieve only their owned project, while supervisors and
administrators are the current global project operators. A denied search is
returned as `404` and recorded without the query text.
