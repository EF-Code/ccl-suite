# Week 5 Wednesday checkpoint

## Planned work

- Learn: vector databases, similarity search, and metadata filters.
- Build: store chunk vectors and retrieve the best passages for a question.
- Submit: a working semantic-search endpoint.
- Safety: retrieval must be filtered by project and user access.

## Delivered

- Added a deterministic, dependency-free local embedding baseline with a fixed
  256-dimensional feature space. It is isolated behind
  `semantic_search.py` so a reviewed embedding provider can replace it later.
- Added nullable embedding metadata to `document_chunks` through migration
  `0008_semantic_search`; new ingestion runs persist vectors with their chunks.
- Added `POST /projects/{project_id}/knowledge-search` with a bounded query,
  a maximum result window of 20, and allow-listed source-type, sensitivity,
  and source-ID filters.
- Added deterministic cosine ranking and newest-ingestion deduplication.
- Re-materialise missing or invalid vectors during search so chunks created by
  the Tuesday migration remain searchable without exposing an indexing route.
- Enforced the approved-source, active-file, project, and completed-ingestion
  boundaries in the retrieval query.
- Restricted staff retrieval to the project owner; supervisor and
  administrator roles act as the current global project operators. Denied
  access returns `404` and records only a bounded `access.denied` event.

## Verification

```bash
~/.venv/bin/python -m pytest -q
~/.venv/bin/python -m alembic check
node --check static/app.js
docker compose config --quiet
docker compose up -d --build
curl -sS http://127.0.0.1:8000/health
```

The endpoint tests cover ranked passage retrieval, metadata filters, pending
and archived-source exclusion, project-boundary denial, bounded validation,
and lazy indexing of pre-existing chunks.

## Boundary

This checkpoint stops at retrieval. It does not generate answers, add source
citations to an assistant response, implement refusal behaviour, run the
20-question evaluation set, or add prompt-injection tests scheduled for later
days.

The local-hash vector is a portable retrieval baseline for this milestone. It
is not a claim of model-level semantic understanding or production-scale
approximate-nearest-neighbour search.
