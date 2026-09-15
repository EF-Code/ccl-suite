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
- Added four prompt-injection regression cases covering direct instruction
  overrides, secret requests, unsafe document evidence, and access bypasses.
- Added explicit 100% pass-rate gates for supported, refusal, conflict, and
  injection categories.
- Documented the 24/24 result and the benchmark limitations in
  `knowledge-answer-evaluation.md`.
- Added and executed a 20-scenario representative media operations corpus
  through registration, approval, ingestion, retrieval, answer composition,
  refusal, and cross-project denial.

## Verification

```bash
~/.venv/bin/python -m pytest -q tests/test_knowledge_evaluation.py tests/test_knowledge_answer.py
~/.venv/bin/python -m pytest -q tests/test_main.py -k knowledge_answer
~/.venv/bin/python scripts/run_knowledge_evaluation.py
```

The fixed suite passed all 24 cases: 12 supported, 5 refusal, 3 conflict, and
4 injection-boundary cases.

The representative end-to-end suite also passed all 20 scenarios: 14 supported
operations questions, 3 missing-information refusals, 2 conflict cases, and 1
wrong-project security denial.

## Boundary

This validation does not claim conflict resolution; it preserves conflicting
evidence for a human or a future policy layer to resolve. The injection checks
are deterministic pattern-based defenses, not a guarantee against every novel
attack on a future generative provider.
