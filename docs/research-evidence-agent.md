# Research Evidence Agent

This document describes the research-evidence capability delivered for the
14–16 September 2026 slice of the project plan. It covers evidence-field
design, claim extraction, and configurable applicability checks. Human review,
verification, correction comments, and export are intentionally outside this
slice.

## Purpose

The capability creates a bounded evidence preview from source-shaped text. It
does not call an external LLM and does not require an API key. The local
extractor classifies text without inventing claims, while the scope checker
compares only fields explicitly supplied by the caller.

## Evidence schema

Every extracted claim contains the following fields:

| Field | Meaning | Boundary |
| --- | --- | --- |
| `claim_id` | Opaque identifier for this preview item | Generated for the response; not a database record |
| `claim` | One bounded claim-sized text unit | Maximum 500 characters |
| `classification` | `factual`, `heading`, `instruction`, `opinion`, or `creative` | Deterministic classification only |
| `source_title` | Human-readable source name | Required metadata |
| `source_reference` | URL, DOI, path, or other source reference | Required metadata |
| `source_date` | Date supplied for the source | Optional; never inferred |
| `passage` | Exact trimmed source line containing the claim | Retained for comparison and later review |
| `scope` | Model year, engine, market, population, setting, and evidence type | Optional, allow-listed fields |
| `review_status` | Current review state | Always `needs_review` in this slice |

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
```

The extraction response is validated before it is returned. Nothing from this
workflow is persisted as approved evidence. The exact source passage remains
attached to the claim so a later reviewer can compare source and claim before
any approval decision.

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

## API surface

- `POST /projects/{project_id}/research/claims/extract` accepts bounded source
  metadata, source text, and optional source scope, then returns the validated
  preview.
- `POST /projects/{project_id}/research/claims/check-scope` accepts one
  validated claim and a target scope, then returns field-level comparisons.

Both routes require the existing `knowledge.read` permission and apply the
same project-owner or supervisor/administrator boundary as the knowledge base.
Unsafe instruction-shaped input receives a bounded `422` response. Raw source
text is not placed in audit records, and no extraction output is saved at this
stage.

## Deliberate boundary

This slice does not implement reviewer approval, evidence corrections,
verification status, or CSV/JSON/Markdown export. Those actions require a
separate review and publication contract so that a preview cannot be mistaken
for approved company evidence.
