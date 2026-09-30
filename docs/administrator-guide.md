# Administrator guide

Administrators manage access and system setup. A user account alone does not
grant access to another project's files; the API applies both role permissions
and project boundaries.

## First administrator and sign-in

Create the first administrator once with the bootstrap command in the
[installation guide](installation.md). Sign in through the dashboard. The
browser uses a server-side session cookie and CSRF protection; an `X-User-ID`
header is not an authentication method.

There is no public sign-up. From Setup, create one-time invitations for the
appropriate role and share the generated link only with its intended recipient.
Invitation links expire after three days and can be accepted once. Local demo
messages appear in Mailpit; they are not sent to real mailboxes.

## Roles and access

| Role | Administrative scope |
| --- | --- |
| Administrator | User and invitation administration, all project operations, security-event writes, alert management, and organization-wide views |
| Supervisor | Project operations, source review, workflow decisions, security-event writes, alert management, and organization-wide views |
| Staff | Work on owned projects, including file and workflow operations; scoped security reads and alert evaluation, but no security-event writes or alert management |
| Intern | Read-only project and file metadata |

The `member` role is a legacy alias for `staff`; `reviewer` is an alias for
`supervisor`. Use the current role names for new invitations. See the
[permission matrix](permissions.md) for operation-level detail.

Disable an account from Setup when access should end. Disabling revokes its
active sessions. Review the account list and invitation state during access
reviews; do not reuse a recipient's invitation link for another person.

## Routine administration

- Keep the local `.env` private. Rotate credentials through the deployment's
  approved secret-management procedure, not by editing tracked files.
- Set `CCL_PUBLIC_URL` to the exact browser-facing origin before creating
  invitations. Recreate the API after changing Compose environment values.
- Review the Security page for scoped events and alerts. Alert evaluation is
  manual in this release; there is no background scheduler.
- Create project backups, verify them, and periodically perform a restore to a
  new path. Follow the [backup and recovery runbook](backup-recovery.md).
- Database backups are separate from project-file archives. Define and test a
  database backup and restore procedure with the selected database operator.
- Mailpit is only for local demonstrations. Production email requires an
  approved provider and protected provider credentials.

## Account recovery and support

The application does not provide self-service password reset. A trusted local
Linux operator with access to the rootless Docker service can reset the
password for an existing active, password-enabled account. Login and reset
transactions serialize on the account row, so the API does not need to be
stopped for recovery:

```bash
docker compose run --rm --no-deps --entrypoint python api \
  scripts/reset_account_password.py --email account@example.com
```

The command asks the operator to confirm the account and enter the new
passphrase twice without putting it in shell history or logs. It keeps the
account's role unchanged, revokes that account's sessions, and writes an
`auth.password.reset` security event with an opaque audit reference. Because
the reset is performed outside an authenticated application session, the event
has no application-user actor; the operator must record their identity, time,
and audit reference in the restricted local operations record. The command
refuses disabled accounts and accounts that have not accepted an invitation.
Test sign-in and review the security event. A login already in progress either
finishes first and has its new session revoked by recovery, or waits for the
reset and must use the new password. Do not put passwords, invitation tokens, session cookies,
or recovery codes in project issues, reports, or demonstration notes.
