# Week 4 Friday checkpoint: backup and restore

## Planned work

- Learn: backup strategy, manifests, checksums, and recovery tests.
- Build: back up a sample project and verify integrity after restoration.
- Submit: Digital Asset System Version 1.
- Safety: record and test the recovery procedure.

## Delivered

- Project entries are enumerated deterministically. Regular files and
  directories are included; symbolic links and special files fail closed.
- Each backup has a canonical JSON manifest and an uncompressed deterministic
  tar archive stored outside project storage. The database stores only
  relative generated keys, counts, sizes, and SHA-256 values.
- Creation performs a second verification before the backup is marked
  `verified`. Verification rechecks the manifest, archive member types and
  paths, sizes, modes, and every file checksum.
- Restoration verifies first, extracts to a private staging directory, scans
  the staged tree again, and publishes only to a new destination. Existing
  destinations and source files are preserved.
- API routes cover create, list, verify, and restore. Backup permissions are
  explicit for administrator, supervisor, and staff roles; interns remain
  read-only for project/file metadata.
- Successful and failed lifecycle operations are recorded as structured
  security events tied to the authenticated actor and backup ID, without raw
  request bodies or host paths.
- The local dashboard exposes the create, list, verify, and restore actions.

## Evidence to retain

Run the default regression suite and keep its result with this checkpoint:

```bash
.venv/bin/python -m pytest -q
```

For the full recovery demonstration, use
[`backup-recovery.md`](backup-recovery.md) and record the backup ID, both
checksums, response counts, source/restored file comparisons, destination, and
the authenticated actor. The opt-in browser and PostgreSQL checks remain
useful release gates when their local services are available.

## Boundary

The V1 archive restores project filesystem contents and integrity evidence. It
does not silently create a new database Project/File record set. After a
successful restore, inventory the new directory and register it through the
normal workflow if it should become an active project. Database-provider
backups remain a separate operational responsibility.
