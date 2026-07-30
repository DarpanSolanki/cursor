# LMS-DEFECT — GAP-062 writeoff PrepaymentApproppriation NPE

**Status:** code pushed; awaiting QA retest (local writeoff still blocked on missing catalogue)

## Root cause

`loanWriteoff` orch passes `prepayment_amount`←`writeoff_amount`, `value_date`, `penalty_amount` (String).
`PrepaymentApproppriationProcessor` read `total_foreclosure_amount` / `foreclosure_date` / `penal_amount` as BigDecimal → NPE / ClassCast → opaque **333**.

## Fix

`PrepaymentApproppriationProcessor.normalizeAppropriationContext` + `coerceBd` — shared for all callers:
- `loans_orc.xml` loanWriteoff :1446
- `loans_orc.xml` loanPrepayment :2023
- `group_mfi_orc.xml` :305

## Proof

After fix, writeoff proceeds past appropriation to `GetTransactionCatalogueIdProcessor` → **132223** Invalid transaction_type (`LOAN_WRITE_OFF`/`FINAL_WRITE_OFF` **absent** from local `transaction_catalogue`). GAP-062 NPE cleared; durable writeoff PASS needs catalogue seed (separate env gap).

## Sha

`896c02a56` on `origin/mfi_integration_v3.4.2.4`
