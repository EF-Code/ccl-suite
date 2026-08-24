# File records

The inventory endpoint keeps file contents on the approved project filesystem
and stores only searchable metadata in PostgreSQL. This makes the database
useful for discovery and audit without turning it into a file-content store.

## Persist an inventory

After a project folder exists, scan it:

```bash
curl -X POST http://127.0.0.1:8000/projects/<PROJECT_ID>/inventory
```

The response includes the scanned records, duplicate-hash counts, the number
of records persisted, and the number of history events created. Generated
`manifest.json` and `manifest.csv` files are evidence outputs and are excluded
from the asset database.

## Search records

Search is always scoped to one project and supports a bounded result window:

```bash
curl "http://127.0.0.1:8000/projects/<PROJECT_ID>/files/search?query=report&status=active&limit=25"
```

The `query` parameter matches file names, project-relative paths, and MIME
types. `checksum_sha256`, `media_type`, `status`, `limit`, and `offset` provide
exact filtering and pagination.

## Inspect history

Use the file identifier returned by search to inspect immutable snapshots:

```bash
curl http://127.0.0.1:8000/projects/<PROJECT_ID>/files/<FILE_ID>/history
```

The service records `created`, `updated`, `missing`, and `restored` events. A
missing file is not deleted from the database; when it reappears, its status is
restored to `active` and the new checksum and metadata are recorded.
