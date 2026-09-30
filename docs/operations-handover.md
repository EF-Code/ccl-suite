# Local operations and demo guide

This guide supports local operation and demonstration of the CCL Suite. It is
not a claim of production hosting or remote-access readiness. Real email
delivery and backup/recovery setup are not prerequisites for local use.
Role-based review and approval remain normal application features; the backup
feature remains optional.

## Local verification — 2026-09-30

- Hosted CI run [36720490053](https://github.com/EF-Code/ccl-suite/actions/runs/36720490053)
  passed on base revision `8cfe1f579b4a921dd34f413f390379150ae9512b`, before
  the current uncommitted changes. It covered backend and PostgreSQL tests,
  frontend lint/build/audit, live dashboard browser tests, Compose validation,
  and repository secret scanning.
- After the current changes, the full local Python suite passed (`368 passed,
  2 skipped`); frontend lint/build, the scoped Ruff checks, and Compose
  configuration validation passed. Vite's largest JavaScript bundle is now
  436.05 kB, below the unchanged 550 kB warning threshold.
- The API image was rebuilt and only the API container was recreated. The
  running API and PostgreSQL services are healthy and loopback-bound; `/health`
  returned 200. The dashboard login screen loaded in the in-app browser, and
  all nine generated JavaScript/CSS assets returned 200 from the API.
- The authenticated Chromium suite had passed 10 flows on the hosted base
  revision, but it was not rerun against this uncommitted chunking change. The
  current verification exercised the login shell and every served asset; it
  did not submit account credentials or create demo records.
- Compose uses Mailpit to capture invitation messages. This is sufficient for
  local account testing; no external mail provider is configured or required.
- No backup operation is required for local use. Existing backup code, local
  archives, and the previously configured systemd timer were not changed here;
  this does not constitute an off-device recovery plan.
- The application remains loopback-only. Cloudflare Tunnel, LAN access, and
  local TLS are unconfigured and are outside the current local-use scope.

## Optional local walkthrough

Use sanitized or disposable data to exercise product flows.

1. Sign in and confirm the active account, role, and project selector.
2. Select a project, inventory its files, inspect an organization preview, and
   apply only safe planned operations.
3. Register a sample knowledge source, review and approve it with an authorized
   reviewer account, then inspect a cited extractive answer.
4. Preview research claims and scope/evidence warnings; verify claims only
   after inspecting their source passages, then export a review package.
5. Request a workflow action as one user and decide it from a different
   authorized account; inspect the resulting action and trace.
6. Review operational alerts and the weekly report, noting that alert
   evaluation is manual.
7. For invitations, open Mailpit and use the captured one-time link. External
   email delivery is not part of the local demo.

Stop at a failing step and preserve the error and sanitized run reference.
Do not present local test evidence as a production deployment or load test.

## Local-use checklist

| Area | Local-use status |
| --- | --- |
| Application and data services | Compose API and PostgreSQL; loopback-bound by default |
| Authentication and invitations | Server-side sessions and invite-only accounts; Mailpit captures invitation mail |
| Review and approvals | Available as application workflows; independent reviewer accounts can be used in a walkthrough |
| Email delivery | External provider not configured and not needed for local use |
| Backups | Not a local-use prerequisite; optional product workflow and existing host timer/archive are separate from this checklist |
| Remote access and TLS | Not configured; unnecessary while using the application on this host |

Keep credentials out of reports, screenshots, and source control. Use separate
test accounts when demonstrating role boundaries, and avoid real client or
employee data in a demo project.

## Follow-up only if scope changes

Remote hosting or access would require a separately reviewed network boundary,
TLS, secrets management, operational ownership, and recovery plan. External
email delivery should be configured only if invitations must reach real
recipients. Neither is needed for the current local workflow.
