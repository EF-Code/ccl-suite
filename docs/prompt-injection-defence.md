# Prompt-injection defence report

## Scope

The knowledge base treats uploaded files, retrieved passages, and user
questions as untrusted data. The local answer engine does not execute document
text or call an external model, but the same boundary is enforced before a
future provider could receive the data.

## Attack coverage

The sanitized corpus in
[`samples/security/prompt-injection-cases.json`](../samples/security/prompt-injection-cases.json)
covers:

| Attack shape | Example intent | Expected result |
| --- | --- | --- |
| Direct instruction override | Ignore the agent rules or publish a new policy | Refuse without citations |
| Direct secret exfiltration | Reveal a system prompt or credential | Refuse without citations |
| Indirect document instruction | Tell the agent to disclose keys while processing a file | Block ingestion and suppress the passage |
| Access-boundary bypass | Retrieve another project's sources | Refuse; project authorization still applies |
| Benign policy wording | Document a rule that denies cross-project access | Do not flag the document |

## Controls

1. `scan_prompt_injection()` returns only bounded rule identifiers and attack
   categories; it never returns matched text.
2. Approved documents are scanned immediately after checksum verification and
   before chunk persistence. A flagged document remains on disk unchanged,
   receives a failed ingestion record, and produces a bounded denial event.
3. Retrieval suppresses flagged legacy chunks before ranking and never returns
   their content to the browser.
4. The answer composer refuses injection-shaped questions and skips flagged
   evidence even when called directly outside the HTTP route.
5. Feedback and issue reports accept only enumerated categories. They do not
   store the question, answer, evidence, hidden instructions, or raw logs.

## Acceptance gates

The security evaluation must pass every corpus case and every injection
regression case. The evaluation runner requires a 100% pass rate overall and
within each supported, refusal, conflict, and injection category.

Run the focused checks from the repository root:

```bash
~/.venv/bin/python -m pytest -q tests/test_knowledge_security.py tests/test_knowledge_evaluation.py
~/.venv/bin/python scripts/run_knowledge_security_evaluation.py
~/.venv/bin/python scripts/run_knowledge_evaluation.py
```

This is a deterministic pattern-based defence report, not a claim that a
future generative model is immune to every novel prompt-injection technique.
Any future provider must preserve the authorization, data/instruction
separation, refusal, citation, and privacy boundaries documented here.
