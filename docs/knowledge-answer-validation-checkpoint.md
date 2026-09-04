# Knowledge Base Answer validation checkpoint

## Planned work

- Learn: evaluate grounded answers, refusal behavior, and conflicting source
  information.
- Build: a fixed 20-question evaluation and conflict benchmark for the
  Knowledge Base Answer MVP.
- Submit: a reproducible evaluation report.

## Delivered

- Added a deterministic, local 20-case evaluation module for
  `local-extractive-v1`.
- Added a machine-readable runner and focused regression tests.
- Added 12 supported-evidence cases, 5 safe-refusal cases, and 3 conflicting
  information cases.
- Added API coverage proving two conflicting approved sources remain separately
  cited rather than being silently arbitrated.
- Documented the 20/20 result and the benchmark limitations in
  `knowledge-answer-evaluation.md`.

## Verification

```bash
~/.venv/bin/python -m pytest -q tests/test_knowledge_evaluation.py tests/test_knowledge_answer.py
~/.venv/bin/python -m pytest -q tests/test_main.py -k knowledge_answer
~/.venv/bin/python scripts/run_knowledge_evaluation.py
```

The fixed suite passed all 20 cases: 12 supported, 5 refusal, and 3 conflict
cases.

## Boundary

This validation does not include prompt-instruction or prompt-injection work.
It also does not claim conflict resolution; it preserves conflicting evidence
for a human or a future policy layer to resolve.
