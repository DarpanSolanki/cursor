---
name: feedback_no_inmem_mutation_after_cas
description: "After a CAS transition (ChildClmtStateMachineService/LoanAccountStateMachineService.transition or patchJsonFields) on a CLMT or loan_account row, never call setters on that entity — the outer disburseLoan Hibernate context auto-flushes the stale mutation with old updated_on and reverts the CAS."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 7fc30f42-df07-4d0a-8093-68fff3c6147e
---

**No in-memory entity mutation after CAS on multi-writer rows.** After `ChildClmtStateMachineService.transition` / `LoanAccountStateMachineService.transition` / `patchJsonFields` on a CLMT or `loan_account` row, do **NOT** call setters on that entity.

**Why:** The outer `disburseLoan` Hibernate persistence context auto-flushes any in-memory mutation with a **stale `updated_on`**, reverting the atomic CAS that another writer/thread just applied (`AbstractBaseEntity` has no `@PreUpdate` to refresh the timestamp). This is the auto-flush race that the post-`4c339282f` (2026-05-07) rule closed: **CAS is the sole writer** of these state columns.

**How to apply:** Treat any `setX(...)` on a CAS-managed entity (`loan_account.disbursement_status` / `loan_status`, `loan_account_events_queue.data->>'disbursement_status'`) as a bug — fail loud in review. If a value must change, route it through the state-machine CAS or `patchJsonFields`, not a setter. Use the **`state-machine-safety`** skill before any state-column change. CLAUDE.md §0 Rule 3. Pairs with [[feedback_concurrency_contract_audit]], [[rca-workflow]].
