# Knowledge access control

Knowledge retrieval is authorized before the search query touches the
retrieval candidate set. Authorization is a server-side decision; the answer
composer and any future model provider cannot grant access.

## Decision order

1. Resolve the authenticated actor from `X-User-ID` (or the local development
   fallback).
2. Require the `knowledge.read` permission from the server-side role matrix.
   An intern is denied even when the intern is recorded as the project owner.
3. Apply the project boundary before loading chunks:
   - staff/member may read only a project they own;
   - supervisor/reviewer and administrator are global knowledge operators; and
   - unknown roles and every other cross-project staff request are denied.
4. Retrieve only source-linked records that still satisfy every data boundary:
   the chunk, source, and file belong to the requested project; the source is
   approved; the file is active; and the ingestion run is completed.
5. Apply the allow-listed source-type, sensitivity, and source-ID filters
   supplied by the request.

The access decision is implemented in
[`knowledge_access.py`](../knowledge_access.py) and is called by both the
semantic-search and grounded-answer routes before retrieval. Keeping the
policy separate makes its role rules directly unit-testable and prevents a
new retrieval entry point from silently inventing a different project rule.

## Denied requests

A request that fails the project boundary returns `404 Project was not found.`
This avoids confirming whether a caller can discover another project. The
server records a bounded `access.denied` event containing only the authenticated
actor and request path. Query text, source content, document titles, and
credentials are not written to the denial event.

Permission failures such as an intern calling a knowledge route are rejected
by the same server-side permission gate and use the same audit convention.

## Scope table

| Actor | `knowledge.read` | Owned project | Other projects |
| --- | --- | --- | --- |
| Administrator | Yes | Read | Read |
| Supervisor/reviewer | Yes | Read | Read |
| Staff/member | Yes | Read | Denied |
| Intern | No | Denied | Denied |
| Unknown role | No | Denied | Denied |

Project scope does not override source sensitivity or lifecycle controls.
Approved status, active-file status, completed ingestion, and the request's
allow-listed sensitivity filter remain mandatory for every actor.
