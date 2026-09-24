# Agent Security Test Report

## Scope

This report covers the deterministic, in-process specialist handoff prototype
and its interaction with workflow state, approval records, project access, and
persisted traces. The specialists do not call an external language-model
provider, execute arbitrary code, or perform destructive operations.

Tests use synthetic project data and an isolated in-memory database. No live
service credentials or company source documents are used.

## Results

| Security case | Verification evidence | Result |
| --- | --- | --- |
| Specialist responsibilities and tool boundaries | `tests/test_agent_orchestration.py::test_specialists_have_distinct_responsibilities_and_bounded_tools`; result-schema tests | Each role has a distinct responsibility; outputs cannot claim an undeclared tool or metric. |
| Delegation outside the approved graph | `tests/test_agent_orchestration.py::test_delegation_edges_are_allow_listed`; `tests/test_main.py::test_specialist_guardrails_trace_blocked_injection_and_bad_delegation` | Unapproved edges and missing completed source handoffs are recorded as blocked. |
| Instruction override and secret extraction | `tests/test_agent_orchestration.py::test_agent_input_blocks_secret_extraction_and_approval_bypass`; `tests/test_main.py::test_specialist_guardrails_trace_blocked_injection_and_bad_delegation` | Inputs are blocked before specialist execution; traces omit the submitted text. |
| Unsafe paths, IDs, and operations | `tests/test_agent_orchestration.py::test_agent_input_rejects_injection_and_traversal_without_raw_trace_text`; `tests/test_main.py::test_specialist_guardrails_trace_blocked_injection_and_bad_delegation` | Unix, Windows-drive, and traversal paths fail validation; malformed workflow IDs and unregistered operations return validation errors. |
| Approval bypass attempt | `tests/test_main.py::test_specialist_handoff_cannot_bypass_human_approval_or_leak_context` | The handoff is blocked, the linked publish action remains pending approval, and the blocked attempt is traceable without its raw context. |
| Credential-bearing or malformed output | `tests/test_agent_orchestration.py::test_agent_result_rejects_unstructured_or_secret_bearing_output`; `tests/test_main.py::test_specialist_handoff_fails_closed_on_credential_bearing_output` | Output validation fails closed; the response and stored trace contain no unsafe result. |
| Unauthorized tools or incomplete role metrics | `tests/test_main.py::test_specialist_handoff_fails_closed_on_unauthorized_tool_output`; `tests/test_main.py::test_specialist_handoff_fails_closed_on_incomplete_metric_schema` | Invalid specialist output is marked failed and persisted with an empty result and generic summary. |
| Cross-project access | `tests/test_main.py::test_specialist_handoff_cannot_cross_project_access_boundary` | A workflow identifier outside the caller's project access returns the standard not-found response. |
| Trace privacy and outcome linkage | `tests/test_main.py::test_specialist_handoff_cannot_bypass_human_approval_or_leak_context`; `tests/test_main.py::test_specialist_agents_return_project_scoped_results_and_traces` | Success and blocked handoffs have trace IDs; stored input is represented by a fingerprint and safe summary, with a corresponding security event. |

The focused verification command completed with **22 passed**:

```text
~/.venv/bin/python -m pytest -q tests/test_agent_orchestration.py tests/test_main.py -k 'agent or specialist'
```

The repository-wide suite completed with **335 passed, 2 skipped**. The skips
are the opt-in live-browser suite and the PostgreSQL integration suite, which
require their dedicated local services and credentials.

## Limits and follow-up

Prompt and credential detection is pattern-based; it is a defense-in-depth
filter, not a guarantee that arbitrary natural-language attacks or unknown
secret formats will be detected. Trace fingerprints are plain SHA-256 digests,
not encrypted or keyed values; low-entropy inputs may be guessable if the
database is exposed, so credentials must not be sent as handoff context. The
specialist implementation is deterministic and does not establish the safety
of a future model provider or external tool integration. Any such integration
needs a separate permission boundary, provider-specific threat review, and
tests against that implementation.

This report records local automated tests. It is not a production penetration
test, an independent security certification, or a claim that the full platform
has no vulnerabilities.
