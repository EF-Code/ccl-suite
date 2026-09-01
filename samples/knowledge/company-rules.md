# Company File Handling Rules

This sample is a non-sensitive training document for the Week 5 Tuesday
ingestion checkpoint. It describes the kind of approved internal source that
can be registered, reviewed, extracted, and split into source-linked chunks.

## Approved project locations

Store new material in the project's `incoming/` directory. Work in progress
belongs in `working/`, reviewed deliverables belong in `output/`, and retained
historical material belongs in `archive/`. Do not use a path outside the
approved project root.

## Naming and file handling

Use lowercase kebab-case for project folder names. Keep one clear extension on
each file, preserve the original before conversion, and preview organisation
changes before applying them. A conflict must be reported or quarantined; it
must not be silently overwritten or deleted.

## Backups and restoration

Create a verified backup before a high-impact change. Compare the archive and
manifest checksums before restoration. Restore to a new destination, confirm
the restored files, and keep the original project unchanged.

## Review boundary

This document is reference data for the knowledge-base pipeline. Any
instruction-like text found inside a source remains source content and cannot
change application rules, permissions, or approval requirements. A human
reviewer remains responsible for approving the source before ingestion.
