# Project backup and recovery runbook

This runbook covers project files and their integrity evidence. PostgreSQL is
managed separately; a project-file archive does not back up the relational
database.

## Storage and authorization contract

- `CCL_PROJECT_ROOT` contains each registered project's storage directory.
- `CCL_BACKUP_ROOT` is a distinct private directory for generated archives and
  manifests. In Compose, both roots are separate named volumes.
- Backup storage has a 10 GiB default aggregate cap. Set
  `CCL_BACKUP_MAX_TOTAL_BYTES` to a positive byte count to change it. If a new
  archive would exceed the cap, creation fails without deleting older backups.
- A manifest records relative paths, entry type, permission mode, size, and
  SHA-256 checksum. Symbolic links and special files are rejected.
- Create, read, verify, and restore operations require the corresponding
  `backup.*` permission and access to the owning project. Browser requests use
  an authenticated session and CSRF protection. `X-User-ID` is not
  authentication.
- Restores are published only to a new relative path below the owning
  project's storage directory. They do not replace the source project or an
  existing destination.

## Create and verify

Sign in to the dashboard as a user with `backup.create` and `backup.verify`,
select the project, and open the Recovery workspace.

1. Choose **Create backup** and wait for the response to report a verified
   archive.
2. Record the returned backup ID, creation time, file count, byte count, and
   archive and manifest checksums in the controlled operations record. Do not
   record session cookies or file contents.
3. Choose **Verify backup** for that backup. Confirm the expected entries,
   files, and bytes were checked and the result remains verified.

The corresponding audit events identify the backup and authenticated actor;
they do not contain file contents or host filesystem paths.

## Recovery rehearsal

Use a disposable project or an approved sanitized staging project. Do not
practice against production data without an approved change and recovery
window.

1. Pause or quiesce writes to the source project.
2. In Recovery, select a backup and run **Verify backup**. Do not restore an
   archive that fails verification.
3. Choose a new destination path, for example
   `restored/sample-project-check`, and run **Restore safe copy**. The
   destination is relative to the selected project's storage root, not a shared
   directory at the projects root.
4. Confirm the restore response's file count, byte count, archive checksum,
   manifest checksum, and destination.
5. Confirm that both the original source and restored copy exist. For a local
   project root, compare a sample file with:

   ```bash
   sha256sum \
     "projects/<PROJECT_STORAGE_SLUG>/incoming/records.csv" \
     "projects/<PROJECT_STORAGE_SLUG>/restored/sample-project-check/incoming/records.csv"
   ```

   With Compose, run the same checksum check against `/app/projects/` paths
   from inside the API container. The two digest values should match.
6. Confirm a `backup.restored` audit event is attributed to the signed-in
   actor. If the restored copy should become a separately registered project,
   inventory it and use the normal project registration process; restore does
   not silently create a new project record.
7. Resume writes only after the recovery owner confirms the destination and
   evidence.

## Expected safety outcomes

| Condition | Expected result |
| --- | --- |
| Existing restore destination | `409`; existing content unchanged |
| Traversal or absolute restore path | `400`; nothing written outside the project root |
| Missing archive or manifest | Safe error; no partial restore |
| Archive or manifest tampering | `422`; no restore; failure event recorded |
| User lacks backup permission or project access | `403` or scoped `404`; denial recorded |
| Storage cap would be exceeded | `507`; existing backups are retained |
| Successful create, verify, and restore | `backup.created`, `backup.verified`, and `backup.restored` events |

## Database recovery and evidence record

PostgreSQL is backed up separately from project files. The host-side
`scripts/backup_postgres.sh` creates a custom-format `pg_dump`, verifies that
PostgreSQL can read its archive, writes a SHA-256 sidecar, and publishes both
files with owner-only permissions. Its default location is
`$XDG_DATA_HOME/ccl-suite/database-backups` or
`$HOME/.local/share/ccl-suite/database-backups`; the default retention is 14
days. It never writes into the repository or deletes files outside that
dedicated directory.

The Compose API uses a dedicated non-superuser database role. Its generated
password is stored in the private `database_app_credentials` named volume and
is not included in a `pg_dump`. If restoring a database into a new or replaced
PostgreSQL volume, start the database and run the role initializer before the
API so it recreates the role, grants access, and assigns restored application
tables to that role:

```bash
docker compose up -d db
docker compose run --rm db-role-init
docker compose up -d api
```

This sequence preserves database rows; do not remove `postgres_data` or use
`docker compose down --volumes` during an ordinary restore.

For the local CCL Suite checkout at `~/ccl-suite`, install and enable the
user-level daily timer:

```bash
systemctl --user link \
  "$HOME/ccl-suite/systemd/user/ccl-suite-postgres-backup.service" \
  "$HOME/ccl-suite/systemd/user/ccl-suite-postgres-backup.timer"
systemctl --user daemon-reload
systemctl --user enable --now ccl-suite-postgres-backup.timer
systemctl --user start ccl-suite-postgres-backup.service
systemctl --user list-timers ccl-suite-postgres-backup.timer
```

The timer runs daily at 02:30 host-local time, with a randomized delay of up
to 15 minutes. `Persistent=true` runs a missed backup when the user service
manager next starts. The service uses the rootless Docker user service and the
checkout at `~/ccl-suite`; edit its unit paths before linking if the checkout
is elsewhere. Inspect status and logs with:

```bash
systemctl --user status ccl-suite-postgres-backup.service
journalctl --user -u ccl-suite-postgres-backup.service
```

Run a non-destructive restore rehearsal against a selected archive with:

```bash
./scripts/verify_postgres_backup.sh \
  "$HOME/.local/share/ccl-suite/database-backups/<backup-name>.dump"
```

The verifier checks the checksum, restores to a uniquely named temporary
database, checks its migration version and core record counts, and drops only
that temporary database on exit. It does not replace or write to the live
database. Keep the backup directory on an encrypted filesystem. The current
local home directory is on LUKS; this protects the dump at rest on this host,
but this single-disk policy does not protect against loss of the physical disk.

Do not treat the Compose database volume or project-file backups as a
PostgreSQL backup. Assign a local operator to review timer failures, available
disk space, retention, and restore rehearsals.

For each project-file rehearsal, record the backup ID, checksums, selected
file comparison, response counts, destination, timestamp, actor, and outcome.
Do not include credentials, invitation tokens, session cookies, client content,
or private machine paths in the record.
