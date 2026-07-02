# SDCP JIRA custom fields (novopay.atlassian.net)

Project: **SDCP** (SLI During CUG / POST CUG). Issue type: **Task** (`10428`).

Refresh field list when JIRA admin changes screens:

```text
getJiraIssueTypeMetaWithFields(cloudId=novopay.atlassian.net, projectIdOrKey=SDCP, issueTypeId=10428)
```

## Fix handoff fields

| Display name | Field key | Type | Notes |
|--------------|-----------|------|-------|
| RCA | `customfield_11137` | textarea → ADF | Business language; 3 short paragraphs |
| Impact Analysis Details | `customfield_11138` | textarea → ADF | Bullet list; 4 items typical |
| Dev Test Details | `customfield_11901` | textarea → ADF | **Dev scenarios only** + Result per item |
| Test scenarios executed | `customfield_11937` | textarea → ADF | Short labels; mirror dev scenarios |
| Test results (Pass/Fail) | `customfield_11938` | textarea → ADF | One line summary |
| MICRO Service | `customfield_11337` | multicheckboxes | `[{"id": "<optionId>"}]` — see mapping below |
| Pre Deploymenet and Post Deployment Script | `customfield_11336` | textarea → ADF | **One field** — use Pre/Post sub-lines; `NA` when none |

## MICRO Service option IDs

| Checkbox label | Option id |
|----------------|-----------|
| Task | 11840 |
| Inital Set up | 11841 |
| Payments | 11842 |
| Accounting | 11843 |
| LOS | 11844 |
| Actor | 11845 |
| BPMN | 11846 |
| Reporting | 11847 |
| Lib | 11848 |
| sli-android | 11849 |
| Batch | 11850 |
| API Gateway | 11851 |
| Approval | 11852 |
| Audit | 11853 |
| Authorization | 11854 |

### Repo → checkbox (common)

| Workspace repo folder | Check |
|-----------------------|-------|
| `novopay-platform-accounting-v2` | Accounting |
| `novopay-mfi-los` | LOS |
| `novopay-platform-payments` | Payments |
| `novopay-platform-actor` | Actor |
| `novopay-platform-batch` | Batch |
| `novopay-platform-api-gateway` | API Gateway |
| `novopay-platform-lib` | Lib |
| `novopay-platform-task` | Task |
| `novopay-platform-approval` | Approval |
| `novopay-platform-audit` | Audit |
| `novopay-platform-authorization` | Authorization |

Multiple services touched → check all that apply. Lib change that ships only inside a service still check **Lib** + consuming service if both repos changed.

## Pre / Post deployment (single field)

JIRA has **one** textarea (`customfield_11336`), not two separate fields. Always use this structure:

```text
Pre deployment: NA
Post deployment: NA
```

When scripts exist, replace `NA` with a one-line purpose per section; SQL/scripts belong here, not in RCA/Impact/Dev.

## MCP call

```text
editJiraIssue(
  cloudId=novopay.atlassian.net,
  issueIdOrKey=SDCP-12345,
  contentFormat=adf,
  fields={ ... }
)
```

**Never** use `contentFormat: markdown` on textarea custom fields — API rejects it.

## ADF rules (spacing)

- **Do not** emit empty `paragraph` nodes (`content: []`) — causes large gaps in JIRA UI.
- RCA: 3 `paragraph` blocks max (situation, cause, resolution).
- Impact: one `bulletList`.
- Dev Test Details: one `orderedList` with Result in each item.
- Pre/Post: two `paragraph` lines or a 2-item `bulletList`.

Helper: `scripts/bin/jira-fix-adf.py`
