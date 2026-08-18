# CCL AI Suite

## Full AI tool suite


#### How To Start:

- Make sure Python 3.x is installed.
- Clone this repo
 ```bash
git clone https://github.com/EF-Code/ccl-suite.git
```
- Create a virtual environment
```bash
cd ccl-suite
python -m venv .venv
```
- Install dependencies
```bash
.venv/bin/python -m pip install -r requirements.txt
```

- Start the API:

```bash
.venv/bin/python -m uvicorn main:app --reload
```

Open `http://127.0.0.1:8000/docs` for interactive API documentation.

## API endpoints

- `GET /health` returns the service status.
- `POST /users` provisions an opaque development user reference. It is disabled
  when `CCL_ENVIRONMENT` is not `development`.
- `GET /users/{user_id}` returns one development user by opaque ID and is
  disabled outside development. It does not expose a user-list endpoint.
- `POST /projects` creates a database-backed project from a title, description,
  and existing user `owner_id`.
- `GET /projects` lists projects persisted in the database.
- `POST` and `GET /projects/{project_id}/files` manage file metadata only.
- `POST` and `GET /projects/{project_id}/workflows` manage project workflows.
- `POST` and `GET /workflows/{workflow_id}/approvals` manage workflow approvals.
- `POST /approvals/{approval_id}/decision` records one approval decision.
- `POST` and `GET /security-events` manage structured security audit events.

Request bodies are limited to 1 MiB. The API returns `404` when the supplied
`owner_id` does not identify an existing user. User creation and authentication
are separate concerns; the user route is only a local development provisioning
helper and is not an authentication mechanism.

## Database setup

```bash
export DATABASE_URL='postgresql+psycopg://localhost/ccl_suite'
.venv/bin/python -m alembic upgrade head
```

To roll the local schema back to its empty state:

```bash
.venv/bin/python -m alembic downgrade base
```

## Docker development environment

Copy the example environment file, replace its local password, and start the
API and PostgreSQL together:

```bash
cp .env.example .env
docker compose up --build
```

The API container waits for PostgreSQL, applies the Alembic migration, and then
starts Uvicorn. The API is available at `http://127.0.0.1:8000` and its
interactive documentation is at `/docs`.

Stop the services with:

```bash
docker compose down
```

The password is read from the ignored `.env` file and is not copied into the
Docker image.

To exercise a live PostgreSQL round trip, first start the Compose services and
set `TEST_DATABASE_URL` to the same local database, then run the opt-in test:

```bash
export TEST_DATABASE_URL='postgresql+psycopg://ccl_suite:LOCAL_PASSWORD@localhost:5432/ccl_suite'
.venv/bin/python -m pytest -m integration
```

Without `TEST_DATABASE_URL`, the integration test is skipped and the default
suite remains self-contained.

After startup, provision a local development user and use its returned `id` as
the `owner_id` when creating a project:

```bash
curl -X POST http://127.0.0.1:8000/users \
  -H 'Content-Type: application/json' \
  -d '{"external_ref":"local-owner"}'
```

## Tests

```bash
.venv/bin/python -m pytest
```

## Folder Standards

The standalone `folder_generator.py` script creates the standard project layout
for the file-automation work. It normalizes names to lowercase kebab-case and
creates `incoming`, `working`, `output`, and `archive` directories below one
approved root. It rejects path separators, world-writable roots, and existing
projects instead of overwriting them.

```bash
python folder_generator.py "Client Intake Q3" --root ./projects
```

See [`docs/folder-standards.md`](docs/folder-standards.md) for the naming rules,
layout, and safety boundary.

## Week 3 Day 2: file inventory

Create a standard project folder first, then scan it with
`file_inventory.py`:

```bash
python folder_generator.py "Client Intake Q3" --root ./projects
python file_inventory.py --root ./projects/client-intake-q3
```

The scanner records each regular file's relative path, name, extension,
content-based MIME type, size, UTC modification time, SHA-256 hash, and whether
the MIME type agrees with the extension. It writes `manifest.json` and
`manifest.csv` inside the approved root.

Custom manifest paths may be supplied when they remain inside that root:

```bash
python file_inventory.py \
  --root ./projects/client-intake-q3 \
  --json ./projects/client-intake-q3/output/files.json \
  --csv ./projects/client-intake-q3/output/files.csv
```

The scanner rejects symlinked or world-writable roots, skips symlinked files
and directories, and refuses output paths outside the approved root.
