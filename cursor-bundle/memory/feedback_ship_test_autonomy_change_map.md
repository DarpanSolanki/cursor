# Feedback: ship-test autonomy — change → impact cases on push

**When:** 2026-07-23  
**Trigger:** SP-308 notification ship pushed after compile-only; pending froze wrong cases; push skipped close on knowledge HEAD while money pending remained.

## Permanent contract

1. **Edit** → `after-ship-path-edit.sh` → `register_pending_ship.register_paths` (smart `ntest_cases` via `build_impact`).
2. **Close/push** → `resolve_ship_impact` **always re-resolves** path→api→cases (ignore frozen weak `registry_cases` unless `SHIP_HONOR_EXPLICIT_CASES=1`).
3. **Money tier** → zero ntest cases = **FAIL** (no health/smoke fallback).
4. **Map SoT** → `scripts/lib/change_test_map.json` + `change_test_map.py` (class/path → registry apiName). Never invent `disburseLoan` or raw `*BatchService` stems.
5. **Domains** → penal / advance / installment-notification are separate; token-boundary matching so `penalinterest*` ≠ interest accrual.
6. **Fingerprints** → `ship-loop-passed.json` fingerprints vs current files; edit after PASS requires re-close.
7. **push-origin** → knowledge-only HEAD skips auto-close **only if pending is also knowledge-only** (`--skip-auto-close-knowledge`). From a service repo, sets `SHIP_CLOSE_REPO` so close scopes pending (no full-workspace money suite on a train push).
8. **post-commit** → writes `.last-ship-commit` + re-registers HEAD ship paths + queues `ship-test-auto` for service/money.
9. **fc_touch / BY_LATEST** → harness `scripts/testing/foreclosure/*` and prepayment **read** DAO must not force-full FC+DCF (`feedback_ship_loop_fc_touch_harness_blast.md`). Use foreclosure `read_impact_cases`.

## Agent rule

Do **not** `git push` service repos after `compileJava` alone. Use `push-origin.sh` / `workspace-close.sh --from-pending` so impacted registry cases run.

## 2026-07-23 reconcile — DYNAMIC layer
SoT is now `scripts/lib/impact_tests.py` over live KG (written-table siblings + topics).
`change_test_map.json` = seed/override only. Ship blocked without `--mark-ran` (or waiver).
