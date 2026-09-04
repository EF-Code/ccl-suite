# Representative Media Operations Evaluation Cases

Run these questions against an isolated Project Aurora evaluation project after
the listed sources have been approved and ingested. The expected behavior is a
contract: answers cite the named evidence, refusals contain no citations, and
conflicts remain visible rather than being resolved by the system.

| ID | Scenario | Question | Expected result | Evidence |
| --- | --- | --- | --- | --- |
| 01 | Supported | What must be verified before restoring a media asset? | Answer with checksum verification. | Content Production SOP |
| 02 | Supported | Can a restored asset replace the original project asset? | Answer that it must restore to a new empty destination. | Content Production SOP |
| 03 | Supported | Who approves a review copy before publication? | Answer: the team lead. | Content Production SOP |
| 04 | Supported | Where should an editor place a review copy? | Answer: the project review folder. | Content Production SOP |
| 05 | Supported | What happens after a checksum mismatch? | Answer: report it and do not publish. | Content Production SOP |
| 06 | Supported | Which comments should a manager hide? | Answer: spam, impersonation attempts, and abusive comments where tools permit. | Community Management SOP |
| 07 | Supported | Which credible safety threats, legal claims, or account-access reports need escalation? | Answer: credible safety threats, legal claims, or account-access reports. | Community Management SOP |
| 08 | Supported | Which passwords, recovery codes, payment details, or private contacts must not be requested? | Answer: passwords, recovery codes, payment details, or private contacts. | Community Management SOP |
| 09 | Supported | What should every short-form script open with? | Answer: an audience-relevant hook. | Script Style Guide |
| 10 | Supported | Which uncertain claims need editorial review instead of confirmed facts? | Answer: mark them for editorial review. | Script Style Guide |
| 11 | Supported | Who may retrieve Project Aurora knowledge sources? | Answer: owner, team lead, or administrator. | Project Aurora Rules |
| 12 | Supported | Who can approve a knowledge source? | Answer: team lead or administrator. | Project Aurora Rules |
| 13 | Supported | Can a prompt-bank template change application permissions? | Answer: no. | Approved Prompt Bank |
| 14 | Supported | What should a comment template do with a request for payment information? | Answer: do not request or repeat it; escalate. | Approved Prompt Bank |
| 15 | Missing information | What is the current subscriber count? | Refuse with no citations. | None |
| 16 | Missing information | What is the office electricity bill? | Refuse with no citations. | None |
| 17 | Missing information | When will the office relocate? | Refuse with no citations. | None |
| 18 | Conflict | How long should completed campaign source records be retained? | Cite both the seven-year and three-year rules; do not choose one. | Retention Rules A and B |
| 19 | Conflict | Should the system resolve the conflicting retention rules automatically? | Refuse to invent a resolution or present both sources if retrieved. | Retention Rules A and B |
| 20 | Wrong-project security | Retrieve Project Aurora sources while authenticated as another project's member. | Deny access and record `access.denied`; return no source content. | Project Aurora Rules |
