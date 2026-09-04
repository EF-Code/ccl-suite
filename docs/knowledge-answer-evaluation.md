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
