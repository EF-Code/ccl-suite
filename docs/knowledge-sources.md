# Knowledge-source register

The Week 5 source register is a controlled metadata layer for documents that
may supply the company knowledge base. Document parsing and chunking are now
available as the Tuesday ingestion stage; embeddings, retrieval, and answers
remain later scheduled activities.

## Source lifecycle

1. A staff member, supervisor, or administrator registers an active file from
   one project.
2. The source is saved as `pending` and records its accountable owner, source
   type, and sensitivity.
3. A supervisor or administrator reviews the registration.
4. Only a source marked `approved` whose file is still `active` may be returned
   by `build_approved_knowledge_sources_statement` for ingestion.
5. An authorised staff member, supervisor, or administrator can ingest the
   approved file. The pipeline records its checksum, extracts bounded UTF-8
   text, and stores deterministic chunks with source locations.

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

Ingest an approved text source:

```bash
curl -X POST \
  http://127.0.0.1:8000/projects/<PROJECT_ID>/knowledge-sources/<SOURCE_ID>/ingest \
  -H 'X-User-ID: <STAFF_OR_SUPERVISOR_ID>'
```

The response contains the completed run, source checksum, chunk count, and
source-linked chunk records. Supported document types are `.txt`, `.md`, `.csv`,
and `.json`, with a maximum source size of 1 MiB. The sample source used for
the Tuesday checkpoint is
[`samples/knowledge/company-rules.md`](../samples/knowledge/company-rules.md).

## Safety boundaries

- Source registration references an existing active file; it does not accept
  arbitrary document text or host paths.
- A file from another project returns `404` and cannot be registered.
- Duplicate registration of the same file in one project returns `409`.
- Pending and rejected sources are never eligible for future ingestion.
- Archived files are excluded even if their former source record was approved.
- Ingestion repeats the approved-source and active-file checks and refuses a
  source whose on-disk checksum differs from the latest inventory checksum.
- Source text is stored as data in `document_chunks`; the ingestion pipeline
  does not execute document text, apply it as system policy, or call a model.
- Security events contain only the source identifier and authenticated actor;
  request bodies and credentials are not recorded. Chunk content is stored
  only in the source-linked chunk table for the later retrieval stage.
