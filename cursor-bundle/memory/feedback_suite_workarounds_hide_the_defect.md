---
name: feedback_suite_workarounds_hide_the_defect
description: A suite flag that routes around a failing production path keeps the defect alive — fix the path, never the test
metadata:
  type: feedback
---

# Routing the suite around a broken path keeps the bug in production

**Date:** 2026-08-04 · **Ticket:** TDPQA-72 · **Train:** accounting `mfi_integration_v3.4.2.4`

`flowtest.loan_prepayment_fc` carried this header and setting:

> "Vikram loanPrepayment parent AUTO settle hits 134207."
> `os.environ["ICF_USE_LOAN_PREPAYMENT"] = "0"`

So the suite stopped exercising `loanPrepayment` — the **production** entry that triggers the parent
RSCH — and used `individualChildLoanForeclosure` instead, which posts only the child leg. The 134207
was a genuine missing `placeholder -> internal_account_definition` mapping on the parent catalogue.
Because the suite avoided the path, the parent posted **₹5,021 of ₹22,385** in production-shaped runs
for months and every test stayed green.

**Why:** a failing production path is evidence, not an obstacle. Switching the test to a path that
does not reproduce it converts a red into a permanent blind spot, and the greens then actively argue
the flow is fine.

**How to apply:**

1. When a test opts out of a path with a flag or comment naming an error code, treat that code as an
   **open defect**, not test config. Grep for `USE_`/`SKIP_`/`_ENTRY=` switches whose comment cites an
   error number.
2. Never assert the substitute path proves the real one. `individualChildLoanForeclosure` posting a
   correct child leg says nothing about the parent RSCH.
3. Config gaps are defects. A missing placeholder/IAD row or a missing accounting rule is not
   "environment" — reference codes with no rule are dropped silently by
   `ExecuteTransactionRulesProcessor`, which iterates rules, not emitted codes.
4. Balanced does not mean complete. Every leg is internally balanced, so double-entry passes while
   money is stranded. Assert the funding account is **fully drawn**
   (`assert_child_fc_parent_rsch_gl.py::termination_suspense_fully_drawn`).

Related: [[feedback_gates_must_be_provably_failable]],
[[feedback_money_behavior_parity_no_amount_only_ship]], [[feedback_child_cg_gl_vs_parent_named]].
