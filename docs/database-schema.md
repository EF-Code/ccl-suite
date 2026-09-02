# Database schema

Normalized PostgreSQL-compatible schema. Foreign keys express
ownership and lifecycle, while indexes support searchable file records and
audit queries.

```mermaid
erDiagram
    USER ||--o{ PROJECT : owns
    USER ||--o{ FILE : uploads
    USER ||--o{ WORKFLOW : creates
    USER ||--o{ BACKUP : creates
    USER ||--o{ APPROVAL : requests
    USER ||--o{ APPROVAL : decides
    USER ||--o{ SECURITY_EVENT : causes
    USER ||--o{ KNOWLEDGE_SOURCE : owns
    PROJECT ||--o{ FILE : contains
    FILE ||--o{ FILE_HISTORY : records
    FILE ||--o{ FILE_VERSION : versions
    PROJECT ||--o{ WORKFLOW : defines
    PROJECT ||--o{ BACKUP : stores
    PROJECT ||--o{ KNOWLEDGE_SOURCE : registers
    FILE ||--o{ KNOWLEDGE_SOURCE : references
    PROJECT ||--o{ INGESTION_RUN : processes
    KNOWLEDGE_SOURCE ||--o{ INGESTION_RUN : ingests
    PROJECT ||--o{ DOCUMENT_CHUNK : contains
    KNOWLEDGE_SOURCE ||--o{ DOCUMENT_CHUNK : supplies
    INGESTION_RUN ||--o{ DOCUMENT_CHUNK : produces
    WORKFLOW ||--o{ APPROVAL : requires

    USER {
        UUID id PK
        string external_ref UK
        string role
        datetime created_at
        datetime updated_at
    }
    PROJECT {
        UUID id PK
        UUID owner_id FK
        string name
        string storage_slug UK
        string description
        string status
        datetime created_at
        datetime updated_at
    }
    BACKUP {
        UUID id PK
        UUID project_id FK
        UUID created_by_id FK
        string artifact_key UK
        string manifest_key UK
        bigint archive_size_bytes
        int file_count
        bigint total_bytes
        string archive_checksum_sha256
        string manifest_checksum_sha256
        string status
        datetime created_at
        datetime verified_at
        datetime restored_at
        datetime updated_at
    }
    FILE {
        UUID id PK
        UUID project_id FK
        UUID uploaded_by_id FK
        string storage_key
        string name
        string extension
        string media_type
        bigint size_bytes
        string checksum_sha256
        datetime modified_at
        string status
        datetime created_at
        datetime updated_at
    }
    FILE_HISTORY {
        UUID id PK
        UUID file_id FK
        string event_code
        string storage_key
        string name
        string extension
        string media_type
        bigint size_bytes
        string checksum_sha256
        datetime modified_at
        string status
        datetime observed_at
    }
    FILE_VERSION {
        UUID id PK
        UUID file_id FK
        int version_number
        string storage_key
        string media_type
        bigint size_bytes
        string checksum_sha256
        datetime modified_at
        boolean is_original
        datetime created_at
    }
    KNOWLEDGE_SOURCE {
        UUID id PK
        UUID project_id FK
        UUID file_id FK
        UUID owner_id FK
        UUID created_by_id FK
        UUID reviewed_by_id FK
        string title
        string source_type
        string sensitivity
        string approval_status
        string rejection_reason
        datetime reviewed_at
        datetime created_at
        datetime updated_at
    }
    INGESTION_RUN {
        UUID id PK
        UUID project_id FK
        UUID source_id FK
        string source_checksum_sha256
        string status
        int chunk_count
        string error_message
        datetime created_at
        datetime completed_at
    }
    DOCUMENT_CHUNK {
        UUID id PK
        UUID ingestion_run_id FK
        UUID project_id FK
        UUID source_id FK
        int chunk_index
        string title
        string heading
        string location
        int line_start
        int line_end
        text content
        int character_count
        int word_count
        string checksum_sha256
        json embedding_json
        string embedding_model
        int embedding_dimensions
        datetime created_at
    }
    WORKFLOW {
        UUID id PK
        UUID project_id FK
        UUID created_by_id FK
        string name
        string status
        int version
        datetime created_at
        datetime updated_at
    }
    APPROVAL {
        UUID id PK
        UUID workflow_id FK
        UUID requested_by_id FK
        UUID approved_by_id FK
        string status
        string decision_code
        datetime requested_at
        datetime decided_at
    }
    SECURITY_EVENT {
        UUID id PK
        UUID actor_id FK
        string event_code
        string outcome
        string resource_type
        string resource_ref
        string request_ref
        datetime occurred_at
    }
```

## Design notes

- `users.external_ref` is an opaque identity reference. The database does not
  store passwords, access tokens, email addresses, or profile records.
- `files` stores searchable metadata, the latest SHA-256 checksum, and a
  lifecycle status. File contents remain in the approved filesystem boundary.
- `file_history` stores immutable metadata snapshots for `created`, `updated`,
  `missing`, and `restored` inventory events; it never stores file contents.
- `file_versions` provides a per-file version number and immutable metadata
  reference. Each file can have one original version and later versions without
  changing the original record.
- `backups` stores generated relative artifact keys, manifest/archive checksums,
  byte counts, status, and lifecycle timestamps. Archive bytes remain outside
  the database and outside the project source tree.
- `knowledge_sources` registers only metadata for active project files. Its
  `pending`, `approved`, and `rejected` review state prevents unreviewed files
  from entering knowledge-base ingestion. No document contents are stored in
  this table.
- `ingestion_runs` records each bounded extraction attempt, the source checksum,
  status, chunk count, and a safe failure message. A run is linked to one
  approved source and project.
- `document_chunks` stores deterministic source text chunks with title,
  heading, line location, counts, a content checksum, and the derived local
  retrieval vector. The content and vector are untrusted data; they are not
  system policy or executable input.
- `workflows` are versioned per project with a unique `(project_id, name,
  version)` key. `approvals` are separate records so each decision has its own
  lifecycle and actor references.
- `security_events` is structured and intentionally small. It stores event and
  resource references, not raw request bodies, credentials, IP addresses, or
  user-agent strings.
- Project, file, and workflow relationships use cascading deletion within a
  project. Actor references use `SET NULL` so an identity record can be removed
  without destroying audit history.
- Indexes cover project ownership/status, file lookup by project/status,
  file-history lookup by file/time, workflow status, approval status, and
  backup lookup by project/status and time, ingestion lookup by project/source
  and time, chunk lookup by project/source/index, and security-event lookups by
  actor/code and time.

## Migration

Set `DATABASE_URL` in the shell or a local environment file, then apply the
latest migrations:

```bash
export DATABASE_URL='postgresql+psycopg://localhost/ccl_suite'
.venv/bin/python -m alembic upgrade head
```

The migration creates tables and constraints only; it does not insert personal
data or seed credentials.
