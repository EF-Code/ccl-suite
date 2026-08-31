# Knowledge-source register

The Monday Week 5 deliverable is a controlled register for documents that may
later supply the company knowledge base. It is deliberately a metadata layer;
document parsing, chunking, embeddings, and retrieval are later scheduled
activities.

## Source lifecycle

1. A staff member, supervisor, or administrator registers an active file from
   one project.
2. The source is saved as `pending` and records its accountable owner, source
   type, and sensitivity.
3. A supervisor or administrator reviews the registration.
4. Only a source marked `approved` whose file is still `active` may be returned
   by `build_approved_knowledge_sources_statement` for future ingestion.

Rejection requires a reason. Rejected sources remain visible in the project
register for auditability but are excluded from the approved-source query.

## API

Register a source without sending document text:

```bash
curl -X POST http://127.0.0.1:8000/projects/<PROJECT_ID>/knowledge-sources \
  -H 'Content-Type: application/json' \
  -H 'X-User-ID: <STAFF_ID>' \
  -d '{
    "file_id":"<FILE_ID>",
    "owner_id":"<OWNER_ID>",
    "title":"Customer support SOP",
    "source_type":"sop",
    "sensitivity":"internal"
  }'
```

List all registered source metadata for one project:

```bash
curl http://127.0.0.1:8000/projects/<PROJECT_ID>/knowledge-sources \
  -H 'X-User-ID: <STAFF_ID>'
```

Approve a pending source as a supervisor or administrator:

```bash
curl -X POST \
  http://127.0.0.1:8000/projects/<PROJECT_ID>/knowledge-sources/<SOURCE_ID>/review \
  -H 'Content-Type: application/json' \
  -H 'X-User-ID: <SUPERVISOR_ID>' \
  -d '{"decision":"approved"}'
```

## Safety boundaries

- Source registration references an existing active file; it does not accept
  arbitrary document text or host paths.
- A file from another project returns `404` and cannot be registered.
- Duplicate registration of the same file in one project returns `409`.
- Pending and rejected sources are never eligible for future ingestion.
- Archived files are excluded even if their former source record was approved.
- Security events contain only the source identifier and authenticated actor;
  request bodies, document contents, and credentials are not recorded.
- Document text cannot replace system rules. Tuesday's ingestion pipeline must
  preserve this approval filter and treat system instructions as higher
  priority than retrieved material.
