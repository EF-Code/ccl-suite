# Operations handover package

This is a working training and handover plan. It is not evidence that a live
supervisor training session, production deployment, or final release approval
has already occurred. Use the isolated staging instance and sanitized sample
corpus for rehearsal.

## Local operations verification — 2026-09-30

- The source base is `20aaa6ec702eaa5092fc101e58ddbc969ab3a249`. GitHub Actions
  run [36707850960](https://github.com/EF-Code/ccl-suite/actions/runs/36707850960)
  passed for that commit, including backend/PostgreSQL integration, frontend
  build and audit, Compose validation, live dashboard browser acceptance, and
  repository secret scanning. That run verifies the committed base only, not
  the additional uncommitted local changes listed below.
- The local API image was rebuilt from the current worktree and is healthy;
  image ID `sha256:317843a8dab73130643d90c4bda3fcf92f726c8c5b324470f3f80dda1b24cf56`.
  `/health` returned `ok`, the browser dashboard loaded without console errors,
  and the database is at Alembic revision `0017_project_work_items`. API and
  PostgreSQL ports remain bound to `127.0.0.1` only.
- The API now connects as `ccl_app`, not the PostgreSQL bootstrap
  administrator. Live checks confirmed superuser, database-creation,
  role-creation, and RLS-bypass privileges are disabled; all 26 public tables
  are owned by the application role. User/project/work-item counts remained
  `64/3/0` across the role transition.
- The full local backend suite passed (`367 passed, 2 skipped`); both
  PostgreSQL integration tests passed against a disposable database. All 10
  live Chromium dashboard acceptance flows passed against an isolated test
  database, including the 390 px mobile-header regression check. Frontend
  lint/build/audit, Python dependency audit, required Ruff checks, and Compose
  configuration validation passed. The frontend build emits a non-failing
  bundle-size warning (556 KB minified, 154 KB gzip).
- A custom-format PostgreSQL backup with a SHA-256 sidecar was created at
  `ccl-suite-postgres-20260930T125457Z-20aaa6ec702e.dump` and restored to an
  isolated temporary database at revision `0017_project_work_items`; the
  verifier removed that temporary database afterward. The user-level systemd
  timer is enabled for a daily 02:30 host-local run, with 14-day retention.
- The current backup directory is on the LUKS-encrypted system disk. You
  explicitly chose not to configure a secondary destination; this does not
  protect against failure of that physical disk.
- The Compose API remains loopback-only. Cloudflare Tunnel would provide
  Cloudflare-mediated remote access, not LAN-only access; it is not installed
  or configured. Keep it off until a Cloudflare hostname and Access identity
  allowlist are confirmed. Direct LAN access with local TLS is a separate,
  unconfigured option.

## Training session plan

Suggested duration: 45-60 minutes. The supervisor should operate the system
for the final portion rather than only watch a walkthrough.

| Segment | Practice | Completion evidence |
| --- | --- | --- |
| Access and roles | Sign in, identify active role, invite or disable a test account | Confirm the correct role and account lifecycle |
| Project files | Select a project, inventory files, review an organization plan, create and verify a backup | Save the sanitized test project and backup ID; do not record credentials |
| Knowledge and research | Review a source, inspect a cited answer, inspect evidence warnings, verify and export a review | Supervisor explains why source approval and human review are required |
| Workflow and agents | Request an approval, decide it from a separate supervisor session, inspect the handoff trace | Confirm requester and approver are distinct and trace is visible |
| Monitoring and recovery | Evaluate alerts, inspect report scope, restore a verified backup to a new path | Supervisor performs a recovery rehearsal without replacing the source |
| Ownership | Review deployment, secrets, data, database backup, support, and recovery responsibilities | Record named owners and approved procedures in the checklist below |

## Demonstration script

### Before the session

- Confirm the staging instance is healthy and bound only to its approved
  interface.
- Use the representative sanitized media-operations corpus in
  `samples/knowledge/representative-media-company/` or an approved synthetic
  equivalent.
- Confirm separate staff and supervisor accounts are available. Do not put
  passwords, invitation tokens, or session cookies in the script or slides.
- Ensure the selected project contains only disposable demonstration data and
  that its backup destination has sufficient capacity.
- Keep the previous backup outside the demo path; never use `down --volumes`
  as a cleanup step.

### Walkthrough (about 15 minutes)

1. **Access (1 min):** sign in as staff and show the active account and project
   selector. Explain that server-side sessions and project ownership enforce
   access.
2. **File control (3 min):** select the sanitized project, run inventory, and
   show file metadata and the non-destructive organization preview. Apply only
   the planned safe operations.
3. **Knowledge (3 min):** register the sample company-rules file. Switch to the
   supervisor session to approve it, ingest it, then show a cited extractive
   answer and its source passage.
4. **Research (2 min):** preview claims and scope/evidence warnings. Verify
   only after inspecting the evidence; show a review export.
5. **Workflow (2 min):** request approval as staff, record the decision from
   the separate supervisor session, then inspect the persisted action and
   trace.
6. **Recovery and monitoring (3 min):** create and verify a project backup,
   restore it to a new path within the project, compare a sample checksum, and
   show the related audit events and scoped monitoring view.
7. **Close (1 min):** state the current limits: local demo email uses Mailpit,
   answers are extractive rather than provider-generated, alert evaluation is
   manual, and production hosting requires separate approval and setup.

If any step fails, stop the walkthrough at that boundary, preserve the error
and sanitized run reference, and do not claim that the workflow completed.

## Final presentation outline

A supervisor review presentation draft is maintained separately from this
documentation package. Reconcile it with the recorded test evidence after RC2
and the supervisor walkthrough; keep pending release and acceptance gates
visible.

1. Problem and approved project scope
2. System architecture and data/security boundaries
3. File operations and recovery safeguards
4. Approved-source knowledge and cited answers
5. Human-reviewed research and workflow approvals
6. Automated tests, CI, staging evidence, and known limitations
7. Operator handover, ownership decisions, and next roadmap

Use measured results from the release record. Label local, CI, staging, and
supervisor-accepted evidence separately; do not present a demo as a production
deployment or a sequential smoke check as load capacity.

## Handover and release checklist

| Item | State | Record before final handover |
| --- | --- | --- |
| Backend, frontend, Compose, browser, dependency, and secret gates | Hosted CI passed for base `20aaa6ec`; current local checks passed as recorded above | Run hosted CI after local changes are reviewed and committed; record the release revision |
| Critical/high defect register | Prior register is tied to an older baseline; latest CI is green but is not a fresh source defect review | Refresh the [defect register](release-defect-register.md) on the release candidate |
| Installation, administrator, user, architecture, and recovery guides | Local PostgreSQL backup and controlled password-recovery procedures are documented | Supervisor reviews the procedures and confirms the intended operator |
| Presentation and demonstration script | Draft prepared; practice session pending | Review the deck after fresh RC2 evidence and record supervisor corrections |
| Supervisor practice session | Pending | Date, attendee, operator who demonstrated recovery, and follow-up items |
| Local deployment and data approval | No cloud hosting is planned; API and database remain loopback-only. Cloudflare hostname/Access identities and LAN CA/TLS are not configured | Keep remote access off until a hostname, allowed identities, certificate trust, and network boundary are explicitly configured and tested |
| Credential and invitation ownership | Local reset procedure and login/recovery serialization were tested against a disposable PostgreSQL database; no live account was changed | Assign the named credential custodian and account-review owner; never record secret values |
| PostgreSQL backup and restore | Daily systemd user timer enabled; 14-day retention; local restore rehearsal passed; user accepted single-disk storage | Assign an operator to review failures and disk space; record the accepted disk-failure risk and repeat a restore rehearsal periodically |
| Project-file backup and restore | API tests pass; the operational workflow is separate from PostgreSQL backup | Supervisor rehearses a project-file restore against a disposable/sanitized project on the release candidate |
| RC2 and final release tag | Pending | Fresh CI and staging evidence, approved tag, immutable source revision, release notes, and archive location |
| Temporary access cleanup | Not performed; no accounts or invitations were changed during this work | Supervisor reviews the account and invitation list, then authorizes disabling any temporary access |

## Post-handover roadmap

These are follow-up decisions, not claims of current capability:

- Approve and configure a remote deployment with HTTPS, managed secrets,
  durable database backups, monitoring ownership, and documented recovery.
- Select and validate an external email provider if invitations must reach real
  recipients.
- Add a scheduled alert evaluator only if an operator needs unattended checks
  and an owner is assigned to its delivery and failure monitoring.
- Consider a provider-backed language model only after documenting data
  handling, source rights, cost limits, retention, and human-review boundaries.
- Add self-service password recovery only with a reviewed identity and
  notification design.
