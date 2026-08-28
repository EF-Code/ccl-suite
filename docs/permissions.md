# Role permissions

The API uses a server-side role-permission matrix. A caller identifies the
authenticated user with the `X-User-ID` header; the server loads that user and
checks the stored role before running a protected operation. An AI response is
never consulted for authorization.

Identity fields on mutation requests are server-bound. Upload, workflow,
approval, and security-event records use the authenticated user as their
actor. If a caller supplies an actor field, it must match that user or the
request is rejected and recorded as `access.denied`.

## Matrix

| Role | Allowed operations |
| --- | --- |
| `administrator` | All project, file, backup, conversion, workflow, approval, security, and user-management operations |
| `supervisor` | Project creation/read, file read/upload/restore/organise, backup create/read/verify/restore, conversion, workflow, approval decisions, and security events |
| `staff` | Project creation/read, file read/upload/restore/organise, backup create/read/verify/restore, conversion, workflow, approval decisions, and security events |
| `intern` | Project and file metadata read only |

The read-only matrix is available at `GET /permissions`. The API keeps the
legacy `member` and `reviewer` development values as aliases for `staff` and
`supervisor` respectively. Unknown roles receive no permissions and cannot be
created through the development provisioning route.

## Calling a protected route

```bash
curl http://127.0.0.1:8000/projects \
  -H 'X-User-ID: <USER_ID>'
```

When running in development without a header, the first provisioned user is
used for the local prototype. Deployments outside development require the
header and return `401` when it is missing. A known user without the required
permission receives `403`, and the decision is recorded as an
`access.denied` security event without storing request payloads.

Backup lifecycle routes use the separate `backup.read`, `backup.create`,
`backup.verify`, and `backup.restore` permissions. Successful and failed
backup operations record only the backup identifier and authenticated actor in
security events.
