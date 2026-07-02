---
name: feedback_concurrency_contract_audit
description: "Before any race / lost-update / stuck-row fix, enumerate every writer of the affected row → check @Version → verify each handles concurrent state. No @Version on a multi-writer row means the fix must use atomic CAS (or patchJsonFields for advisory) or an @Version migration."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 7fc30f42-df07-4d0a-8093-68fff3c6147e
---

For any race / lost-update / stuck-row bug, run a **concurrency-contract audit before proposing the fix**: enumerate **every writer** of the affected row, check whether the row has `@Version` (optimistic lock), and verify each writer handles concurrent state correctly. If a multi-writer row has **no `@Version`**, the fix MUST use atomic CAS (`ChildClmtStateMachineService` / `LoanAccountStateMachineService.transition`), or `patchJsonFields` for advisory JSON fields, or an `@Version` migration — not a plain `dao.save(entity)`.

**Why:** Without a version guard, interleaved UPDATEs are last-writer-wins, silently reverting a correct state. Fixing one writer without auditing the others just moves the race. The writer registry in the brain doc is the canonical list — if a writer is missing from it, add it (that prevents the next bug).

**How to apply:** Use the **`rca-workflow`** skill's writer-registry step and the **`state-machine-safety`** skill before any state-column change. Cross-check the brain doc's `§writer-registry`. Never call setters on a CAS-managed entity afterwards ([[feedback_no_inmem_mutation_after_cas]]). Pairs with [[rca-workflow]], [[feedback_deep_rca_before_fix]].
