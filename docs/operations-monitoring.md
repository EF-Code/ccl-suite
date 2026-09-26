# Operations monitoring and weekly reporting

This feature adds a persistent in-app alert register and a record-derived weekly operations report to the Security page. It uses deterministic rules and database records; it does not generate an AI-written report narrative or send email, chat, or other external notifications.

## Alert rules

| Rule | Trigger | Identity and lifecycle |
| --- | --- | --- |
| Repeated failures | At least 5 `failure` or `denied` security events for the same actor and event code in a rolling 15-minute window. Ten or more starts at high severity. | One stable fingerprint per actor and event code. The observed count and last observation update when the rule is checked. |
| High-risk agent input | A handoff blocked by an instruction-override, secret-exfiltration, access-boundary-bypass, or approval-bypass rule within the last 7 days. Secret-exfiltration and approval-bypass start at critical severity; other listed blocks start high. | One alert per blocked handoff. The alert records the rule category and handoff reference, never the submitted input. |
| Overdue approval | An approval still pending at least 24 hours after it was requested. | One alert per approval. It is automatically resolved when a subsequent check finds it is no longer pending and overdue. |

Open alerts that have not been acknowledged advance to escalation level 1 after 24 hours and level 2 after 72 hours. Escalation is applied and audited the next time the rules are evaluated; there is no scheduler or background monitoring process in this release. Acknowledged alerts stop escalating. Supervisors and administrators can acknowledge or resolve alerts; those actions are recorded as security events. Repeated-failure and high-risk alerts remain available for human triage until resolved. New evidence can reopen a resolved alert; the original evidence alone does not.

The evaluator can be run from the Security page or with `POST /operations/alerts/evaluate`; this requires `security.alerts.evaluate`. Alert records are listed at `GET /operations/alerts`. Only users with `security.alerts.manage` can acknowledge or resolve them. Supervisors and administrators see organization-wide records; staff see alert records tied to their actor identity or owned projects.

## Weekly report

`GET /operations/weekly-report` returns the previous completed Monday–Sunday week in UTC. A past complete week can be selected with `week_start=YYYY-MM-DD`, which must be a Monday. The `format=csv` option downloads a two-column metric/value export; the default is JSON.

The report distinguishes period counts from current snapshots:

- Projects, workflows, workflow actions, approvals, security events, handoffs, and alerts are counted against persisted records and the report's defined UTC window. Current workflow-action statuses make pending approval-bound actions visible as pending work.
- Fields ending in `_now`, active project counts, and workflow state counts describe the database when the report was generated, not the historical end of the selected week.
- Handoff completion counts and mean duration use handoffs whose completion timestamp is within the selected week; duration is measured in seconds from handoff creation to completion.
- Security events are scoped to the authenticated actor for staff and to the organization for supervisors and administrators. Project-linked metrics use owned projects for staff.
- Open and acknowledged alerts are reported separately so triage status remains clear. Counts are not hours worked, productivity estimates, or AI conclusions. The report note repeats these interpretation limits.

The schema is introduced by Alembic revision `0016_operational_alerts`. Apply migrations with `alembic upgrade head` before deploying the updated API and frontend bundle.
