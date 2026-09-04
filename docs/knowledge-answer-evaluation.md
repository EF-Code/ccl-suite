# Grounded Knowledge Base Answer evaluation

## Scope

This is a fixed, local evaluation of the `local-extractive-v1` answer
composer. It uses deterministic fixture passages rather than project data or
an external model.

The suite contains 20 cases:

- 12 supported questions: an answer must have the expected, source-linked
  excerpt.
- 5 unsupported questions: the endpoint must refuse and emit no citations.
- 3 conflicting-information questions: both contradictory excerpts must remain
  visible as separate citations.

## Result

The recorded evaluation result is **20/20 passed**:

| Category | Cases | Passed |
| --- | ---: | ---: |
| Supported evidence | 12 | 12 |
| Safe refusal | 5 | 5 |
| Conflicting evidence retained | 3 | 3 |
| Total | 20 | 20 |

## Representative media operations acceptance suite

The repository also includes a clearly labelled, fictional representative
corpus for a small multi-role media company operating YouTube and TikTok
accounts. It is sanitized: it contains no real people, account handles,
credentials, private links, customer data, production media, or commercial
figures.

The end-to-end acceptance test registers, approves, and ingests the corpus in
an isolated project before exercising the live FastAPI application boundary.
Its 20 scenarios all passed:

| Category | Cases | Expected behavior |
| --- | ---: | --- |
| Supported company operations questions | 14 | Cited evidence from the intended source. |
| Missing information | 3 | Safe refusal with no citations. |
| Conflicting retention information | 2 | Both contradictory sources remain cited. |
| Wrong-project retrieval | 1 | `404` denial, no source content, and an `access.denied` event. |

Run it with:

```bash
~/.venv/bin/python -m pytest -q tests/test_main.py -k representative_media_corpus
```

The source files and human-readable acceptance matrix are in
[`samples/knowledge/representative-media-company`](../samples/knowledge/representative-media-company).

Run the evaluation directly from the repository root:

```bash
~/.venv/bin/python -m pytest -q tests/test_knowledge_evaluation.py
~/.venv/bin/python scripts/run_knowledge_evaluation.py
```

The JSON runner exits non-zero when any fixed contract fails. Its output
contains case identifiers and pass/fail metadata only; it does not print source
fixture content.

## What this verifies

- A supported answer uses the expected evidence excerpt, rather than a generic
  response.
- A refused answer has the expected refusal reason and no weak citation.
- Conflicting sources are presented together. The local composer does not
  silently choose, merge, or reinterpret contradictory rules.
- The API integration test independently verifies that two ingested,
  contradictory project sources reach the answer endpoint as two citations.

## Limits and boundary

This is a deterministic regression suite, not a claim of semantic reasoning,
conflict resolution, external-model quality, or production policy arbitration.
Project access-control and bounded-request behavior remain covered by the
endpoint test suite.

Prompt instruction handling and prompt-injection testing are deliberately out
of scope for this validation.
