# Release defect register

This register records defects identified in the Week 11 candidate review and
their verified disposition. It is a checkpoint record, not a guarantee that no
other defect exists. The baseline reviewed was revision
`a3dc85f4657ac127b5053ff6388856f737539367` on 2026-09-30. A new RC2 decision
requires fresh checks on the release revision; see the
[handover checklist](operations-handover.md).

## Resolved findings

| ID | Severity | Finding | Resolution | Verification evidence |
| --- | --- | --- | --- | --- |
| DEF-001 | High | Database lookup failures could surface as HTTP 500, while `/health` remained green during database unavailability. | Database failures return a safe `503`; readiness performs a database query, so Compose marks the API unhealthy when PostgreSQL is unavailable. | Hosted CI run [36586252498](https://github.com/EF-Code/ccl-suite/actions/runs/36586252498) passed. The Week 11 staging fault check stopped PostgreSQL, observed `503` on readiness and an authenticated route, then confirmed recovery after PostgreSQL restarted. |
| DEF-002 | Medium | The organizer's conflict-quarantine CLI could reference an undefined journal value after moving a conflict. | The operation now captures and reports its quarantine journal path. | `tests/test_cli_paths.py::test_organizer_cli_reports_the_quarantine_journal` passed in the recorded backend suite. |

## Current triage statement

The recorded candidate checks identified no unresolved critical or high
severity code defect. This statement is limited to the revision and checks
listed above; it is not a claim of zero defects or production readiness.
Re-run the release gates after changes and append any new findings before
approving RC2.

## Local-demo scope

External email delivery and database backups are not prerequisites for the local
demo. Invitations are exercised through Mailpit, and the app's independent
reviewer/approver workflow remains a product feature. Backup and recovery
functionality is still available but is not required for local use. This scope
decision does not claim external mail delivery, off-host recovery, or production
readiness.
