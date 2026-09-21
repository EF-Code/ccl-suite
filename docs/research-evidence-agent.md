# Research Evidence Agent

This document describes the research-evidence capability delivered through
21 September 2026. It covers evidence-field design, claim extraction,
configurable applicability checks, a bounded warning register, and the
durable human review and publication workflow.

## Purpose

The capability creates a bounded evidence preview from source-shaped text. It
does not call an external LLM and does not require an API key. The local
extractor classifies text without inventing claims, while the scope checker
compares only fields explicitly supplied by the caller.

## Evidence schema

Every extracted claim contains the following fields:

| Field | Meaning | Boundary |
| --- | --- | --- |
| `claim_id` | Opaque identifier for this claim | Retained inside a submitted review package |
| `claim` | One bounded claim-sized text unit | Maximum 500 characters |
| `classification` | `factual`, `heading`, `instruction`, `opinion`, or `creative` | Deterministic classification only |
| `source_title` | Human-readable source name | Required metadata |
| `source_reference` | URL, DOI, path, or other source reference | Required metadata |
| `source_date` | Date supplied for the source | Optional; never inferred |
| `passage` | Exact trimmed source line containing the claim | Retained for comparison and later review |
| `scope` | Model year, engine, market, population, setting, and evidence type | Optional, allow-listed fields |
| `review_status` | Current review state | Preview claims start as `needs_review`; persisted claims can become `changes_requested` or `verified` |

The response envelope is versioned as `research-evidence-v1` and includes the
project ID, source metadata, scope, claim count, and validated claim list.

## Example validated claim

```json
{
  "claim_id": "2c7e3b0e-0c4c-4a65-a2e3-1f4a25e4c1f5",
  "claim": "The vehicle uses a hybrid engine.",
  "classification": "factual",
  "source_title": "Vehicle field study",
  "source_reference": "local://vehicle-field-study",
  "source_date": "2026-09-14",
  "passage": "The vehicle uses a hybrid engine.",
  "scope": {
    "model_year": 2024,
    "engine": "hybrid",
    "market": "Nigeria",
    "population": null,
    "setting": null,
    "evidence_type": "field study"
  },
  "review_status": "needs_review"
}
```

The claim and passage are deliberately separate: the claim is the bounded
classification unit, while the passage is the source context that must be
checked before any later approval.

## Example scope result

```json
{
  "schema_version": "research-evidence-v1",
  "project_id": "8e7c3b0e-0c4c-4a65-a2e3-1f4a25e4c1f5",
  "claim_id": "2c7e3b0e-0c4c-4a65-a2e3-1f4a25e4c1f5",
  "claim_classification": "factual",
  "status": "uncertain",
  "reason": "A requested scope field is missing or unclear in the source.",
  "fields": [
    {"field": "model_year", "status": "match", "requested": "2024", "observed": "2024"},
    {"field": "engine", "status": "uncertain", "requested": "electric", "observed": null}
  ]
}
```

The live API includes all six field rows; the abbreviated example highlights
the important distinction between a known match and an unresolved field.

## Workflow

```text
Source text + title/reference/date/scope
                 |
                 v
        Untrusted-input safety gate
                 |
                 v
   Deterministic line and sentence parsing
                 |
                 v
 Classification: factual / heading / instruction /
                 opinion / creative
                 |
                 v
        Pydantic response validation
                 |
                 v
       needs_review evidence preview
                 |
                 v
  Six-field applicability comparison (optional)
                 |
                 v
      applicable / mismatch / uncertain /
              not_applicable
                 |
                 v
      completeness and consistency warnings
                 |
                 v
        durable review package
                 |
                 +--> correction request (reopens claim)
                 |
                 +--> human verification for every claim
                 |
                 v
              approval gate
                 |
                 v
       CSV / JSON / Markdown export
```

The extraction response is validated before it is returned. A preview is not
approved evidence. When a reviewer submits it, the package and its exact
source passages are persisted for a bounded human review. Approval is blocked
until every claim has a recorded verification action.

## Applicability checks

`POST /projects/{project_id}/research/claims/check-scope` evaluates these
fields in order:

1. `model_year`
2. `engine`
3. `market`
4. `population`
5. `setting`
6. `evidence_type`

The comparison is case-insensitive for text and exact for values. Explicit
wildcards such as `worldwide` are accepted. A missing, blank, or explicitly
unknown source value produces `uncertain`; it is never guessed. If a target
field is omitted it is reported as `not_requested`. A factual claim with no
target fields is also `uncertain`, because applicability has not been
established. Headings, instructions, opinions, and creative text return
`not_applicable` rather than being treated as facts.

## Evidence register

`POST /projects/{project_id}/research/evidence-register` accepts the current
validated claim preview and returns deterministic warning categories without
persisting or approving the claims. Optional expected source metadata and a
target scope make source alignment checks explicit rather than inferred.

The register can report:

- `missing_evidence` when a factual claim has no usable source title,
  reference, passage, or requested scope context.
- `source_mismatch` when claim source metadata or requested scope differs from
  the register context.
- `duplicate_claim` when the same factual claim appears more than once.
- `conflict` when explicit positive and negative factual statements share a
  deterministic polarity signature.
- `unsupported_claim` when the factual claim is not present in its retained
  exact source passage.

Each claim receives `supported`, `needs_review`, or `not_applicable`. The
`supported` label means only that these bounded checks found no warnings; it
is not human verification or approval. Every source claim remains tied to its
exact passage and is carried into the durable review package unchanged.

## Human review and publication

`POST /projects/{project_id}/research/reviews` creates a review package from
the current validated claim preview. The server recomputes the warning
register instead of trusting a client-supplied assessment. The package keeps
the source metadata, target scope, claim provenance, and an append-only event
history.

Reviewers can request a correction for an individual claim, optionally
including proposed replacement wording or scope. The correction returns the
claim to `changes_requested` and clears any previous verification or package
approval. A reviewer then calls the verification route for each claim. The
package becomes `verified` only when every claim is verified.

`POST /research/reviews/{review_id}/approve` is the final human gate. It
returns a conflict response if any claim is still awaiting review. Only an
approved package can be downloaded from the export route. CSV includes one
row per claim, JSON includes the complete review history, and Markdown is a
readable publication copy. Each export is recorded as an event without
copying the source text into an audit record.

## API surface

- `POST /projects/{project_id}/research/claims/extract` accepts bounded source
  metadata, source text, and optional source scope, then returns the validated
  preview.
- `POST /projects/{project_id}/research/claims/check-scope` accepts one
  validated claim and a target scope, then returns field-level comparisons.
- `POST /projects/{project_id}/research/evidence-register` checks a bounded
  claim list for missing evidence, source mismatches, duplicates, conflicts,
  and unsupported wording, then returns claim assessments and warning details.
- `POST /projects/{project_id}/research/reviews` submits a validated claim set
  to the durable human-review queue.
- `GET /projects/{project_id}/research/reviews` lists the project's review
  packages; `GET /research/reviews/{review_id}` returns one package.
- `POST /research/reviews/{review_id}/claims/{claim_id}/correction` records a
  correction request and reopens the affected claim.
- `POST /research/reviews/{review_id}/claims/{claim_id}/verify` records human
  verification for one claim.
- `POST /research/reviews/{review_id}/approve` approves only a fully verified
  package.
- `GET /research/reviews/{review_id}/export?format=csv|json|markdown` exports
  only an approved package.

The preview, register, and review-read routes require the existing
`knowledge.read` permission and apply the same project-owner or
supervisor/administrator boundary as the knowledge base. Correction requests
require `workflow.manage`; verification, approval, and export require
`approval.decide`. Unsafe instruction-shaped input receives a bounded `422`
response. Raw source text is retained only inside the project-scoped review
claim when the user explicitly submits it for review; audit events contain
only bounded action notes and opaque IDs.

## Safety behavior

- Source text, source metadata, claim text, passages, and scope strings are
  treated as untrusted input and pass through the existing prompt-injection
  gate.
- Request and response models reject unknown fields and enforce bounded sizes.
- The extractor returns no generated source facts: it only classifies text
  already supplied by the caller.
- Scope comparison uses exact values, case-insensitive text comparison, and
  explicit wildcard values. It does not infer a market, population, setting,
  or evidence type from the claim wording.

## Verification checklist

The implementation is exercised at three layers:

```bash
~/.venv/bin/python -m pytest -q tests/test_research_evidence.py
~/.venv/bin/python -m pytest -q tests/test_main.py -k research
RUN_BROWSER_TESTS=1 ~/.venv/bin/python -m pytest -q tests/test_dashboard_browser.py
```

The browser check covers project selection, source metadata entry, claim
preview, factual-claim selection, an applicable scope result, and a conflict
warning register, human review submission, claim verification, approval, and
the three export controls.
