# Project backup and recovery runbook

This runbook records the recovery procedure for the Digital
Asset System Version 1. It covers project files and their integrity evidence;
the relational database remains managed separately through Alembic and the
database provider's backup policy.

## Storage contract

- `CCL_PROJECT_ROOT` contains the registered project folders.
- `CCL_BACKUP_ROOT` contains generated `.tar` archives and
  `.manifest.json` files. It defaults to `./backups`.
- The two roots must be separate private directories. Backup records store
  relative artifact keys, never host filesystem paths.
- A manifest records every regular file and directory, its relative POSIX
  path, permission mode, size, and SHA-256 checksum. Symbolic links and special
  files are rejected rather than silently omitted.
- Archive members use stable ordering and normalized metadata. A restore is
  staged, re-hashed, and published only to a new destination.

## Create and verify a backup

Run the API with the configured roots and apply the current database migration:

```bash
export CCL_PROJECT_ROOT=./projects
export CCL_BACKUP_ROOT=./backups
.venv/bin/python -m alembic upgrade head
```

After provisioning a development owner and creating a project folder, create
the backup. Replace the placeholders with values from the API responses:

```bash
curl -sS -X POST "http://127.0.0.1:8000/projects/<PROJECT_ID>/backups" \
  -H 'Content-Type: application/json' \
  -H "X-User-ID: <USER_ID>" \
  -d '{}'
```

The response must be `201` with `status: "verified"`, a non-zero archive and
manifest checksum, and relative `artifact_key` and `manifest_key` values.
Record the returned `id` as `<BACKUP_ID>`. A later integrity check is explicit:

```bash
curl -sS -X POST \
  "http://127.0.0.1:8000/projects/<PROJECT_ID>/backups/<BACKUP_ID>/verify" \
  -H 'Content-Type: application/json' \
  -H "X-User-ID: <USER_ID>" \
  -d '{}'
```

The verification response reports `entries_verified`, `files_verified`, and
`bytes_verified`. The corresponding `backup.verified` security event contains
only the backup ID and authenticated actor; it does not contain file contents,
request bodies, or host paths.

## Recovery test

1. Stop or quiesce writes to the source project.
2. List the project's backups and select one whose creation time and checksum
   are recorded:

   ```bash
   curl -sS "http://127.0.0.1:8000/projects/<PROJECT_ID>/backups" \
     -H "X-User-ID: <USER_ID>"
   ```

3. Run the verify request above. Do not restore an archive that fails it.
4. Choose a new destination below the projects root and restore:

   ```bash
   curl -sS -X POST \
     "http://127.0.0.1:8000/projects/<PROJECT_ID>/backups/<BACKUP_ID>/restore" \
     -H 'Content-Type: application/json' \
     -H "X-User-ID: <USER_ID>" \
     -d '{"destination_path":"restored/sample-project-check"}'
   ```

5. Confirm the response's file count, byte count, archive checksum, and
   manifest checksum. Independently inspect the restored tree and compare
   selected file hashes with the original, for example:

   ```bash
   sha256sum projects/<PROJECT_FOLDER>/incoming/records.txt
   sha256sum projects/restored/sample-project-check/incoming/records.txt
   ```

6. Confirm the original file still exists and the `backup.restored` event is
   attributed to the authenticated actor.
7. If the restored copy should become a new registered project, inventory it
   first and register its metadata through the normal project workflow. The
   restore endpoint intentionally does not silently create database records.

## Safety outcomes to record

| Check | Expected result |
| --- | --- |
| Existing restore destination | `409`; existing files unchanged |
| `../` or absolute restore path | `400`; no outside directory created |
| Missing archive or manifest | safe error; no partial restore |
| Archive or manifest tampering | `422`; no restore; failure event recorded |
| Intern role on backup read/restore | `403`; access denial recorded |
| Successful create, verify, restore | `backup.created`, `backup.verified`, and `backup.restored` events |

Keep the recovery result with the weekly checkpoint: backup ID, recorded
checksums, selected file comparisons, response counts, destination, timestamp,
and actor. Do not put credentials, tokens, or raw project contents in the
record.
