# Knowledge Base Answer capability checkpoint

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
- Added the versioned `knowledge-agent-v1` instruction set and
  `grounded-answer-v1` response contract. Every response identifies its
  instruction version, contract version, and current `extractive` answer mode.
- Added runtime and Pydantic validation for status/refusal/citation invariants,
  including matching citation counts and the requirement that answered results
  contain evidence.
- Kept the user question and retrieved document passages in separate labelled
  provider inputs. Retrieved text is evidence data and cannot replace agent
  instructions.
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
bounded input, answer/refusal audit events, and the versioned response
metadata. The pure composer and contract tests cover excerpt selection,
unsupported queries, separated provider inputs, and invalid response states.

## Boundary

This checkpoint does not add an external model provider or API key. A future
provider must preserve this contract, source boundary, project access checks,
citations, refusals, and audit behaviour.
