---
name: feedback_batch_assert_timing_and_coverage_lookup
description: "Four mistakes made while covering EOD/BOD batch jobs, each of which produced a confident wrong answer. Assert timing, coverage lookup, generic error codes, and staging with -A while agents write."
metadata:
  node_type: memory
  type: feedback
---

Four errors from the 2026-08-07/08 EOD/BOD coverage push. Each produced a green or a citation
that looked right. Check for these reflexively.

**1 — A batch trigger returns 200 before the job runs. Assert AFTER `COMPLETED`, never at the call.**

`ntest` evaluated `db_eq` immediately after the HTTP trigger, so every batch DB assert was reading
the state the PREVIOUS run had left. The four money cases passed anyway, because their jobs are
idempotent and the prior state already satisfied the assert — which is exactly why nobody caught
it. Fixed: `DEFERRED_RULE_TYPES = {"file_exists", "file_row_count", "db_matches_path"}` wait for
`wait_batch` to report `COMPLETED`.

Generalise: **any assert on work a request kicks off asynchronously must be deferred.** If a
green is explainable by the previous run, it is not evidence.

**2 — `COMPLETED` with `read=0` is not "nothing to do". Compare against the job's own plan.**

A partitioned job stores its candidate count as `batch_record_count` in
`mfi_batch.batch_job_execution_params` (column `parameter_value`, varchar — there is no
`long_val`). `ntest` now compares it against `read_count` on every batch case, unconditionally.
On 2026-08-07 `loanInstallmentDueNotificationJob` reported `planned=112 read=0` and shipped
green — that is GAP-095.

Limits, both real: it catches **total** loss only (37-of-38 still passes), and it covers **34 of
60** jobs — the ones that record a plan. Pinned by `scripts/lib/test_batch_read_plan.py`.

**3 — Check the `api` field, not the case id, before calling a job uncovered.**

A case was written for `loanInstallmentDueNotificationJob` that already existed as
`batch.loan_installment_due_notification`. The "uncovered" list matched job names against case
**ids**. Three other jobs matched the same way — those turned out to be `type: flow`,
`verify_mode: WORKSPACE_ONLY` KG-presence placeholders that assert nothing, so the new cases were
genuine upgrades, but the lookup was still wrong.

```bash
python3 -c "import json,collections;r=json.load(open('scripts/testing/registry.json'));\
a=collections.defaultdict(list);[a[v['api']].append(k) for k,v in r.items() if isinstance(v,dict) and v.get('api')];\
print({k:v for k,v in a.items() if len(v)>1})"
```

**4 — `333` is a generic fallback, not a validator code. Same for any code with hundreds of throw sites.**

I attributed `generateNocFileJob`'s `333/FAIL` to two product-JSON validators because they were
the only two `throw new Novopay*Exception("333")` sites in accounting. But `333` is
`NovopayAPIConstants.UNEXPECTED_ERROR_CODE`, written by `ServiceOrchestrator:73-78` for **any**
exception that is not a `NovopayFatalException`/`NovopayNonFatalException` — ~357 sites. The job's
orchestration has no validators at all. The real cause was a plain `RuntimeException`
(`BatchRuntimeException` from `Files.createDirectories`) missing the specific catch.

Generalise: **before citing a throw site for an error code, check whether the code is generic.**
`kg_error <code>` returns every site; if it returns hundreds, the code is a fallback and the site
list is not the answer. Grepping for two and naming them is a guess dressed as a citation.

**5 — Do not `git add -A` while subagents are writing.**

Commit `b4f7abe` swallowed an agent's in-progress KG work under a message about something else.
Stage explicit paths.

## Pairs with

`.cursor/rules/40-knowledge-upkeep.mdc` (presence-only is not an assert; the local DB is not the
source of truth) · `.cursor/rules/run-the-real-thing-locally.mdc` (red before green) ·
`feedback_money_behavior_parity_no_amount_only_ship.md`
