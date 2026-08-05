<!-- Relocated verbatim from .cursor/rules/accounting.mdc / accounting-module-knowledge.mdc. Edit these skill topic files; thin accounting.md only routes here. -->

## Accounting Financial Signoff Gate

For any accounting bug fix/enhancement/refactor that can affect money/state/contracts, signoff is blocked unless this gate is satisfied.

## Required signoff output
Before declaring completion, provide a compact signoff with these sections:
1. **Scope changed**: files/symbols changed + what money/state outputs are affected.
2. **Impact map**: all entry points/callers/consumers checked.
3. **Risk check**: cutoff alignment, prerequisites, idempotency, replay/concurrency, contract compatibility.
4. **Evidence**: DB/test/log evidence or exact SQL/test steps requested from user if direct access unavailable.
5. **Residual risk**: any remaining assumptions and what monitoring catches them.

## Non-negotiable checks
1. No “single-path only” validation for money logic; verify all known computation/posting entry points.
2. No semantic drift in existing response fields/ExecutionContext keys without compatibility handling.
3. No retry-on-business-validation errors; retries only for transient failures.
4. No merge-ready claim without at least one negative-path or replay-path verification.

## Financial safety defaults
1. Prefer fail-fast over silent wrong-state progression.
2. Preserve auditability on every write path.
3. Keep write flows idempotent and replay-safe.
4. If uncertainty remains, call it out explicitly and stop short of “fully fixed” language.

---

## Accounting Financial Flow Preflight

Any change that affects financial figures, derived due/paid/waived state, outstanding/balance computations, or GL/posting inputs must be protected by an end-to-end preflight + impact analysis. The goal is to prevent “looks correct in code, wrong in flow” issues caused by missing prerequisites, cutoff drift, or inconsistent entry-point sequencing.

## Mandatory Impact Analysis (no skipping)
## 1) Scope and blast radius
1. Identify the exact financial outputs affected (examples: outstanding principal/interest, POS/PRIN buckets, overdue/pending buckets, extra/waived/paid split, GL line amounts, file/staging amounts).
2. Map the end-to-end data path for those outputs: DB tables/schemas -> DAO/repository -> processor/service -> writer/postTransaction -> downstream staging/APIs/files -> consumers/batches (if any).
3. Enumerate every code entry point that can compute or populate the same outputs:
   - orchestration processors and pre-processors (including stage processors)
   - writers that call `postTransaction` or populate DCF/claim staging
   - batch processors and scheduled jobs that call the same services/internal APIs
   - Kafka consumers and callbacks/inquiries that re-run or resume the flow
   - internal API endpoints used by other modules

## 2) Call-site & contract coverage
1. Find every usage/caller of the changed classes/methods/ExecutionContext keys/constants across the accounting module (and known downstream modules).
2. Verify no breaking semantic change:
   - ExecutionContext keys: are they written/read by downstream steps consistently?
   - API/response shapes: additive-only; do not change meaning of existing fields.
   - list/collection semantics: if callers assume non-empty, keep backward compatible behavior.

## 3) Cutoff/as-on date invariants (critical)
1. For every computation step, list the cutoff inputs used:
   - `job_time`, `asOnDate`, `value_date`, `date_of_death`, `dateOfReporting`, `deathDateMinusOne`, due_date boundary comparisons (`>=`, `>`, `<`, `<=`).
2. Verify all entry points that produce the final number use the same cutoff semantics for the same business meaning.
3. If different steps intentionally use different cutoffs (rare), document the reason and ensure it matches GL/posting expectations.

## 4) Prerequisites enforcement (billing/accrual/posting)
1. If the computation reads derived state (billing/accrual/posting-driven):
   - Ensure the prerequisite sync/job is executed before reading those records in every entry point.
2. If there are multiple computation entry points (preprocessor vs writer vs stage processors vs batch), ensure they all enforce the same prerequisite or all share the same prerequisite guarantee from the orchestration.
3. Confirm prerequisite parameters match the computation cutoff (same accounts list, same job time/as-on time, required audit context if the job requires it).

## 5) ExecutionContext discipline
1. List keys written/overwritten by your change; ensure downstream readers get the intended values.
2. Use `putLocal()` for transient/current-step keys; use `put()` only when downstream needs it.
3. Avoid accidental overwrites; if a key is derived, set only when missing/blank unless explicitly required.

## 6) Replay safety and lifecycle correctness
1. For write flows: confirm idempotency/dedupe/status checks exist so retries don’t double-post.
2. Verify state transitions across the lifecycle (success/failure/retry/callback/inquiry) do not regress or diverge.
3. For Kafka consumers: confirm they check current state before processing and handle partial failures.

## 7) DB safety & auditability
1. Identify which schema/tables are touched; confirm correct datasource/schema usage.
2. Confirm soft-delete rules (`is_deleted = false` on reads; soft-archive on writes) and NOT NULL constraints.
3. Ensure audit fields (`created_by/on`, `updated_by/on`, `performed_by/on` where applicable) remain correct for the run.

## 8) Failure-mode and distributed-systems checks (mandatory)
1. Partial failure analysis:
   - Identify all places where one step can commit and the next step can fail (internal API, DB write, event publish, callback dependency).
   - Define compensation/retry/idempotent re-entry behavior for each partial-failure point.
2. Concurrency analysis:
   - Check what happens for duplicate triggers, retries, parallel consumers, or maker-checker re-approvals.
   - Verify no double-posting or status regression under concurrent execution.
3. Ordering analysis:
   - Validate ordering assumptions (especially callback/inquiry vs posting, scheduler vs manual trigger, consumer replay ordering).
4. Classification analysis:
   - Ensure exceptions are correctly typed (validation/business vs transient/infrastructure) and retry policy matches error type.

## 9) Performance and data-volume safety
1. Query safety:
   - No N+1 loops in hot paths; use single/bulk queries where applicable.
   - Confirm indexed predicates for added/changed filters.
2. Batch safety:
   - Validate chunk/grid settings and memory use for large account sets.
   - Avoid loading unbounded datasets into memory.
3. Hot-path logging:
   - No noisy per-row logs in high-volume loops; keep logs structured and actionable.

## 10) Verification evidence requirements
1. DB evidence:
   - Provide before/after SQL validation for impacted outputs and status transitions.
   - Include row-level checks for due/paid/waived/posting amounts where applicable.
2. Flow evidence:
   - Verify all impacted entry points, not just one path.
   - Validate both happy path and at least one retry/replay path.
3. Contract evidence:
   - Verify all known callers still work with unchanged assumptions.
4. If live DB access is unavailable:
   - Provide exact copy-paste SQL for each impacted schema/table and request results before final signoff.

## 11) Rollback and observability readiness
1. Rollback plan:
   - Confirm safe rollback path (feature flag / reversible deployment / non-breaking schema behavior).
2. Monitoring:
   - Define what to watch post-deploy (error codes, duplicate count, stuck statuses, posting mismatches).
3. Alerting:
   - Ensure critical anomalies are detectable early (mismatch counters, unexpected retries, status drift).

## 12) Completion criteria (before you mark “done”)
1. All impacted entry points are identified and verified for cutoff/prerequisite alignment.
2. All downstream consumers/readers of affected keys/contracts are checked (no hidden semantic dependencies).
3. A short verification plan is defined (DB queries, replay tests, or running the relevant local sanity suite).
4. Failure-mode, concurrency, and replay checks are completed and documented.
5. Verification evidence exists (or exact SQL/test plan has been provided to collect it).
6. Rollback and monitoring checks are explicitly covered.

---

## Accounting Financial Signoff Gate

For any accounting bug fix/enhancement/refactor that can affect money/state/contracts, signoff is blocked unless this gate is satisfied.

## Required signoff output
Before declaring completion, provide a compact signoff with these sections:
1. **Scope changed**: files/symbols changed + what money/state outputs are affected.
2. **Impact map**: all entry points/callers/consumers checked.
3. **Risk check**: cutoff alignment, prerequisites, idempotency, replay/concurrency, contract compatibility.
4. **Evidence**: DB/test/log evidence or exact SQL/test steps requested from user if direct access unavailable.
5. **Residual risk**: any remaining assumptions and what monitoring catches them.

## Non-negotiable checks
1. No “single-path only” validation for money logic; verify all known computation/posting entry points.
2. No semantic drift in existing response fields/ExecutionContext keys without compatibility handling.
3. No retry-on-business-validation errors; retries only for transient failures.
4. No merge-ready claim without at least one negative-path or replay-path verification.

## Financial safety defaults
1. Prefer fail-fast over silent wrong-state progression.
2. Preserve auditability on every write path.
3. Keep write flows idempotent and replay-safe.
4. If uncertainty remains, call it out explicitly and stop short of “fully fixed” language.

---

## Accounting Financial Flow Preflight

Any change that affects financial figures, derived due/paid/waived state, outstanding/balance computations, or GL/posting inputs must be protected by an end-to-end preflight + impact analysis. The goal is to prevent “looks correct in code, wrong in flow” issues caused by missing prerequisites, cutoff drift, or inconsistent entry-point sequencing.

## Mandatory Impact Analysis (no skipping)
## 1) Scope and blast radius
1. Identify the exact financial outputs affected (examples: outstanding principal/interest, POS/PRIN buckets, overdue/pending buckets, extra/waived/paid split, GL line amounts, file/staging amounts).
2. Map the end-to-end data path for those outputs: DB tables/schemas -> DAO/repository -> processor/service -> writer/postTransaction -> downstream staging/APIs/files -> consumers/batches (if any).
3. Enumerate every code entry point that can compute or populate the same outputs:
   - orchestration processors and pre-processors (including stage processors)
   - writers that call `postTransaction` or populate DCF/claim staging
   - batch processors and scheduled jobs that call the same services/internal APIs
   - Kafka consumers and callbacks/inquiries that re-run or resume the flow
   - internal API endpoints used by other modules

## 2) Call-site & contract coverage
1. Find every usage/caller of the changed classes/methods/ExecutionContext keys/constants across the accounting module (and known downstream modules).
2. Verify no breaking semantic change:
   - ExecutionContext keys: are they written/read by downstream steps consistently?
   - API/response shapes: additive-only; do not change meaning of existing fields.
   - list/collection semantics: if callers assume non-empty, keep backward compatible behavior.

## 3) Cutoff/as-on date invariants (critical)
1. For every computation step, list the cutoff inputs used:
   - `job_time`, `asOnDate`, `value_date`, `date_of_death`, `dateOfReporting`, `deathDateMinusOne`, due_date boundary comparisons (`>=`, `>`, `<`, `<=`).
2. Verify all entry points that produce the final number use the same cutoff semantics for the same business meaning.
3. If different steps intentionally use different cutoffs (rare), document the reason and ensure it matches GL/posting expectations.

## 4) Prerequisites enforcement (billing/accrual/posting)
1. If the computation reads derived state (billing/accrual/posting-driven):
   - Ensure the prerequisite sync/job is executed before reading those records in every entry point.
2. If there are multiple computation entry points (preprocessor vs writer vs stage processors vs batch), ensure they all enforce the same prerequisite or all share the same prerequisite guarantee from the orchestration.
3. Confirm prerequisite parameters match the computation cutoff (same accounts list, same job time/as-on time, required audit context if the job requires it).

## 5) ExecutionContext discipline
1. List keys written/overwritten by your change; ensure downstream readers get the intended values.
2. Use `putLocal()` for transient/current-step keys; use `put()` only when downstream needs it.
3. Avoid accidental overwrites; if a key is derived, set only when missing/blank unless explicitly required.

## 6) Replay safety and lifecycle correctness
1. For write flows: confirm idempotency/dedupe/status checks exist so retries don’t double-post.
2. Verify state transitions across the lifecycle (success/failure/retry/callback/inquiry) do not regress or diverge.
3. For Kafka consumers: confirm they check current state before processing and handle partial failures.

## 7) DB safety & auditability
1. Identify which schema/tables are touched; confirm correct datasource/schema usage.
2. Confirm soft-delete rules (`is_deleted = false` on reads; soft-archive on writes) and NOT NULL constraints.
3. Ensure audit fields (`created_by/on`, `updated_by/on`, `performed_by/on` where applicable) remain correct for the run.

## 8) Failure-mode and distributed-systems checks (mandatory)
1. Partial failure analysis:
   - Identify all places where one step can commit and the next step can fail (internal API, DB write, event publish, callback dependency).
   - Define compensation/retry/idempotent re-entry behavior for each partial-failure point.
2. Concurrency analysis:
   - Check what happens for duplicate triggers, retries, parallel consumers, or maker-checker re-approvals.
   - Verify no double-posting or status regression under concurrent execution.
3. Ordering analysis:
   - Validate ordering assumptions (especially callback/inquiry vs posting, scheduler vs manual trigger, consumer replay ordering).
4. Classification analysis:
   - Ensure exceptions are correctly typed (validation/business vs transient/infrastructure) and retry policy matches error type.

## 9) Performance and data-volume safety
1. Query safety:
   - No N+1 loops in hot paths; use single/bulk queries where applicable.
   - Confirm indexed predicates for added/changed filters.
2. Batch safety:
   - Validate chunk/grid settings and memory use for large account sets.
   - Avoid loading unbounded datasets into memory.
3. Hot-path logging:
   - No noisy per-row logs in high-volume loops; keep logs structured and actionable.

## 10) Verification evidence requirements
1. DB evidence:
   - Provide before/after SQL validation for impacted outputs and status transitions.
   - Include row-level checks for due/paid/waived/posting amounts where applicable.
2. Flow evidence:
   - Verify all impacted entry points, not just one path.
   - Validate both happy path and at least one retry/replay path.
3. Contract evidence:
   - Verify all known callers still work with unchanged assumptions.
4. If live DB access is unavailable:
   - Provide exact copy-paste SQL for each impacted schema/table and request results before final signoff.

## 11) Rollback and observability readiness
1. Rollback plan:
   - Confirm safe rollback path (feature flag / reversible deployment / non-breaking schema behavior).
2. Monitoring:
   - Define what to watch post-deploy (error codes, duplicate count, stuck statuses, posting mismatches).
3. Alerting:
   - Ensure critical anomalies are detectable early (mismatch counters, unexpected retries, status drift).

## 12) Completion criteria (before you mark “done”)
1. All impacted entry points are identified and verified for cutoff/prerequisite alignment.
2. All downstream consumers/readers of affected keys/contracts are checked (no hidden semantic dependencies).
3. A short verification plan is defined (DB queries, replay tests, or running the relevant local sanity suite).
4. Failure-mode, concurrency, and replay checks are completed and documented.
5. Verification evidence exists (or exact SQL/test plan has been provided to collect it).
6. Rollback and monitoring checks are explicitly covered.

---

