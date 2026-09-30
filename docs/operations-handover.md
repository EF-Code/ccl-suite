# Operations handover package

This is a working training and handover plan. It is not evidence that a live
supervisor training session, production deployment, or final release approval
has already occurred. Use the isolated staging instance and sanitized sample
corpus for rehearsal.

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
| Backend, frontend, Compose, browser, dependency, and secret CI gates | Verified on the recorded Week 11 source revision | Record the new release revision and its CI run after documentation changes are published |
| Critical/high defect register | No known open critical/high code defect in the current candidate test pass | Review the [defect register](release-defect-register.md) and re-run release checks on RC2 |
| Installation, administrator, user, architecture, and recovery guides | Prepared in the linked operations documentation | Supervisor reviews steps against the intended deployment |
| Presentation and demonstration script | Draft prepared; practice session pending | Review the deck after fresh RC2 evidence and record supervisor corrections |
| Supervisor practice session | Pending | Date, attendee, operator who demonstrated recovery, and follow-up items |
| Production hosting and data approval | Not established by the local staging demo | Named service owner, hosting decision, data classification, and approval reference |
| Credential and invitation ownership | Pending supervisor assignment | Named credential custodian and account review owner; never record secret values |
| PostgreSQL backup and restore | Separate operational procedure required | Provider, schedule, retention, restore test date, and responsible owner |
| Project-file backup and restore | Implemented; verify against the final release candidate | Backup ID, checksums, destination, timestamp, and actor |
| RC2 and final release tag | Pending | Fresh CI and staging evidence, approved tag, immutable source revision, release notes, and archive location |
| Temporary access cleanup | Pending final review | Confirm temporary accounts are disabled and their sessions revoked |

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
