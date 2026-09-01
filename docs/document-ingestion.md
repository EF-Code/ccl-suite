# Document ingestion

This is the Week 5 Tuesday pipeline. It processes one approved project source
into bounded, deterministic text chunks for a later retrieval stage. It does
not create embeddings, search vectors, generate answers, or call an AI model.

## Processing flow

1. Inventory a regular project file so its size, MIME type, and SHA-256 checksum
   are recorded.
2. Register the file as a knowledge source. New registrations start as
   `pending`.
3. Have a supervisor or administrator approve the source.
4. Call the ingestion endpoint. The service checks that the source is still
   approved, its file is still active, and its on-disk checksum matches the
   latest inventory record.
5. The service reads bounded UTF-8 text and creates deterministic overlapping
   chunks. Each chunk keeps the source title, active Markdown heading, project
   relative location, line range, word/character counts, and content checksum.

## Supported sources

The Tuesday stage accepts `.txt`, `.md`, `.csv`, and `.json` files up to 1 MiB.
Files must use an allow-listed MIME type, contain valid UTF-8 text, and be
regular files inside the approved project root. Empty, binary, symlinked,
oversized, or changed sources are rejected.

## Ingest an approved source

```bash
curl -X POST \
  http://127.0.0.1:8000/projects/<PROJECT_ID>/knowledge-sources/<SOURCE_ID>/ingest \
  -H 'X-User-ID: <STAFF_OR_SUPERVISOR_ID>'
```

The response contains the completed `ingestion_run`, its source checksum, the
chunk count, and the persisted source-linked chunks. Failed processing is
recorded as a failed run and returns a safe error without returning raw source
content in the error message.

## Sample dataset

[`samples/knowledge/company-rules.md`](../samples/knowledge/company-rules.md)
is a non-sensitive training source. It can be copied into an approved project's
`incoming/` directory, inventoried, registered, approved, and ingested using
the normal workflow.

## Safety boundary

The pipeline treats document text as untrusted reference data. It never
executes source text, changes application rules, grants permissions, or bypasses
approval. The source checksum and chunk content are retained for traceability;
interpretation and retrieval controls belong to later stages of the plan.
