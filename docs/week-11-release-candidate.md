# Release candidate and acceptance record

This is the Week 11 staging handover record. It is intentionally a gate, not
an assertion that supervisor acceptance or production readiness has already
been granted. Use sanitized sample material only; never seed real client or
employee data into the staging instance.

## Candidate identity

- Candidate/version: Local Week 11 release candidate (not tagged)
- Source revision: `a3dc85f4657ac127b5053ff6388856f737539367` (`main`, 2026-09-30)
- Staging URL: `http://127.0.0.1:18000` (loopback only)
- Deployment date: 2026-09-29
- Image: `ccl-week11-staging-api`, `sha256:91c797f03cb68024699ff3fb4630b1757ca90d794dc0688ef516da1afa84d166`
- Data set: synthetic, sanitized browser-acceptance fixtures; no production/customer data
- Compose project: `ccl-week11-staging`, with separate PostgreSQL, project-storage, and backup-storage volumes

## Automated pull-request gates

The GitHub Actions workflow in `.github/workflows/ci.yml` runs on pull requests
and pushes to `main`. It runs Python correctness lint, unit/API/PostgreSQL
integration tests, frontend lint/build and live Chromium acceptance tests,
Python and production JavaScript dependency audits, and a Git history secret
scan. The hosted workflow passed on the published source revision below. The
documentation changes now in progress require a fresh run after publication.

- CI run URL and revision: [run 36586252498](https://github.com/EF-Code/ccl-suite/actions/runs/36586252498) on `a3dc85f4657ac127b5053ff6388856f737539367` - passed
- Python correctness lint: passed (`ruff check --isolated --select E4,E7,E9,F .`)
- Python unit/API suite: 361 passed, 2 skipped locally; hosted backend job passed, including PostgreSQL integration
- Live PostgreSQL integration: passed in the hosted backend job against its isolated CI database
- Frontend lint and production build: passed
- Python dependency audit: no known vulnerabilities reported
- Production frontend dependency audit: no known vulnerabilities reported
- Git history secret scan: passed on the hosted run; no secret finding reported
- Live browser acceptance: 9 passed against the isolated staging API

## Acceptance and fault checks

Run these against the isolated staging project and attach sanitized evidence.

| Area | Expected result | Result / evidence |
| --- | --- | --- |
| Functional integration | Login, project/folder setup, upload/inventory/organize/restore, source review/ingestion, cited answer, research review/export controls, independent workflow approval, and guarded specialist flow | Passed: 9 live browser tests against staging |
| Invalid input | Invalid paths, unsupported uploads, malformed requests, stale plans, and conflicting destinations must fail safely without overwriting data | Passed in the 361-test backend/API suite |
| Service failure | Database loss must fail closed; readiness and protected API operations return 503 and Compose marks the API unhealthy | Passed live: `/health` and authenticated `/projects` returned 503 while PostgreSQL was stopped |
| Unauthorized access | Unauthenticated, wrong-role, cross-project, CSRF-invalid, and requester self-approval attempts are denied | Passed in backend/API tests; browser approval flow uses a separately invited supervisor |
| Adversarial input | Prompt injection, secret-extraction, approval-bypass, and path-traversal cases remain blocked | Passed in the automated security and agent guardrail tests |
| Performance | 100 sequential loopback requests per route, one request at a time, rootless Docker 29.7.2 on the development host; zero failed samples | `/health`: p50 5.60 ms, p95 10.18 ms, max 14.28 ms. `/`: p50 6.99 ms, p95 12.89 ms, max 15.14 ms. Not a concurrent/load-capacity result. |
| Recovery | PostgreSQL stopped for a controlled fault test; verified backup creation/restore and interrupted file-operation rollback in the test suite | Passed: Compose marked API unhealthy during outage; after PostgreSQL restart, DB/API became healthy and authenticated `/projects` returned 200 in 10.1 seconds. Backup/restore and interrupted-move checks also passed. |

## Defect triage and supervisor sign-off

| Priority | Defect | Owner | Status |
| --- | --- | --- | --- |
| High, resolved | Authenticated database lookup failures escaped as HTTP 500, and `/health` stayed green when PostgreSQL was unavailable | Engineering | Fixed: failures now return a safe 503; health check performs a database readiness query; unit and live outage/recovery checks pass |
| Medium, resolved | Organizer conflict-quarantine CLI referenced an undefined journal variable after moving a conflict | Engineering | Fixed: captures and reports the quarantine journal; regression test passes |

- Critical/high defects resolved or explicitly accepted: the two issues above are resolved; no known open critical/high code defect from this candidate test pass
- Supervisor reviewer and acceptance date:
- Acceptance evidence/reference:
- Release decision: **Not approved until the pending checks and supervisor sign-off above are complete.**

## Staging isolation

Use a distinct Compose project name and non-default loopback ports so the
candidate has separate containers and named volumes from the regular demo:

```sh
CCL_API_BIND_PORT=18000 \
CCL_DB_BIND_PORT=15432 \
CCL_MAILPIT_BIND_PORT=18025 \
CCL_PUBLIC_URL=http://127.0.0.1:18000 \
docker compose --project-name ccl-week11-staging up --build -d
```

Compose project naming gives this staging run its own PostgreSQL, project-file,
and backup volumes. Do not use `down --volumes` on a project whose data is not
disposable. The local candidate is populated only with synthetic/sanitized
acceptance data and a staging-only administrator. Keep it bound to loopback;
supervisor access beyond this host requires an approved network/TLS setup.
