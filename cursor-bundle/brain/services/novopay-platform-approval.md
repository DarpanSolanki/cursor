# `novopay-platform-approval` — Maker-checker engine

> Provides the maker-checker workflow capability used by every accounting CRUD, plus LOS underwriting/disbursement, actor employee changes, and several payments operations. Owns drafts, application workflow state, and the **target-API replay** that fires when the checker approves.

## Identity

| Field | Value |
|---|---|
| Java root package | `in.novopay.approval` |
| DB schema | `mfi_approval` |
| Repo | [`novopay-platform-approval/`](../../novopay-platform-approval/) |
| Service CLAUDE.md | [`novopay-platform-approval/CLAUDE.md`](../../novopay-platform-approval/CLAUDE.md) |

## API surface

| XML | Lines | Purpose |
|---|---:|---|
| `ServiceOrchestrationXML.xml` | 480 | Core workflow |
| `orc_mfi.xml` | 185 | MFI extras |

**Core 8 Requests** (`ServiceOrchestrationXML.xml`):
- `createOrUpdateDraftApplication` — maker creates a draft (target API + payload)
- `deleteDraftApplication` — maker discards before submit
- `submitApplication` — **the entry point** every other service calls
- `getApplicationCount`, `getApplicationList` — checker dashboard
- `sendApplicationForClarification` — checker bounces back to maker
- `approveApplication` — **executes the target API**
- `rejectApplication` — closes without execution

**MFI extras** (`orc_mfi.xml`): `updateApplication`, `updateAssigneeByTaskId`, `checkIfApplicationIsPending`, `getApprovalApplicationListCriteriaBased`, `updateAooApplicationDetailsNewApprover`.

## Kafka

Producer: `producer_id_approval`. **No consumers.**

## Outbound HTTP

- masterdata (`getUseCaseDetails` for use-case master)
- actor (`getUserDetails` for maker/checker info)
- dms (`verifyDocuments` for application attachments)
- notifications (`getNotificationMessageByNotificationCode` for response copy)
- **The target API itself** — when `approveApplication` fires, it calls back into whatever service originated the draft (almost always accounting)

## Inbound — every maker-checker entry point

Every accounting Request that has `<API id="…_submitApplication">` (see [`../accounting/04-cross-module-deps.md`](../accounting/04-cross-module-deps.md) §approval). Plus LOS underwriting and disbursement, actor employee/office updates.

## DB clusters

| Cluster | Tables |
|---|---|
| Drafts | `draft_application` — maker-side WIP; deleted on submit/discard |
| Workflow | `application` — pending/approved/rejected; holds target API name + payload + checker info |
| Attachments | `application_attachment` — links to dms-stored docs |
| Use-case mirror | `user_story` — local cache of use-case codes |

## How it works

```
Service X (e.g. accounting) wants to make a state change with maker-checker
  ▼
1. Maker hits Request createGeneralLedger (function_code=DEFAULT)
  ▼
2. Accounting orchestration runs validators + sendForApprovalGeneralLedgerPreProcessor
  ▼
3. Accounting calls API id="accounting_submitApplication"  →  approval.submitApplication
  ▼
4. submitApplication INSERTs draft_application + application
   - target_api_name = "createOrUpdateGeneralLedger"
   - target_payload  = original request body
   - status          = PENDING
   - returns response_code 30003 ("sent for approval")
  ▼
5. (Time passes; checker reviews via getApplicationList)
  ▼
6. Checker hits approveApplication (or rejectApplication)
  ▼
7. approveApplication calls back into accounting:
   - same Request name (createOrUpdateGeneralLedger)
   - function_code=APPROVE
   - same payload
  ▼
8. Accounting orchestration sees function_code=APPROVE → skips approval branch,
   runs the actual createGeneralLedgerProcessor → response_code 30000
```

## Concept owned

**Drafts + workflow + target-API replay.** The approval service is *content-agnostic* — it doesn't know what `createOrUpdateGeneralLedger` does. It only knows: (a) where to send the request when approved, (b) the JSON to send, (c) who can approve.

## Known gotchas

1. **Target-API idempotency is critical.** `approveApplication` calls the original Request again. If the maker-side flow had partial side-effects, the approve-side must tolerate them.
2. **Maker-checker is per-use-case-action.** Toggle is `${maker_checker_enabled}` checked inside each accounting Request; values are tenant-config driven.
3. **Draft / application data must stay aligned** — the application row carries the payload that gets replayed, so any maker-side mutation between draft creation and approval must update both.
4. **No Kafka consumers** — purely sync/HTTP.
