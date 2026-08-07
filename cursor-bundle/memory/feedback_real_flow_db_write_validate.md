# Real-flow DB write validation (STANDING — any money/service fix)

Darpan, 2026-07-17: "No assumption, no guesses, validate each and every database update
(if correct values are inserted/updated), the testing should be how in real the flow will
move and transactions will happen .. standard for any fix or implementation testing from now on."

## The bar (fail-closed)

1. **Real flow, not SQL-only.** Drive the actual orchestration / API / batch job that a
   production request/transaction would take (e.g. `deathForeclosureInsuranceJob`, last-child
   DFC path, `loanRepayment`, disburse). Never assert "row should have been inserted" from a
   hand-written INSERT or a status-only 200.
2. **Assert exact column values, not presence.** After each critical write, read the row back
   and compare the actual `interest_amount` / `principal_amount` / `client_reference_number` /
   `original_amount` / `excess_amount` / `is_deleted` / accrued-vs-billed to the EXPECTED value.
   A row existing is not a pass; the value must be right.
3. **Adversarial + dirty state.** Production rows are not clean seeds. Cover pre-existing state
   (e.g. `DCF_SEED_EMI_LABD=1`, `SEED_EXTRA=1`), boundary zero, and the exact QA fail mode
   (EMI-labd hijack, amount!=principal, Accrued>Original). The assert must FAIL on the fail mode.
4. **No assumed PASS.** If any written value is wrong → FAIL. If a stage can't run, follow
   `20-ship-gates.md` but still cite the expected writes (table+column+value).

## Machine enforcement (do not rely on prose)

- `scripts/lib/acceptance_coverage.py` — enforced money domains must declare
  `acceptance.db_asserts` (or registry `expect.db_eq`) covering every `domain_money_tables`
  entry in `acceptance_coverage_manifest.json`. Each db_assert needs `table` +
  (`expect`|`assert`|`columns`) + `checked_by` evidence. Presence-only phrasing
  ("row exists", "should have inserted", "status-only") is rejected. `self-test` proves it.
- Wired into `ship_discipline_gate.py` → runs on every money/service `--from-pending` close.
- DFC e2e (`scripts/dcf_sanity/group_parent_last_child_dfc_local_e2e.py`) asserts column-level
  values for labd (EMI preserved + dedicated FB prin=0), transaction_master client_ref +
  original_amount, payments amount==principal + excess, IAD Accrued<=Original — parent + children.

## Precedent (TDPQA-72 / SDCP-10199, 2026-07-17)

Real DB after live job: lid 7455066 → EMI labd int188/prin762 (157002) + FB labd int38/prin0
(157102); FB `transaction_master` client_ref `DFC_PRTL_BILL_7899567_1770489000000` orig=38;
parent payment amount=13702==principal excess=1244; Obs3 Accrued==Original 919/974/1845.
`findByLoanInstallmentDetailsId ORDER BY id DESC LIMIT 1` returns a non-reversed row for both
(FB for one child, EMI for the other) — all callers are null/reversed-only so multi-row is safe.

Pairs with: `feedback_qa_acceptance_not_subset_verify.md`,
`feedback_webapp_verify_mandatory_ui_ships.md`, `feedback_post_ship_registry_runbook_gap_mandatory.md`.
