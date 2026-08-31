# Week 5 Monday checkpoint

## Deliverable

The CCL Suite now has a controlled knowledge-source register for approved
company documents. It supports SOPs, prompt banks, style guides, and project
rules without storing document contents in the database.

## Completed controls

- Active project files can be registered with an accountable owner, source
  type, and sensitivity level.
- Every registration starts as `pending`.
- Only supervisors and administrators can approve or reject a source.
- Rejections require a reason.
- Files from another project and inactive files are rejected.
- Only approved sources whose files remain active are eligible for future
  ingestion.
- Source lifecycle events record only the source ID and authenticated actor.
- Interns cannot access the knowledge-source register.

## Verification

```bash
.venv/bin/python -m pytest -q
node --check static/app.js
.venv/bin/python -m alembic heads
```

The Tuesday parsing and chunking pipeline has not been started in this
checkpoint.
