# Installation and deployment guide

This guide runs the suite locally with Docker Compose. The default setup is a
loopback-only demonstration environment, not a production deployment.

## Requirements

- Git
- Docker Engine with the Docker Compose v2 plugin
- Available loopback ports for the API (`8000`), PostgreSQL (`5432`), and
  Mailpit (`8025`); each port can be changed in `.env`

## Start a fresh local instance

1. Clone the repository and enter it:

   ```bash
   git clone https://github.com/EF-Code/ccl-suite.git
   cd ccl-suite
   ```

2. Create a local environment file and change its database password. Keep this
   file private and out of version control:

   ```bash
   cp .env.example .env
   chmod 600 .env
   ```

3. Start the stack and wait for the API health check:

   ```bash
   docker compose up --build -d
   docker compose ps
   curl -fsS http://127.0.0.1:8000/health
   ```

   Compose uses separate named volumes for PostgreSQL, project files, backups,
   and the generated application database credential. A one-shot storage
   initializer prepares the volumes, then a restricted role-initialization
   service creates a non-superuser application role and assigns existing app
   tables to it. The API receives only that role's owner-only password file;
   the PostgreSQL bootstrap administrator credential is not passed to the API.
   The API applies Alembic migrations as the application role before starting.

4. Bootstrap the first administrator. Use a passphrase from 12 to 1,024
   characters. The command prompts for it; do not put it on the command line:

   ```bash
   docker compose exec api python scripts/bootstrap_admin.py \
     --email admin@example.com
   ```

5. Open `http://127.0.0.1:8000/`, sign in, and invite a supervisor or staff
   account from Setup. In this local profile, invitation emails are captured in
   Mailpit at `http://127.0.0.1:8025`; they are not delivered externally.

## Operate and update

Useful checks and logs:

```bash
docker compose ps
docker compose logs --tail=100 api
docker compose logs --tail=100 db
```

After changing source code, rebuild and recreate the API:

```bash
docker compose up --build -d api
```

Stop the services without deleting persistent data:

```bash
docker compose down
```

Do not use `docker compose down --volumes` unless the PostgreSQL, project-file,
and backup data are intentionally disposable. A Docker volume is persistent
storage, not a backup.

The API runs as an unprivileged user with a read-only root filesystem and
restricted capabilities. The separate storage initialization service has
only the permissions needed to set volume ownership. Project and backup roots
are private, distinct volumes. Backup creation has a 10 GiB aggregate default
limit, configurable with `CCL_BACKUP_MAX_TOTAL_BYTES`.

## Environment settings

Set local values in the ignored `.env` file. The tracked `.env.example` is a
template, not a source of production credentials.

| Setting | Purpose |
| --- | --- |
| `POSTGRES_PASSWORD` | Required local database password |
| `POSTGRES_USER` | PostgreSQL bootstrap administrator; not used by the API |
| `CCL_DATABASE_USER` | Application database role; defaults to `ccl_app` and must differ from `POSTGRES_USER` |
| `CCL_ENVIRONMENT` | Use `development` for the loopback demo; production enables secure cookies |
| `CCL_PUBLIC_URL` | Browser-facing origin used to construct invitation links |
| `CCL_BACKUP_MAX_TOTAL_BYTES` | Aggregate backup storage cap in bytes |
| `CCL_SMTP_*`, `CCL_MAIL_FROM_ADDRESS` | Outgoing email configuration; Mailpit is the local default |
| `CCL_API_BIND_PORT`, `CCL_DB_BIND_PORT`, `CCL_MAILPIT_BIND_PORT` | Host loopback ports |

Compose generates a distinct random application-role password in the private
`database_app_credentials` volume. Do not remove that volume independently
while retaining `postgres_data`; if it is lost, the next role-initialization
run generates a new password and applies it to the application role.

For a local database and API without Compose, create PostgreSQL separately,
then use the project environment:

```bash
~/.venv/bin/python -m pip install -r requirements.txt
export DATABASE_URL='postgresql+psycopg://localhost/ccl_suite'
~/.venv/bin/python -m alembic upgrade head
~/.venv/bin/python scripts/bootstrap_admin.py --email admin@example.com
~/.venv/bin/python -m uvicorn main:app --host 127.0.0.1 --port 8000
```

## Production deployment boundary

The Compose profile is for local development and controlled demonstrations.
Before exposing an instance beyond the host, provide HTTPS at a trusted proxy,
set `CCL_ENVIRONMENT=production` and the correct HTTPS `CCL_PUBLIC_URL`,
configure a real mail provider, establish database and file-storage backup
ownership, and review access, retention, monitoring, and recovery procedures.
Mailpit is not a production mail service. Do not copy demo passwords, sample
content, or `.env` values into a production environment.
