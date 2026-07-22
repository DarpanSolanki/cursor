---
name: feedback_qa_acceptance_not_subset_verify
description: Never mark RESOLVED/Pass/handoff when asserts allow the exact QA fail mode; QA acceptance shape (not a passing subset) is the bar across ANY money/flow
---

# QA acceptance is the bar — a passing subset is NOT "verified"

Triggered 2026-07-17 (SDCP-10199 / TDPQA-72). Darpan got embarrassed in QA: the flow
functionally worked (child close / parent RSCH / DFC_PRTL_BILL) but **acceptance was broken**
and the e2e was written to *pass around* the exact things QA rejected.

## What actually failed (genuine, not false alarm)

- **Obs1 (force-bill / EMI labd):** parent force-bill not visible the way billing QA expects;
  EMI `labd` `transaction_reference_number` overwritten while billing amounts still look like EMI.
  Our `assert_force_bill_labd` only checked "a labd linked to `DFC_PRTL_BILL_*` exists" — it did
  **not** detect the EMI-hijack / no-dedicated-force-bill-visibility case QA saw.
- **Obs2 (amount ≠ principal):** parent RSCH `original_amount` ≠ payment `principal_amount`
  (e.g. 11550 vs 11605). Our assert printed **"OK A2 netting"** and passed whenever
  `expected_extra > 0` — i.e. the assert *explicitly allowed the QA fail mode*.

## Standing rules (apply to EVERY money/flow — not TDPQA-72 only)

1. **No RESOLVED/Pass/handoff if the assert allows the exact QA fail mode.** If a test prints
   "OK …" / "WARN …" for a state QA rejects, that is a **FAIL**, not a Pass. Fix the assert to
   fail, or split it behind an explicit **debug-only** flag that is OFF by default.
2. **Acceptance shape, not subset.** A green subset e2e (loan CLOSED, txn exists) is **not Done**
   while the acceptance shape QA cites (amount == principal OR documented components; force-bill
   labd visible without EMI hijack; parent-scope force-bill present) is unproven.
3. **`amount == component` must be Pass or Out-of-scope-documented.** If `principal > txn_amount`
   is real product behaviour, it must be **documented components** (which legs make up the delta),
   not a silent "netting OK". Default the test to **strict fail**; only a debug flag
   (`ALLOW_A2_NETTING_DISPLAY_DIFF=1`) may relax it, and that flag never ships a handoff Pass.
4. **EMI-overwrite / hijack path must be a fixture.** Money asserts must run the dirty /
   pre-existing state path (e.g. pre-existing EMI labd on the death-cycle installment), not only
   the clean happy path.
5. **"Webapp verified" requires the fields QA cites.** Do not claim UI verified unless the exact
   screen fields (statement amount, force-bill visibility) were checked — partial ≠ verified.
6. **Product-scope items (e.g. parent force-bill) must be Pass or explicitly Out-of-scope**, never
   silently dropped from the assert set.

## Adversarial fixture matrix (money ships)

Every money e2e must cover, or explicitly document Out-of-scope:

| Path | Why |
|------|-----|
| happy path | baseline |
| dirty / pre-existing state | QA sees production rows, not clean seeds (EMI labd already present) |
| UI-component equality | `amount == principal`/component; delta only if components documented |

## Enforcement (fail-closed, not another essay)

- `.cursor/rules/10-quality-gates.mdc` Gate D — forbids claiming Pass when the assert allows the QA fail mode.
- `.cursor/rules/20-ship-gates.mdc` — adversarial fixture matrix required for money ships.
- `.cursor/rules/20-ship-gates.mdc` — registry asserts must encode QA acceptance shapes.
- `scripts/bin/ship-knowledge-gate.sh` (money profile) — WARN/FAIL when e2e / registry note contains
  acceptance anti-patterns ("OK A2 netting", "allow prin > amount", "principal_amount exceeds txn").
- **`scripts/lib/acceptance_coverage.py`** + `acceptance_coverage_manifest.json` — required dimensions
  (`happy_path`, `dirty_state`, `replay_idempotency`, `downstream_ui`, …) on enforced domains;
  `downstream_ui` needs `ui_fields` / `ui_asserted`; wired into `ship_discipline_gate` + `ship-loop-gate`.
  Unit: `scripts/lib/test_acceptance_coverage.py`. Backlog domains listed until annotated.
- `scripts/dcf_sanity/group_parent_last_child_dfc_local_e2e.py` — `ACCEPTANCE_STRICT=1` (default):
  amount≠principal FAILS; `assert_force_bill_labd` fails on EMI-hijack; `DCF_SEED_EMI_LABD` fixture flag.

## Root cause of the miss

Incomplete A2/B + verification that treated subset Pass as Done: asserts allowed amount≠principal,
EMI-overwrite path was untested, parent force-bill was scoped out silently, "webapp verified" was
partial. Gate scripts had no hard check for "assert allows the QA fail mode".
