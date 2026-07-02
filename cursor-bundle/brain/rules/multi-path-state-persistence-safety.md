---
description: Multi-path state persistence safety (general + disbursement queue/JSON layers)
globs:
  - "**/*.java"
  - "**/*.xml"
alwaysApply: false
---

# Multi-path state persistence safety (general)

Many production “stuck / duplicate / not progressed” bugs happen because the same business state can be persisted via **multiple entry points**, but the fix is applied to only one path.

This rule applies to **any** bug fix or behavior change that updates **state** (DB rows, status fields, workflow flags, queue rows), not just disbursement.

## Mandatory checklist before calling a fix “done”

### 1) Identify the state you are changing

- Which table/entity/aggregate is the source of truth?
- Which fields represent lifecycle state? (status enums, stage flags, retry counters, error codes/messages)
- Are there *multiple layers* of state (e.g., a row-level `status` plus embedded JSON status, or a parent status gated by child rows)?

### 2) Enumerate ALL persistence paths for that same state

At minimum, check these categories and explicitly list the entry points you found:

- **HTTP API** orchestration requests (including “internal API” calls)
- **Callback** handlers (bank/payment/webhooks)
- **Inquiry / poller / retry-job** paths (including post-processors after external calls)
- **Kafka consumer** paths (at-least-once delivery implies replays)
- **Batch/scheduler** jobs that pick “pending” rows
- **Manual override / LAR / backoffice** update APIs

If more than one path can “finish” the same lifecycle, the fix must keep them consistent.

### 3) Enforce invariants across paths

For each persistence path, confirm these invariants are true:

- **Terminal-state consistency**: terminal business state must imply terminal queue/workflow state (e.g., if embedded payload says COMPLETED, the row must not remain PENDING).
- **Idempotency**: re-entry should not double-post/double-disburse/double-publish. Verify dedupe keys / status checks.
- **Parent/child gating**: if parent progression depends on child rows, ensure the child completion flag used by the gate is correctly set in every path.
- **Auditability**: updated fields have correct timestamps/actor fields; errors are preserved where needed.

### 4) Evidence requirement (for RCAs)

For “it happened but status didn’t change” incidents, always collect evidence for:

- **DB**: before/after row snapshots of the exact fields that drive progression (include `updated_on`)
- **Logs**: the entry point that ran (API/consumer/job) and the commit/build if available

If logs show a path ran but DB state didn’t move, suspect “updated one layer but not the gating layer” or “updated in one path but not the other path”.

## Practical tip

When you fix a bug in one place, spend 5 minutes asking: “Where else can this same state be written?”
If you don’t answer that, the fix is not complete.

---

# Disbursement multi-path persistence safety

When changing any disbursement/NEFT/MFT code that updates status or `loan_account_events_queue` rows, you MUST treat “state persistence” as a multi-path problem.

## Mandatory multi-path trace (no skipping)

For the same business outcome (e.g. “child disbursement completed”), identify and verify all paths that can persist state:

- **Callback path**: bank hits callback API → callback processor updates queue/loan tables.
- **Inquiry + post-processor path**: system initiates inquiry / bank call returns → WebClient post-processor updates queue/loan tables.
- **Batch path**: `childLoanEventProcessingBatchJob` picks pending queue rows and runs ORC processors.
- **Manual/LAR path**: manual override processors that update queue + parent status.

Do not assume only one of these runs in production; logs often show both callback and inquiry in the same lifecycle.

## Invariant to enforce (queue vs embedded JSON)

`loan_account_events_queue` has TWO layers of state:

- **Row state**: `event_status` (`P`/`C`) — drives batch pickup + parent-sync gating.
- **Embedded JSON**: `data.disbursement_status` (`NEFT_STAGE_*`, `DTFC_SUCCESS`, `COMPLETED`, …) — drives stage routing and UI/debugging.

**Rule**: if embedded `data.disbursement_status` transitions to terminal `COMPLETED` for a child, then the queue row must transition to `event_status='C'` in every path that performs that transition. If a path intentionally keeps `event_status='P'`, it must also keep `data.disbursement_status` non-terminal and document why.

## Required grep checklist (before declaring a fix “done”)

For any change touching CLMT/NEFT/MFT completion, search and review these entry points:

- `DoGenericSyncSTPBankNeftCallBackProcessor` (NEF/NEI callback)
- `PostNEFTChildLoanBankDisbursementProcessor` + `ChildNeftClmtPostBankService` (NEFT inquiry/post-processor)
- `PostMFTChildLoanBankDisbursementProcessor` (MFT post-processor)
- `ChildLoanEventProcessingItemProcessor` (batch queue completion)
- `ParentGroupDisbursementStatusSyncService` (parent transitions gated on CLMT/CLB completion)
- `UpdateChildLoanDisbursementStatusProcessor` (manual/LAR override)

## Evidence requirement

For any bug report like “bank callback came but CLMT still P”, collect evidence for BOTH layers:

- Queue row: `event_status`, `updated_on`, `filler_2` (external_ref), `event_type`
- Embedded JSON: `data.disbursement_status`, `external_error_code/message`

If `updated_on` is after the callback/inquiry time and `event_status` is still `P`, suspect a path that updated JSON but not `event_status`.
