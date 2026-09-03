# Week 5 Thursday checkpoint

## Planned work

- Learn: source attribution, structured responses, and refusal behaviour.
- Build: answer from retrieved evidence and cite the source document.
- Submit: Knowledge Base Agent MVP.
- Safety: refuse unsupported answers instead of inventing rules.

## Delivered

- Added `POST /projects/{project_id}/knowledge-answer` as the next layer above
  the existing project-scoped semantic-search boundary.
- Added a bounded answer request with the same source-type, sensitivity, and
  source-ID filters as retrieval, plus an evidence window capped at eight
  passages.
- Added a dependency-free `local-extractive-v1` answer composer. It selects
  short, query-overlapping excerpts from passages that clear the answer score
  threshold; it does not call a model or interpret document text as policy.
- Added structured numbered citations with source ID, title, file identity,
  heading, line range, location, score, and a bounded excerpt.
- Added explicit `answered` and `refused` states. Unsupported or low-confidence
  questions return a safe refusal with no weak citations.
- Recorded answer and refusal audit events without storing the question,
  request body, or source content.
- Added the production Knowledge Base Answer tab with an evidence rail and a
  clear refusal state. The two local frontend handover documents remain
  untouched and uncommitted.

## Verification

```bash
~/.venv/bin/python -m pytest -q
pnpm --dir frontend build
docker compose config --quiet
docker compose exec -T api python -m alembic check
```

The API tests cover cited answers, low-confidence refusal, project access,
bounded input, and answer/refusal audit events. The pure composer tests cover
excerpt selection and unsupported queries.

## Boundary

This checkpoint does not include Friday's 20-question evaluation report,
conflicting-information benchmark, or Week 6 prompt-instruction and
prompt-injection work.
