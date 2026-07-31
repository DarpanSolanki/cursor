---
name: feedback_ship_credit_pass_skip_refire
description: >-
  Ship-loop credits recent ntest PASS when pending file fingerprint matches —
  skip re-fire to cut TAT. 2026-07-31.
---

# Ship-loop credit PASS (skip re-fire)

## Problem

Agents already ran money e2e (e.g. `flowtest.shg_int_accrual_stitch`) before
`workspace-close` → ship-loop re-ran the same suite (~minutes–hours TAT waste).
Discipline-stale retries re-fired green cases again.

## Fix

- `scripts/lib/ship_credit_pass.py` — fingerprint pending ship files; record on ntest PASS
- `ntest.py` `_telemetry` → `record_pass` / `clear_pass`
- `ship-loop-gate.sh` → `SKIP CREDIT` when eligible (progress PASS wall=0)

## Rules

- Default **on** (`SHIP_CREDIT_PASS=1`)
- Disable: `SHIP_CREDIT_PASS=0` or `SHIP_FORCE_REFIRE=1`
- Max age: `SHIP_CREDIT_PASS_MAX_AGE_S` (default 7200)
- Fingerprint mismatch (pending files changed) → must re-fire
- Credits file: `.cursor/.ntest-pass-credits.json` (local, not committed)

## Does not fix

- Over-wide impact selection (see `feedback_ship_loop_fc_touch_harness_blast.md`)
- Lock collisions (see flowtest lock L1)
