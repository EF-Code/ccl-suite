# Knowledge-source register

The Week 5 source register is a controlled metadata layer for documents that
may supply the company knowledge base. Document parsing, chunking, and the
first bounded semantic-search endpoint are now available. Answer generation,
source-grounded citations, and refusal behaviour remain later scheduled
activities.

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
   text, stores deterministic chunks with source locations, and materialises
   the local retrieval vector.

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

Search approved source passages for one project:

```bash
curl -X POST http://127.0.0.1:8000/projects/<PROJECT_ID>/knowledge-search \
  -H 'Content-Type: application/json' \
  -H 'X-User-ID: <PROJECT_OWNER_ID>' \
  -d '{
    "query":"How do we verify a file before restoring it?",
    "source_type":"sop",
    "sensitivity":"internal",
    "limit":5
  }'
```

The endpoint returns ranked source-linked passages, not an answer. Retrieval
is limited to approved sources whose files remain active, is scoped to the
requested project, and permits that project's owner or a supervisor/admin
operator. A denied non-owner request returns `404` and records an
`access.denied` event without storing the query text.

## Safety boundaries

- Source registration references an existing active file; it does not accept
  arbitrary document text or host paths.
- A file from another project returns `404` and cannot be registered.
- Duplicate registration of the same file in one project returns `409`.
- Pending and rejected sources are never eligible for future ingestion.
- Archived files are excluded even if their former source record was approved.
- Ingestion repeats the approved-source and active-file checks and refuses a
  source whose on-disk checksum differs from the latest inventory checksum.
- Source text and its derived local vector are stored as data in
  `document_chunks`; the pipeline does not execute document text, apply it as
  system policy, or call a model.
- Retrieval uses the approved-source and active-file boundary again rather
  than trusting a caller-supplied source identifier alone.
- The current local-hash vector is a dependency-free retrieval baseline, not a
  claim of model-level semantic understanding or production-scale ANN search.
- Security events contain only the source identifier and authenticated actor;
  request bodies and credentials are not recorded. Chunk content and its
  derived vector are stored only in the source-linked chunk table.
