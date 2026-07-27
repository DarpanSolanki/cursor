# DPIC v1 — Code vs Product Sheet Audit (Accounting Rules)

> Source sheet: `downloads/Sample Calculation and Accounting Entries of DPI v 1.3.xlsx`
> Sheets audited: `Transaction Cataloge`, `Plaeholder Master`, `Transaction Accounting Rule`, `Death Foreclosure TXS Acct Rule`.
> Code audited: `novopay-platform-accounting-v2` @ `feature/dpic-v1` (read via `git show`/`git grep`; working tree is on `feature/neft-v2-payment-reinit-qa-3.3.1.2`).
> Date: 2026-06-08. Status of seeds: **NOT inserted in QA** (per user) — so the sheet is the spec; the code must emit literals that match it.

## Verdict

The DPI **GL accounts, catalogue rows, and accounting rules are data** that product will seed from these sheets. The **code's job** is to post each DPI transaction with a `transaction_type`/`sub_type` and per-leg `reference_code` that the seeded rules can bind to. **The code uses a different naming vocabulary than the sheet in every DPI flow** → as written, the sheet's rules will not bind to the amounts the code computes.

## How binding works (proven)

- Rule engine resolves each rule's amount by **exact key lookup**: `executionContext.get(rule.source_amount)`, no fallback to top-level `amount` — `transaction/processor/ExecuteTransactionRulesProcessor.java:187-193`, and for `TRANSFER` rules `calculatedAmount = sourceAmount` (`:205`). All DPI rules in the sheet are `entry_type=TRANSFER`.
- Multi-leg amounts reach the context as `{reference_code → amount}`: `transaction/processor/PopulateAdditionalAmountProcessor.java:37,43` flattens `additional_amount_details` legs into the EC.
- ⇒ **A leg's `reference_code` (or the literal `amount`) MUST equal the rule's `source_amount`**, or the leg resolves to null.
- Rule also looks up debit/credit GL by `placeholder_master.code` (`ExecuteTransactionRulesProcessor.java:133-134`) ⇒ the 6 DPI GLs must exist before any DPI rule resolves.

## Proof the vocabularies are disjoint

`git grep -l <key> feature/dpic-v1` in accounting-v2:

| Sheet `source_amount` key | Files in code |
|---|---|
| `DPI_ACCR_INT_AMT` | **0** |
| `BILLED_DPI_INT_AMT` | **0** |
| `PAID_BILLED_DPI_INT_AMT` | **0** |
| `UNPAID_BILLED_DPI_INT_AMT` | **0** |
| `DPI_ACCR_INT_SUSPENSE_AIR_AMT` | **0** |
| `BILLED_DPI_INT_WAIVED_AMT` | **0** |
| `DPI_INT_SUSP_AIR_AMT` | **0** |

None of the sheet's DPI amount keys exist anywhere in the code. The code instead uses `DPI_AMT`, `OVER_DUE_DPI_AMT`, `DPI_INT_AMT`, `DPI_INT_SUSPENSE_AIR_AMT`, `LOSSES_BILLED_DPI_WAIVED`, `LOSSES_DPI_WAIVED`, or top-level `amount`.

## Mismatch matrix (code key → sheet `source_amount`)

| Flow | Code emits (file:line) | Sheet expects (rule row) | Match |
|---|---|---|---|
| DPI accrual (normal/NPA) | top-level `amount` — `DpiAccrualBookingBatchService.java:118` | `DPI_ACCR_INT_AMT` (rule R8) | ✗ |
| DPI billing (normal) | top-level `amount` — `DpiBillingBatchService.java:112` | `BILLED_DPI_INT_AMT` (R11) | ✗ |
| DPI NPA accrual-on-billing | top-level `amount`, subtype `DPI_NPA_BOOKING` — `DpiBillingBatchService.java:45,112` | `DPI_INT_SUSP_AIR_AMT` (R31, New_Id_5) | ✗ |
| Repayment CASH/CASA | leg `DPI_AMT` — `loans_orc.xml:1140,1194` | `BILLED_DPI_INT_AMT` (R14/R18) | ✗ |
| Repayment EXCESS_AMT (110) | leg `DPI_AMT` (repayment) | `BILLED_DPI_INT_AMT` (R22) | ✗ |
| Repayment NPA (115) | no `PAID_BILLED_DPI_INT_AMT` key (0 files) | `PAID_BILLED_DPI_INT_AMT` (R24) | ✗ |
| Writeoff | leg `DPI_AMT` — `loans_orc.xml:1460` | (no DPI writeoff rule in sheet) | flag |
| Child-loan repayment | leg `DPI_AMT` — `group_mfi_orc.xml:103` | `BILLED_DPI_INT_AMT` | ✗ |
| REGULAR_TO_NPA income | leg `DPI_INT_AMT` — `DpiNpaMovementService.java:51,108` | `UNPAID_BILLED_DPI_INT_AMT` (R27) | ✗ |
| REGULAR_TO_NPA AIR | leg `DPI_INT_SUSPENSE_AIR_AMT` — `DpiNpaMovementService.java:52,109` | `DPI_ACCR_INT_SUSPENSE_AIR_AMT` (R28) | ✗ |
| NPA_TO_REGULAR income | leg `DPI_INT_AMT` | `UNPAID_BILLED_DPI_INT_AMT` (R34) | ✗ |
| NPA_TO_REGULAR AIR | leg `DPI_INT_SUSPENSE_AIR_AMT` | `DPI_ACCR_INT_SUSPENSE_AIR_AMT` (R35) | ✗ |
| Part-prepayment (116) | legs `DPI_AMT`, `OVER_DUE_DPI_AMT` — `PopulateAdditionalAmountForPartPrepaymentProcessor.java:225,250` | `BILLED_DPI_INT_AMT` (R49/R53) | ✗ |
| Foreclosure (117) DPI principal | (no `BILLED_DPI_INT_AMT` key) | `BILLED_DPI_INT_AMT` (R59/R64) | ✗ |
| Foreclosure (117) DPI waiver | leg `LOSSES_BILLED_DPI_WAIVED` — `PopulateAdditionalAmountAndAccountDetailsForForeclosureProcessor.java:299` | `BILLED_DPI_INT_WAIVED_AMT` (R72) | ✗ |
| Child FC parent reschedule (209) | (handled in foreclosure path) | `BILLED_DPI_INT_AMT` (R118/R125), `BILLED_DPI_INT_WAIVED_AMT` (R112) | ✗ |
| Death foreclosure (119) | legs `DPI_AMT`/`ADV_DPI_AMT`/`LOSSES_DPI_WAIVED`/`LOSSES_DPI_WAIVED_AIR` — `DeathForeclosureInsuranceWriter.java:392,409,423,425` | `BILLED_DPI_INT_AMT` (DFC R6/R10), `BILLED_DPI_INT_WAIVED_AMT` (DFC R21) | ✗ |

Runtime manifestation of a non-binding leg (exception vs silently-zero leg) **NOT traced** — but it is certain the code-computed DPI amount cannot flow into the sheet's GL legs, because the keys are disjoint.

## FLAGGED — gaps in the sheet (cannot fix from sheet alone)

1. **`sub_type` code not specified.** The `Transaction Cataloge` sheet has columns `id | type | type | type_name | sub_type_name` — **there is no `sub_type` column**. It only gives the display `sub_type_name` ("DPI NORMAL ACCRUAL"). The DB column the engine matches on is `sub_type` (underscore form, e.g. existing `NORMAL_ACCRUAL`, `NORMAL_BILLING`, `INT_INCOME` — QA query). ⇒ The exact `sub_type` codes to seed are undefined; cannot verify code's literals (`DPI_NORMAL_ACCRUAL`, `DPI_NPA_ACCRUAL`, `DPI_NORMAL_BILLING`, `DPI_NPA_BOOKING`, `DPI_INT_INCOME`) against the sheet. **Product must specify.**
2. **Code posts a `DPI_NPA_ACCRUAL` sub_type with no matching catalogue/rule in the sheet.** Accrual on an NPA loan → `DpiAccrualBookingBatchService.java:158`. The catalogue has only New_Id_1 (DPI NORMAL ACCRUAL) and New_Id_5 (DPI NPA ACCRUAL **ON BILLING**); no plain "DPI NPA ACCRUAL" row. Needs product decision: add the rule, or change the code to accrue normally and rely on the REGULAR_TO_NPA move.
3. **Logical ids.** Sheet uses `New Id_1..5` and legacy ids (104,107,108…) that are not the QA PKs (QA: INTEREST=2, BILLING=7, REGULAR_TO_NPA=5, NPA_TO_REGULAR=6). Product must assign real `transaction_catalogue_id` FKs when seeding.
4. **DPI billing rule R11 has a blank `sequence_number`.**
5. **No DPI rule for writeoff** though the code posts a `DPI_AMT` leg in `loanWriteoff` (`loans_orc.xml:1460`).

## Placeholder GLs (sheet `Plaeholder Master` R32-R37) — product to seed

`DPI_ACC_NOT_DUE` (ASSET), `DPI_INT_INC` (INCOME), `DPI_BILLED_INTEREST` (ASSET), `DPI_BILLED_INT_WAIVE` (EXPENSE), `DPI_INT_SUSP_AIR` (LIABILITY), `DPI_INT_SUSP` (LIABILITY). Code never references these directly (correct — resolved by the rule engine from each rule's debit/credit placeholder); they only need to exist before the rules resolve.

## RECONCILIATION — "DPI mirrors INTEREST" (product principle, confirmed in code)

Product states DPI behaves the same as normal interest. Confirmed in code: existing interest accrual posts **single-leg top-level `amount`** ([InterestAccrualBookingBatchService.java:281](../../trustt-platform-accounting/src/main/java/in/novopay/accounting/batchnew/interest/interestaccrualbooking/InterestAccrualBookingBatchService.java#L281)) with rule `source_amount="amount"` (QA), and the same 3 sub_types `NORMAL_ACCRUAL`/`NPA_ACCRUAL`/`NPA_ACCRUAL_BOOKING`. The DPI code mirrors interest faithfully (DPI-prefixed keys). **It is the SHEET's amount-key names that diverge from the interest convention** — and in two flows they collide.

3-way comparison (INTEREST key from QA | DPI code key file:line | DPI sheet `source_amount`):

| Flow / leg | INTEREST (QA) | DPI code | DPI sheet | Verdict |
|---|---|---|---|---|
| Accrual normal | `amount` (id2) | top `amount` | `DPI_ACCR_INT_AMT` | code OK; **sheet should be `amount`** |
| Accrual NPA | `amount` (id8) | top `amount` | *(missing)* | code OK; **sheet missing row** |
| NPA accrual-on-billing | `amount` (id9) | top `amount` | `DPI_INT_SUSP_AIR_AMT` | code OK; **sheet should be `amount`** |
| Billing normal | n/a (1-leg) | top `amount` | `BILLED_DPI_INT_AMT` | code OK; **sheet should be `amount`** |
| Repayment cash/casa/excess | `INT_AMT` | `DPI_AMT` | `BILLED_DPI_INT_AMT` | code OK; **sheet should be `DPI_AMT`** |
| Repayment NPA (115) | `INT_SUS_AMT` | *(none)* | `PAID_BILLED_DPI_INT_AMT` | **CODE GAP**; sheet name should mirror (e.g. `DPI_SUS_AMT`) |
| REGULAR_TO_NPA income/AIR | `INT_AMT` / `INT_SUSPENSE_AIR_AMT` | `DPI_INT_AMT` / `DPI_INT_SUSPENSE_AIR_AMT` | `UNPAID_BILLED_DPI_INT_AMT` / `DPI_ACCR_INT_SUSPENSE_AIR_AMT` | code OK; **sheet diverges** |
| NPA_TO_REGULAR income/AIR | `INT_AMT` / `INT_SUSPENSE_AIR_AMT` | `DPI_INT_AMT` / `DPI_INT_SUSPENSE_AIR_AMT` | `UNPAID_BILLED_DPI_INT_AMT` / `DPI_ACCR_INT_SUSPENSE_AIR_AMT` | code OK; **sheet diverges** |
| Part-prepayment (116) | `INT_AMT` + `OVER_DUE_INT_AMT` | `DPI_AMT` + `OVER_DUE_DPI_AMT` | `BILLED_DPI_INT_AMT` (BOTH legs) | code OK; **sheet diverges + COLLIDES** |
| Foreclosure (117) pay | `INT_AMT`(TRMN) + `ADV_INT_AMT`(EXCESS) | `DPI_AMT` + `ADV_DPI_AMT` | `BILLED_DPI_INT_AMT` (BOTH legs) | code OK; **sheet diverges + COLLIDES** |
| Foreclosure (117) waiver | `LOSSES_BILLED_INT_WAIVED` | `LOSSES_BILLED_DPI_WAIVED` | `BILLED_DPI_INT_WAIVED_AMT` | code OK; **sheet diverges** |
| Death FC | `BLD_INT_AMT`/`ADV_BLD_INT_AMT`/`BLD_INT_WAIVED_AMT` | `DPI_AMT`/`ADV_DPI_AMT`/`LOSSES_DPI_WAIVED` | `BILLED_DPI_INT_AMT`/`BILLED_DPI_INT_WAIVED_AMT` | all 3 differ — **needs alignment** |

**Revised conclusion:** the code is right for ~all flows (it mirrors interest). The reconciliation should correct the **sheet** to the interest-mirroring keys the code emits — NOT rewrite the code. Genuine **code** items: (1) NPA repayment (115) missing DPI suspense→income leg; (2) NPA-on-billing sub_type `DPI_NPA_BOOKING` → align to `DPI_NPA_ACCRUAL_BOOKING`; (3) sheet must add the missing "DPI NPA ACCRUAL" row.

Sub_type code rule (product-confirmed): `sub_type` = `sub_type_name` with spaces→`_` (matches existing QA: `NORMAL ACCRUAL`→`NORMAL_ACCRUAL`, `INT INCOME`→`INT_INCOME`).

## Fixable from the sheet (code → sheet) vs blocked

- **Fixable now (sheet gives the target `source_amount`):** all per-leg `reference_code` renames + emitting named legs for single-leg accrual/billing. Files: `DpiAccrualBookingBatchService`, `DpiBillingBatchService`, `DpiNpaMovementService`, `PopulateAdditionalAmountForPartPrepaymentProcessor`, `PopulateAdditionalAmountAndAccountDetailsForForeclosureProcessor`, `DeathForeclosureInsuranceWriter`, `loans_orc.xml` (loanRepayment ×2), `group_mfi_orc.xml`; repayment-NPA (115) path needs a new `PAID_BILLED_DPI_INT_AMT` leg.
- **Blocked (need product):** `sub_type` codes (gap #1), the missing DPI NPA ACCRUAL rule (gap #2), writeoff DPI rule (gap #5).
