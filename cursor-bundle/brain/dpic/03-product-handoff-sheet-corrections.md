# DPI Sheet — Corrections for Product (hand-off)

## STATUS (2026-06-08): code aligned to sheet where unambiguous; build green (compileJava). NOT committed, NOT runtime-verified (seeds not in QA).

### Catalogue re-update (product populated `sub_type` column)
- Only the **Transaction Cataloge** sheet changed; **Transaction Accounting Rule** + **Death Foreclosure** sheets UNCHANGED (collisions + missing DPI_NPA_ACCRUAL row still open).
- sub_type gap RESOLVED — product confirmed: `DPI_NORMAL_ACCRUAL`, `DPI_NORMAL_BILLING`, `DPI_INT_INCOME` (✓ match code). **New_Id_5 renamed → `DPI_NPA_ACCRUAL_BOOKING`** (mirrors INTEREST `NPA_ACCRUAL_BOOKING`). Code updated: `DpiBillingBatchService` NPA-booking sub_type → `DPI_NPA_ACCRUAL_BOOKING`.

### Single-entry + force-bill (per product: "force-bill gap, then single settle") — FORECLOSURE done
- `getDpiAmount`: settlement `DPI_AMOUNT` = billed DPI + gap (unbilled-till-date), as one `BILLED_DPI_INT_AMT` leg (dropped separate `BPD_AMT` gap leg).
- Orchestration (loanPrepayment): after settlement, force-bill the gap via `BILLING/DPI_NORMAL_BILLING` (`BILLED_DPI_INT_AMT` = gap → DR `DPI_BILLED_INTEREST` / CR `DPI_ACC_NOT_DUE`), guarded by `dpi_force_bill_required`. Net balances to zero.
- **Still pending product (rule sheet)**: make 117 (and 116/209/DFC) a SINGLE `BILLED_DPI_INT_AMT` settlement leg (DR `TRMN_SUSP` / CR `DPI_BILLED_INTEREST`) instead of two colliding legs; the force-bill reuses New_Id_2 `DPI_NORMAL_BILLING`.
### Lifecycle DPI — understood per-transaction (not copied), all flows done
Mechanism kept simple (no flags/orchestration ceremony): each settlement transaction emits ONE settlement leg `BILLED_DPI_INT_AMT` (= billed + gap) plus, when a gap exists, ONE `DPI_FORCE_BILL_AMT` leg (= the unbilled-till-date gap). Both legs ride the existing settlement postTransaction.
- **Foreclosure (117)**: settlement `BILLED_DPI_INT_AMT` (billed+gap) + `DPI_FORCE_BILL_AMT` (gap); `ADV_DPI_AMT` kept for excess-funded.
- **Part-prepayment (116)**: **fixed a pre-existing double-count** — gap was emitted in BOTH `OVER_DUE_DPI_AMT (=dpi_amount, which already includes the appropriated gap)` AND a separate `DPI_AMT (=gap)`. Now ONE `BILLED_DPI_INT_AMT` (= appropriated `dpi_amount`) + `DPI_FORCE_BILL_AMT` (gap).
- **Death-FC (119)**: `DPI_AMT` already combined overdue+gap → renamed leg to `BILLED_DPI_INT_AMT`; added `DPI_FORCE_BILL_AMT` (gap); `ADV_DPI_AMT` kept.
- **Loan closure**: `DPI_AMT (=unpaidDpiAmount, billed only, no gap)` → renamed `BILLED_DPI_INT_AMT`; no force-bill (no gap in closure).

**Product to seed (rule sheet still unchanged):** in each settlement catalogue (117/116/209/119) — (a) ONE `BILLED_DPI_INT_AMT` settlement rule: DR settlement-acct (TRMN_SUSP for FC, DUE_TO_FC_B for part-prepay/DFC, EXCESS_ACCT for the excess-funded `ADV_DPI_AMT`) / CR `DPI_BILLED_INTEREST` — i.e. resolve the current two-`BILLED_DPI_INT_AMT`-leg collision into `ADV_DPI_AMT` (EXCESS) + `BILLED_DPI_INT_AMT` (settlement); (b) ONE `DPI_FORCE_BILL_AMT` rule: DR `DPI_BILLED_INTEREST` / CR `DPI_ACC_NOT_DUE` (force-bill gap AIR→billed). Still also: add the missing `DPI_NPA_ACCRUAL` catalogue row.


**Applied in code** (`feature/dpic-v1`, accounting-v2 — uncommitted working tree):
| Flow | File | Change |
|---|---|---|
| DPI accrual | DpiAccrualBookingBatchService.java | emit named leg `DPI_ACCR_INT_AMT` (both post methods) |
| DPI billing | DpiBillingBatchService.java | named leg `BILLED_DPI_INT_AMT` (normal) / `DPI_INT_SUSP_AIR_AMT` (NPA); sub_type `DPI_NPA_BOOKING`→`DPI_NPA_ACCRUAL_ON_BILLING` |
| NPA movement | DpiNpaMovementService.java | income leg→`UNPAID_BILLED_DPI_INT_AMT`, AIR leg→`DPI_ACCR_INT_SUSPENSE_AIR_AMT` |
| Repayment 108/109/110 | loans_orc.xml | DPI leg `DPI_AMT`→`BILLED_DPI_INT_AMT` (both TRIAL+REAL) |
| Child repayment | group_mfi_orc.xml | `DPI_AMT`→`BILLED_DPI_INT_AMT` |
| Repayment NPA 115 | loans_orc.xml + RepaymentApproppriationProcessor.java | NEW leg `PAID_BILLED_DPI_INT_AMT` (=paid DPI) released suspense→income; NPA-txn amount→`npa_suspense_total_amount` (interest+DPI) |
| Foreclosure waiver | PopulateAdditionalAmountAndAccountDetailsForForeclosureProcessor.java | `LOSSES_BILLED_DPI_WAIVED`→`BILLED_DPI_INT_WAIVED_AMT` |
| Death-FC waiver | DeathForeclosureInsuranceWriter.java | billed-DPI waiver leg→`BILLED_DPI_INT_WAIVED_AMT` |

**STILL ASK PRODUCT (gaps — left unchanged in code, sheet must resolve):**
1. **Collisions** — 116/117/209/Death-FC give the same `BILLED_DPI_INT_AMT` to two pay-legs (advance vs overdue/regular). Code keeps distinct keys (`ADV_DPI_AMT`/`DPI_AMT`, `DPI_AMT`/`OVER_DUE_DPI_AMT`). Sheet must use two distinct `source_amount`s; until then these pay-legs won't bind.
2. **Missing "DPI NPA ACCRUAL" catalogue+rule** — code posts sub_type `DPI_NPA_ACCRUAL` for NPA-loan daily accrual (mirrors interest id8); add row DR `DPI_ACC_NOT_DUE`/CR `DPI_INT_SUSP_AIR`, `source_amount=DPI_ACCR_INT_AMT`.
3. **Writeoff** DPI leg (`loans_orc` ~1465) + **Loan account closure** (`LoanAccountClosureService:279`, `DPI_AMT`) + **DPI waiver-AIR** (foreclosure/death `LOSSES_DPI_WAIVED_AIR`) — no sheet rules. Confirm intended GL legs.
4. **New_Id_5 sub_type name** — code now `DPI_NPA_ACCRUAL_ON_BILLING` (= name with `_`). Interest analog is `NPA_ACCRUAL_BOOKING`; confirm final name (code follows whatever you seed).
5. Single-leg accrual/billing now bind on the **named keys per sheet** (`DPI_ACCR_INT_AMT`/`BILLED_DPI_INT_AMT`/`DPI_INT_SUSP_AIR_AMT`) — seed those exactly (NOT `amount`).

---


> Outcome of the code-vs-sheet audit ([02-code-vs-sheet-audit.md](02-code-vs-sheet-audit.md)). Decision: reconcile by correcting the **sheet** to match the code, because the code faithfully mirrors the normal-INTEREST accounting pattern (product principle: "DPI same as interest"). The sheet's amount-key names diverge from that pattern, and in two flows they collide.

## Rule of thumb
`sub_type` code = `sub_type_name` with spaces → `_` (matches existing QA: `NORMAL ACCRUAL`→`NORMAL_ACCRUAL`, `INT INCOME`→`INT_INCOME`).
A rule's `source_amount` must equal the per-leg key the code emits (engine binds by exact key — `ExecuteTransactionRulesProcessor.java:187-205`).

## Corrections to `Transaction Accounting Rule` sheet (`source_amount` / `reference_code`)

| Sheet row(s) | Flow | Current | Correct to |
|---|---|---|---|
| R8 (New_Id_1) | DPI normal accrual | `DPI_ACCR_INT_AMT` | `amount` |
| R11 (New_Id_2) | DPI normal billing | `BILLED_DPI_INT_AMT` | `amount` |
| R31 (New_Id_5) | DPI NPA accrual-on-billing | `DPI_INT_SUSP_AIR_AMT` | `amount` |
| R14/R18/R22 | Repayment cash/casa/excess | `BILLED_DPI_INT_AMT` | `DPI_AMT` |
| R24 (115) | Repayment NPA | `PAID_BILLED_DPI_INT_AMT` | `DPI_SUS_AMT` |
| R27/R34 | REGULAR/NPA_TO_REGULAR income | `UNPAID_BILLED_DPI_INT_AMT` | `DPI_INT_AMT` |
| R28/R35 | REGULAR/NPA_TO_REGULAR AIR | `DPI_ACCR_INT_SUSPENSE_AIR_AMT` | `DPI_INT_SUSPENSE_AIR_AMT` |
| R49 (116 seq3, EXCESS) | Part-prepayment advance DPI | `BILLED_DPI_INT_AMT` | `OVER_DUE_DPI_AMT` *(see note)* |
| R53 (116 seq4, DUE_TO_FC) | Part-prepayment overdue DPI | `BILLED_DPI_INT_AMT` | `DPI_AMT` |
| R59 (117 seq3, EXCESS) | Foreclosure advance DPI | `BILLED_DPI_INT_AMT` | `ADV_DPI_AMT` |
| R64 (117 seq4, TRMN_SUSP) | Foreclosure regular DPI | `BILLED_DPI_INT_AMT` | `DPI_AMT` |
| R72 (117 seq22) | Foreclosure DPI waiver | `BILLED_DPI_INT_WAIVED_AMT` | `LOSSES_BILLED_DPI_WAIVED` |
| R112/R118/R125 (209) | Child-FC-parent-reschedule | `BILLED_DPI_INT_*` | mirror 117 keys |
| DFC R6/R10 | Death FC DPI pay (EXCESS/DUE_TO_FC) | `BILLED_DPI_INT_AMT` | `ADV_DPI_AMT` / `DPI_AMT` |
| DFC R21 | Death FC DPI waiver | `BILLED_DPI_INT_WAIVED_AMT` | `LOSSES_DPI_WAIVED` |

> **Collision flagged:** sheet rows 116 (R49/R53) and 117 (R59/R64) currently give the **same** `source_amount` (`BILLED_DPI_INT_AMT`) to two legs that must carry different amounts (advance vs overdue/regular). As written they are unimplementable — one key cannot feed two different leg amounts. Interest distinguishes them (`ADV_INT_AMT` vs `INT_AMT`, `INT_AMT` vs `OVER_DUE_INT_AMT`); DPI must too.

## Corrections to `Transaction Cataloge` sheet
1. Add the missing **"DPI NPA ACCRUAL"** row → type `INTEREST`, sub_type `DPI_NPA_ACCRUAL` (mirror interest id8 `NPA_ACCRUAL`). The accrual job already posts this sub_type for NPA loans. Its rule: DR `DPI_ACC_NOT_DUE` / CR `DPI_INT_SUSP_AIR`, `source_amount=amount`.
2. New_Id_5 sub_type: code now emits `DPI_NPA_ACCRUAL_ON_BILLING` (= name "DPI NPA ACCRUAL ON BILLING" with `_`). Interest's analog is `NPA_ACCRUAL_BOOKING` — **confirm** whether to keep "ON BILLING" or rename to "DPI NPA ACCRUAL BOOKING" for consistency; code will match whichever you finalize.
3. Provide real `transaction_catalogue_id` FKs for `New Id_1..5` when seeding (sheet uses logical ids; QA PKs differ).
4. R11 (DPI billing) is missing a `sequence_number`.

## GLs to create (placeholder_master) — confirmed correct, just need seeding
`DPI_ACC_NOT_DUE` (ASSET), `DPI_INT_INC` (INCOME), `DPI_BILLED_INTEREST` (ASSET), `DPI_BILLED_INT_WAIVE` (EXPENSE), `DPI_INT_SUSP_AIR` (LIABILITY), `DPI_INT_SUSP` (LIABILITY).
