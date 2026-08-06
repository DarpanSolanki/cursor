---
name: feedback-shared-dpi-fixture-needs-teardown
description: A scenario that mutates loan config or appends dues on a shared DPI fixture LAN must tear down, or it silently reds sibling cases
metadata:
  type: feedback
---

The DPI fixture LANs (`8060160`, `8057160`, `116360`) are shared by every `dpic.*` case. A scenario
that changes loan-level config and leaves it behind makes later cases accrue against a value that
scenario invented.

**Why:** on TDPQA-237 the new ROI-change scenario left a seeded
`loan_account_restructuring_details` row and `effective_rate = 20` on `8060160`. Every subsequent DPI
case then read a ROI change that no other scenario knew about. It cost a full round of chasing
"regressions" that were self-inflicted. Separately, `reset_dpi_fixtures.sh` purged
`dpi_accrual_details` but not billed DPI `loan_due_details`, so each billing run appended a row and
`dpic.jump_regression` drifted upward run over run (30 → 54 → 81 → 108 against a fixed 27) — a moving
failure number is the signature of accumulation, not of a code defect.

**How to apply:**
- Capture the original value **before** seeding and restore it in a `trap ... EXIT`, not at the end of
  the happy path — a mid-script `fail()` must still clean up.
- When a number in a failing assert *changes between runs*, suspect fixture accumulation before code.
- Prove a suspected regression by re-running the same case with the fix stashed
  (`git stash push -- src/main/java`) on an equally clean fixture. Identical failure = pre-existing.

Precedent: `scripts/dpic/run_dpi_roi_change_e2e.sh` teardown; DPI-due purge added to
`scripts/dpic/reset_dpi_fixtures.sh`. Related: [[feedback_sql_seeded_config_needs_cache_evict]].
