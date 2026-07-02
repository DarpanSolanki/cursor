# Flow — Maker-checker (the meta-pattern)

## Mental model

Most state-changing operations in the platform are gated by a **maker-checker** workflow. Maker submits → approval service stores a draft + workflow row → checker reviews and approves/rejects. On approve, the **same Request** is re-fired with `function_code=APPROVE`, and the target service's processor pipeline runs the actual mutation.

The approval service is **content-agnostic** — it doesn't know what the target Request does. It only knows: where to send the request when approved, what JSON to send, who can approve.

## Services involved

- Originating service (accounting / LOS / actor / payments / task)
- approval (workflow + replay)
- task (operator pickup task — optional, configured per use-case)
- actor (`getUserDetails` for maker/checker info)
- masterdata (`getUseCaseDetails` for use-case master)
- audit (framework auto)

## Step-by-step

### Phase 1 — Maker submits

```
Operator clicks "Save" on a maker-side form (e.g. Create GL)
  ▼
gateway → accounting:createOrUpdateGeneralLedger (function_code=DEFAULT, function_sub_code=DEFAULT)
  ▼
Orchestration runs (maker_checker_enabled=1 branch):
  1. accounting_getUserDetails → actor          (maker info)
  2. getUserDetailsPostProcessor
  3. accounting_getUseCaseDetails → actor       (use-case master, e.g. GENL-LEDG-UC001)
  4. getUseCaseDetailsPostProcessor
  5. checkDataFor* validators
  6. fetchBulkUniqueMasterData                   (friendly labels for audit)
  7. sendForApproval*PreProcessor
       ─ emits AuditData{ entity_type=SEND_FOR_APPROVAL_*, new_data=… }
  8. accounting_submitApplication → approval:submitApplication
       INSERT mfi_approval.draft_application + application
         target_api_name = "createOrUpdateGeneralLedger"
         target_payload  = original request body
         status          = PENDING
         maker_user_id   = current user
  9. deleteDraftProcessor (clear local draft cache)
 10. accounting_getNotificationMessage → notifications
 11. setUserStoryForResponseProcessor
 12. dummyProcessor → response_code = 30003 ("sent for approval")
```

Result: a `mfi_approval.application` row in PENDING; an audit row (`SEND_FOR_APPROVAL_*`); optionally a task in `mfi_task.task` for the checker to pick up.

### Phase 2 — Checker reviews

```
Checker fetches their pending approval queue:
  approval:getApplicationList
    → returns rows for the checker's role / hierarchy

Checker reviews and clicks Approve:
  approval:approveApplication
    ─ marks application APPROVED
    ─ calls back into the originating service:
         callInternalAPI(target_api_name, target_payload)
         with function_code=APPROVE on the request
```

Or Reject:
```
approval:rejectApplication
    ─ marks application REJECTED
    ─ no target call; emits notification
```

Or Send back for clarification:
```
approval:sendApplicationForClarification
    ─ marks application CLARIFICATION
    ─ task fires back to maker
    ─ maker can RESUBMIT (function_code=RESUBMIT)
```

### Phase 3 — Target service replays

```
gateway → accounting:createOrUpdateGeneralLedger (function_code=APPROVE)
  ▼
Orchestration runs (different branch — APPROVE):
  1. populateCurrentDateProcessor
  2. dummyProcessor (maps user_id, current_date)
  3. createGeneralLedgerProcessor (the actual DAO write)
  4. accounting_getNotificationMessage
  5. setUserStoryForResponseProcessor
  6. dummyProcessor → response_code = 30000 (success)
```

The state change happens here. From the user's POV, the GL was created on the checker's approve action.

## How the same Request handles both branches

The orchestration XML uses `<Control method="regExp" pattern="${function_code}" condition="=" value="DEFAULT|APPROVE|RESUBMIT">` to wrap the maker / approve / resubmit branches. Inside each branch a different processor list runs.

Toggle for the whole pattern: `<Control method="regExp" pattern="${maker_checker_enabled}" condition="=" value="0|1">` — when 0, the maker-checker branch is skipped and the domain processor runs inline.

## Where the use-case lives

The `getUseCaseDetails` call against actor returns metadata for codes like `GENL-LEDG-UC001`, `INTL-ACCT-DEFN`, etc. Each use case defines:
- Which roles can be makers / checkers
- Whether maker-checker is enabled (overrides the tenant default)
- Notification routing
- Task assignment rules

## The application row — why idempotency matters on APPROVE

`approveApplication` re-invokes the original Request. If the maker-side flow had partial side effects (e.g. wrote a row that the APPROVE branch then tries to re-write), the APPROVE branch must tolerate them. Most processors handle this with "if exists update else insert" semantics; a few rely on the maker-side branch being side-effect-free (only validators + draft).

## Variants

- **`RESUBMIT`** — maker re-sends after a clarification request. Same `application_id`; payload may have changed.
- **Bulk maker-checker** — `bulkBatchSubmitApplication` (batch service) submits a bulk file for approval; on approve, the bulk apply job runs.
- **Task-driven maker-checker** — some workflows create a `mfi_task.task` row for the checker on submit; the task is closed on approve/reject via `updateTaskStatus`.

## DB writes summary

| Table | When |
|---|---|
| `mfi_approval.draft_application` | submit (deleted on approve/reject) |
| `mfi_approval.application` | submit (status flips on approve/reject) |
| `mfi_approval.application_attachment` | submit (links to dms documents) |
| `mfi_audit.audit_log` | submit (`SEND_FOR_APPROVAL_*`) + approve/reject (action) |
| `mfi_task.task` | submit (if use-case configured to create one) |

## Failure modes

| Symptom | Cause |
|---|---|
| Stuck PENDING forever | No checker action — push the operator |
| Approved but state didn't change | APPROVE branch threw mid-pipeline; check app log around approve timestamp |
| No application row | Maker-side Request failed before `submitApplication` ran |
| Unauthorized to approve | Checker role doesn't match use-case checker config |
| Duplicate `application` row | submitApplication called twice (maker double-clicked); idempotency on STAN should prevent |

## When you'll touch this

- Wiring a new maker-checker use-case → seed actor's use-case master + add `_submitApplication` `<API>` call inside the originating Request.
- Disabling maker-checker for a use-case → set `${maker_checker_enabled}` config in masterdata.
- Investigating "approval pending forever" → join `mfi_approval.application` ↔ `mfi_task.task`.

## Code anchors

- approval Requests: [`novopay-platform-approval/deploy/application/orchestration/ServiceOrchestrationXML.xml`](../../novopay-platform-approval/deploy/application/orchestration/ServiceOrchestrationXML.xml)
- accounting maker side: every `createOrUpdate*` Request in accounting wraps with `${maker_checker_enabled}` Control
- Use-case master: actor service

## Where to dig deeper

- Architecture overview: [`../accounting/02-architecture.md`](../accounting/02-architecture.md) §"Path A"
- Approval service brain: [`../services/novopay-platform-approval.md`](../services/novopay-platform-approval.md)
