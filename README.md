# CCL AI Suite

## Full AI tool suite


#### How To Start:

- Make sure Python 3.x is installed.
- Clone this repo
 ```bash
git clone https://github.com/EF-Code/ccl-suite.git
```
- Use a Python virtual environment and install dependencies (the commands below
  use `~/.venv`):
```bash
cd ccl-suite
~/.venv/bin/python -m pip install -r requirements.txt
```

- Start the API:

```bash
~/.venv/bin/python -m alembic upgrade head
~/.venv/bin/python scripts/bootstrap_admin.py --email admin@example.com
~/.venv/bin/python -m uvicorn main:app --reload
```

Open `http://127.0.0.1:8000/docs` for interactive API documentation.
Open `http://127.0.0.1:8000/` to sign in to the operations dashboard. The
bootstrap command prompts for the first administrator's password.

## API endpoints

- `GET /health` returns the service status.
- `GET /permissions` returns the administrator, supervisor, staff, and intern
  role-permission matrix.
- `POST /auth/login`, `GET /auth/me`, and `POST /auth/logout` manage an
  authenticated session.
- Administrators create, list, and revoke one-time account invitations under
  `/auth/invitations`; invitees accept them at `/auth/invitations/accept`.
- Administrators can list and disable accounts under `/auth/users`.
- `POST /projects` creates a database-backed project from a title, description,
  and existing user `owner_id`.
- `GET /projects` lists projects persisted in the database.
- `POST` and `GET /projects/{project_id}/files` manage searchable file
  metadata. Inventory scans persist file names, extensions, MIME types, sizes,
  modification times, SHA-256 hashes, and lifecycle status.
- `GET /projects/{project_id}/files/search` searches file name/path, MIME type,
  checksum, and status with project scoping and bounded pagination.
- `GET /projects/{project_id}/files/{file_id}/history` returns immutable
  inventory snapshots for created, updated, missing, and restored events.
- `GET /projects/{project_id}/files/{file_id}/versions` returns numbered,
  immutable metadata snapshots; inventory reports how many new versions it
  created in `versions_created`.
- `POST /projects/{project_id}/files/{file_id}/versions/{version_number}/restore`
  restores a verified version to a new destination without overwriting the
  original or an existing file.
- `PUT /projects/{project_id}/uploads/{storage_key}` streams an allow-listed
  upload, indexes its metadata, and records rejected attempts as security
  events.
- `GET /upload-policy` describes the upload size, filename, extension, and MIME
  allowlists used by the upload endpoint.
- The `file_versions` table is linked to each file record and stores the
  per-file version number, checksum, size, storage reference, and original-file
  marker for the version-control work.
- `POST /projects/{project_id}/conversions` converts an approved project file
  without overwriting its source or an existing destination.
- `POST /project-folders` creates the standard project folder layout below the
  configured projects root.
- `POST /projects/{project_id}/inventory` writes confined JSON/CSV manifests,
  synchronizes searchable file records, records metadata history, and returns
  inventory metadata and duplicate-hash counts.
- `POST` and `GET /projects/{project_id}/knowledge-sources` register and list
  source metadata for active project files. New sources are always `pending`.
- `POST /projects/{project_id}/knowledge-sources/{source_id}/review` lets a
  supervisor or administrator approve or reject a source. Only approved
  sources with active files are eligible for knowledge-base ingestion.
- `POST /projects/{project_id}/knowledge-sources/{source_id}/ingest` extracts
  one approved text source, creates deterministic chunks with source locations,
  stores a deterministic local retrieval vector, and persists the ingestion
  run and chunk metadata. It does not generate answers or call a model.
- `POST /projects/{project_id}/knowledge-search` ranks approved, active source
  passages for a bounded query with optional source-type, sensitivity, and
  source-ID filters. It enforces project-owner or supervisor/administrator
  access and returns source metadata with each passage.
- `POST /projects/{project_id}/knowledge-answer` composes a bounded,
  extractive answer from the strongest approved passages, returns numbered
  source citations, and refuses questions without sufficient evidence. It is
  deliberately dependency-free and does not call an external model.
- `POST /projects/{project_id}/knowledge-feedback` records a structured
  helpful/not-helpful rating without storing the question, answer, or source
  text.
- `POST /projects/{project_id}/knowledge-error-reports` records a structured
  search/answer issue category without storing raw request payloads or logs.
- `POST /projects/{project_id}/research/claims/extract` returns a bounded,
  validated claim preview with source metadata, exact passages, scope, and a
  `needs_review` status. It uses a local deterministic extractor and does not
  persist the preview.
- `POST /projects/{project_id}/research/claims/check-scope` compares a claim's
  model year, engine, market, population, setting, and evidence type with a
  target scope. Missing context is reported as `uncertain` rather than guessed.
- `POST /projects/{project_id}/research/evidence-register` checks a bounded
  claim preview for missing evidence, source mismatches, duplicates, explicit
  conflicts, and unsupported claim wording. It returns warnings without
  persisting or approving evidence.
- `POST /projects/{project_id}/backups` creates and immediately verifies a
  project archive plus a checksummed manifest without changing the source.
- `GET /projects/{project_id}/backups` lists project-scoped backup metadata;
  `/backups/{backup_id}/verify` rechecks the archive and every manifest hash.
- `POST /projects/{project_id}/backups/{backup_id}/restore` verifies and
  restores a backup to a new relative directory below the configured projects
  root. Existing destinations and the original project are never replaced.
- `POST /projects/{project_id}/organization/plan` previews file moves without
  changing files.
- `POST /projects/{project_id}/organization/apply` applies safe moves and can
  quarantine conflicts; `/organization/rollback` restores a journal.
- `POST` and `GET /projects/{project_id}/workflows` manage project workflows.
- `POST` and `GET /workflows/{workflow_id}/approvals` manage workflow approvals.
- `POST /approvals/{approval_id}/decision` records one approval decision.
- `POST` and `GET /security-events` manage structured security audit events.

Knowledge-base capability documentation covers the controlled
[source register](docs/knowledge-sources.md),
[document ingestion](docs/document-ingestion.md),
[semantic search](docs/semantic-search-checkpoint.md), and
[grounded answers](docs/knowledge-answer-checkpoint.md). The
[knowledge-agent contract](docs/knowledge-agent-contract.md) defines the
versioned instructions, response schema, extractive mode, and evidence
boundary. The [knowledge access control](docs/knowledge-access-control.md)
document defines the server-side permission, project, source-lifecycle, and
denial-audit boundaries. The
[evaluation report](docs/knowledge-answer-evaluation.md) records the fixed
20-case evidence, refusal, and conflicting-information validation suite.
The [research evidence agent](docs/research-evidence-agent.md) defines the
validated claim schema, preserved source passage, scope checker, evidence
register warnings, and the explicit preview-only boundary.
A non-sensitive [sample source](samples/knowledge/company-rules.md) is
available for the normal ingestion workflow.
The [representative media operations corpus](samples/knowledge/representative-media-company/README.md)
provides a clearly labelled, sanitized end-to-end acceptance set.

Protected routes require an active server-side session. An `X-User-ID` header
does not authenticate a production or development request. Login sets a
`HttpOnly`, `SameSite=Strict` session cookie and a CSRF cookie; state-changing
requests send the latter in `X-CSRF-Token`. Logout and administrator account
disable revoke sessions. Denied decisions are recorded as `access.denied`
security events. Mutation actor fields are bound to the authenticated actor;
supplied `uploaded_by_id`,
`created_by_id`, `requested_by_id`, `approved_by_id`, and security-event
`actor_id` values must match that user.

There is no public sign-up. Bootstrap the first administrator once, then have
that administrator create invitations in the Setup view. Each link expires
after three days and is accepted once. Invite tokens are carried in the URL
fragment so they are not sent in the initial page request. Existing
pre-migration demo users remain in the database but are inactive until explicitly replaced with
invited accounts; their project/file data is not erased. Set `CCL_PUBLIC_URL`
to the browser-facing origin for correct invitation links.

For a remote deployment, use HTTPS, set `CCL_ENVIRONMENT=production` (for
Secure cookies), set `CCL_PUBLIC_URL` to the HTTPS origin, and terminate TLS at
a trusted reverse proxy. The default Compose ports bind to loopback only.
There is not yet a self-service password-reset flow; an administrator must
handle lost credentials through an operational recovery procedure.

Request bodies are limited to 1 MiB. A new project's owner must be the
authenticated account unless the actor has administrative or supervisory
privileges. The legacy development user routes are unavailable outside the
isolated test suite.

## Database setup

```bash
export DATABASE_URL='postgresql+psycopg://localhost/ccl_suite'
~/.venv/bin/python -m alembic upgrade head
```

To roll the local schema back to its empty state:

```bash
~/.venv/bin/python -m alembic downgrade base
```

## Docker development environment

Copy the example environment file, replace its local password, and start the
API and PostgreSQL together:

```bash
cp .env.example .env
docker compose up --build -d
```

The API container waits for PostgreSQL, applies the Alembic migration, and then
starts Uvicorn. The API is available at `http://127.0.0.1:8000` and its
interactive documentation is at `/docs`. The local Mailpit inbox is at
`http://127.0.0.1:8025`.

In the Compose demo, invitation emails are captured by Mailpit and are not
delivered to real recipients. Its inbox is bound to localhost; SMTP is only
available to services on the Compose network. Mailpit stores messages in
memory, so its inbox clears when the container is recreated.

Create the first administrator in the running API container. This prompts for
a password and refuses to create a second bootstrap administrator:

```bash
docker compose exec api python scripts/bootstrap_admin.py --email you@example.com
```

Sign in at the dashboard, then use Setup to invite teammates by email and
role. Open Mailpit to inspect the captured message, or copy the one-time link
from the dashboard. Configure `CCL_PUBLIC_URL` in `.env` if users open the
site at a different origin, then recreate the API container. For a real mail
provider, set `CCL_SMTP_HOST`, `CCL_SMTP_PORT`, `CCL_SMTP_STARTTLS`,
`CCL_SMTP_USERNAME`, `CCL_SMTP_PASSWORD`, and `CCL_MAIL_FROM_ADDRESS` in `.env`.
Keep provider credentials out of source control.

Check container health and startup logs with:

```bash
docker compose ps
docker compose logs --tail=100 api
```

Stop the services with:

```bash
docker compose down
```

Do not add `--volumes` unless you intentionally want to erase the PostgreSQL,
project-file, and backup volumes.

The password is read from the ignored `.env` file and is not copied into the
Docker image.

Project backup storage is configured with `CCL_BACKUP_ROOT` and defaults to
`./backups`. It must be a separate private directory from `CCL_PROJECT_ROOT`.
The API returns portable artifact and manifest keys rather than host paths.
The complete recovery procedure and integrity checklist are in
[`docs/backup-recovery.md`](docs/backup-recovery.md).

To exercise a live PostgreSQL round trip, first start the Compose services and
set `TEST_DATABASE_URL` to the same local database, then run the opt-in test:

```bash
export TEST_DATABASE_URL='postgresql+psycopg://ccl_suite:LOCAL_PASSWORD@localhost:5432/ccl_suite'
~/.venv/bin/python -m pytest -m integration
```

Without `TEST_DATABASE_URL`, the integration test is skipped and the default
suite remains self-contained.

The dashboard uses the signed-in account as the owner when creating a project.

## Tests

```bash
~/.venv/bin/python -m pytest
```

To measure branch coverage locally:

```bash
~/.venv/bin/python -m pip install -r requirements-dev.txt
~/.venv/bin/python -m coverage run -m pytest
~/.venv/bin/python -m coverage report -m
```

The dashboard workflow smoke test is opt-in because it needs a running local
API and a Chromium-compatible browser. Install the browser once, start the API
with an isolated development database and project root, then run:

```bash
~/.venv/bin/python -m pip install -r requirements-browser.txt
~/.venv/bin/python -m playwright install chromium
RUN_BROWSER_TESTS=1 \
  DASHBOARD_BASE_URL=http://127.0.0.1:8000 \
  DASHBOARD_TEST_EMAIL=you@example.com \
  DASHBOARD_TEST_PASSWORD='your-isolated-test-password' \
  ~/.venv/bin/python -m pytest -m browser tests/test_dashboard_browser.py
```

Use an isolated disposable database for this opt-in browser suite: it creates
projects and files. The test follows login, project creation, folder generation,
inventory, and guarded operations. It skips during the normal suite unless
`RUN_BROWSER_TESTS=1` is set.

## Folder Standards

The standalone `folder_generator.py` script creates the standard project layout
for the file-automation work. It normalizes names to lowercase kebab-case and
creates `incoming`, `working`, `output`, and `archive` directories below one
approved root. It rejects path separators, world-writable roots, and existing
projects instead of overwriting them.

```bash
.venv/bin/python folder_generator.py "Client Intake Q3" --root ./projects
```

See [`docs/folder-standards.md`](docs/folder-standards.md) for the naming rules,
layout, and safety boundary.

## File inventory

Create a standard project folder first, then scan it with
`file_inventory.py`:

```bash
.venv/bin/python folder_generator.py "Client Intake Q3" --root ./projects
.venv/bin/python file_inventory.py --root ./projects/client-intake-q3
```

The scanner records each regular file's relative path, name, extension,
content-based MIME type, size, UTC modification time, SHA-256 hash, and whether
the MIME type agrees with the extension. It writes `manifest.json` and
`manifest.csv` inside the approved root.

Custom manifest paths may be supplied when they remain inside that root:

```bash
.venv/bin/python file_inventory.py \
  --root ./projects/client-intake-q3 \
  --json ./projects/client-intake-q3/output/files.json \
  --csv ./projects/client-intake-q3/output/files.csv
```

The scanner rejects symlinked or world-writable roots, skips symlinked files
and directories, and refuses output paths outside the approved root.

Inventory persistence is project-scoped. A file that disappears from a later
scan is marked `missing`; if it reappears, it is marked `active` and a
`restored` history snapshot is recorded. Generated manifests are excluded from
the asset database so repeated scans do not create false file history.

See [`docs/file-records.md`](docs/file-records.md) for search, history, upload,
and restoration examples. See [`docs/permissions.md`](docs/permissions.md) for
the role-permission matrix and authorization behavior.

## Safe file organisation

`file_organizer.py` creates a deterministic plan for moving files from a
project's `incoming` directory into category folders under `working`. The
default command is a dry run: it prints the proposed moves and writes
`organization-plan.json` without changing any files.

```bash
.venv/bin/python file_organizer.py ./projects/client-intake-q3
```

Review the plan before explicitly applying it:

```bash
.venv/bin/python file_organizer.py ./projects/client-intake-q3 \
  --apply \
  --journal ./projects/client-intake-q3/organization-journal.json
```

Files whose normalised names would collide are never overwritten. They can be
moved into a timestamped `quarantine` directory instead:

```bash
.venv/bin/python file_organizer.py ./projects/client-intake-q3 \
  --apply --quarantine-conflicts
```

Every applied move is recorded with its SHA-256 hash. Roll back a journal only
after checking the plan and the affected files:

```bash
.venv/bin/python file_organizer.py ./projects/client-intake-q3 \
  --rollback ./projects/client-intake-q3/organization-journal.json
```

The organiser refuses symlinked or world-writable roots, rejects path
components in directory and file names, keeps all plan/journal/quarantine
paths below the approved project root, and never performs permanent deletion.
Rollback also refuses to move a file whose recorded hash has changed.

## Operations dashboard

The authenticated dashboard at `http://127.0.0.1:8000/` exposes the current
operations in one screen: health checks, account invitations and project setup,
folder generation, inventory scanning, controlled conversion, and organiser
preview/apply/rollback. Select a project in the project table to populate the
inventory, conversion, and organisation forms.

The dashboard authenticates with server-side sessions and exposes operations
already implemented by the API and safe command-line modules. The default
Compose configuration is intentionally loopback-only.

## Controlled file conversion

The conversion endpoint operates on paths relative to the project's generated
folder. Create that folder below the approved projects root before calling the
endpoint:

```bash
.venv/bin/python folder_generator.py "Endpoint Project" --root ./projects
```

The database project's title is normalised to the same lowercase kebab-case
folder name. The request accepts these approved pairs:

- CSV to JSON and JSON to CSV
- Markdown to plain text and plain text to Markdown
- PNG to JPG and JPG to PNG

Example request (replace `<PROJECT_ID>` with the project identifier):

```bash
curl -X POST http://127.0.0.1:8000/projects/<PROJECT_ID>/conversions \
  -H 'Content-Type: application/json' \
  -d '{
    "source_path": "incoming/records.csv",
    "destination_path": "output/records.json"
  }'
```

The response reports the source and destination paths, canonical formats, and
number of bytes written. Text inputs must be UTF-8. Image conversion uses the
declared Pillow dependency. The endpoint returns `400` for unsafe paths, `404`
for missing project storage or source files, `409` for an existing destination,
`415` for an unsupported format pair, and `422` for malformed content.

Sources are never deleted or modified. Destination paths must remain below the
project root, symlinks and path traversal are rejected, and output is created
without replacing an existing file. Failed validation happens before output is
created, so the original remains available for retry.
