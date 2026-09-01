# Week 5 Tuesday checkpoint

## Planned work

- Learn: parsing, chunking, overlap, and source metadata.
- Build: extract approved documents and split them while retaining title,
  heading, project, and location information.
- Submit: document-ingestion pipeline and sample dataset.
- Safety: document text must remain data and must not replace application
  rules.

## Delivered

- Added bounded UTF-8 extraction for `.txt`, `.md`, `.csv`, and `.json` sources.
- Added MIME/extension checks, a 1 MiB source limit, binary/empty-file
  rejection, line-ending normalisation, and SHA-256 source checksums.
- Added deterministic paragraph/line-aware chunking with bounded overlap,
  Markdown heading context, project-relative source locations, line ranges,
  word/character counts, and per-chunk checksums.
- Added the approved-only
  `POST /projects/{project_id}/knowledge-sources/{source_id}/ingest` route.
- Added `ingestion_runs` and `document_chunks` persistence through migration
  `0007_document_ingestion`.
- Added checksum freshness validation, failed-run records, and source-scoped
  success/failure security events.
- Added the non-sensitive sample source at
  `samples/knowledge/company-rules.md`.

## Verification

```bash
.venv/bin/python -m pytest -q
node --check static/app.js
.venv/bin/python -m alembic upgrade head
.venv/bin/python -m alembic check
```

The focused ingestion/API/schema tests cover successful persistence, pending
source rejection, changed-source rejection, chunk metadata, and failure
recording.

## Boundary

This checkpoint intentionally stops after extraction, chunking, and persistence.
Embeddings, vector search, source-grounded answers, evaluation, and prompt-
injection testing remain scheduled for later days and are not part of this
Tuesday deliverable.
