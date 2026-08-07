# Accounting coverage — what is proven, beyond the batch jobs

Scope: `trustt-platform-accounting`. Measured 2026-08-08 against `mfi_integration_v3.4.2.5`.

**Everything here runs correctly in production.** A flow listed uncovered is a gap in *this test
suite*, not a product defect. Read the whole document with that prior.

## Headline

**30 of 351 live accounting apiNames (8.5%) have a runtime-verified case.
7 of 23 live loan transactions (30%) are proven at value level.**

The stock report's `reg` column says 72 (20%). The difference is placeholders, sims and
undeclared cases counted as coverage. Confirmed independently by a second generator:
`loan_flow_worklist.py` → *241 flows reaching a loan account, 22 proven covered, 219 to do*.

## Grading

| `verify_mode` | Verdict |
|---|---|
| `runtime` / `RUNTIME_VERIFIED` | covered |
| `WORKSPACE_ONLY` | **UNCOVERED — theatre.** Proves the code exists, not that it works |
| `processor_mirror_sim` / `orch_sibling_sim` | not covered |
| absent / `none` / `static_gate` | not covered |

Join cases to APIs on the case's **`api`** field and its **`apis`** list — never the case id. That
exact mistake produced a duplicate case this week.

## Dead code — excluded from every denominator

| Domain | Why |
|---|---|
| `penal_interest` | **PINT is not configured in production.** Agrees with `40-knowledge-upkeep.md` § Precedent discipline, and with `flowtest.penal_accrual`'s own `quarantine.label = OUT-OF-SCOPE` |
| `writeoff` | `flowtest.loan_writeoff` → `NOT-DEVELOPED`, GAP-062 WONT_TRACK |
| `dpi` | Not dead — *not measurable here*. Zero accounting apiNames contain "dpi"; DPI runs as Spring Batch. Its `0/0` row reads green off an empty denominator. Real proof is in the `dpic.*` cases |

Live denominator: **351** apiNames (354 − 2 penal − 1 writeoff).

## The 15 placeholders that assert nothing

All `type: flow`, zero `db_asserts`, zero `expect.db_eq`:

`foreclosure.child_loan_foreclosure_kg` · `reversal.child_txn_reversal_kg` ·
`restructuring.child_loan_restructuring_kg` · `restructuring.loan_account_reschedule_kg` ·
`reopening.get_loan_account_reopening_details_kg` · `npa_dpd.loan_account_asset_criteria_kg` ·
`npa_dpd.loan_account_asset_classification_kg` · `eod_bod.run_eod_jobs_kg` ·
`eod_bod.run_bod_jobs_kg` · `read_inquiry.get_loan_account_accrued_bpi_kg` ·
`mandates_si.expire_pending_mandates_kg` · `portfolio.execute_lms_portfolio_transfer_kg` ·
`waiver.child_waive_loan_account_charges_kg` ·
`excess_refund.proactive_excess_amount_refund_staging_kg` ·
`excess_refund.loan_account_excess_amount_refund_kg`

Effect: `portfolio` reads 1/1 and is **0/1**. `waiver` reads 2/2 and is **1/2**. `eod_bod` reads
4/5 and is **2/5** — `runEODJobs` and `runBODJobs`, the entry points to the entire nightly chain,
are placeholders.

## Loan transactions

| State | Transactions |
|---|---|
| **Runtime + value asserts** | `disburseLoan`, `loanRepayment`, `loanPrepayment`, `loanAccountReopening`, `childLoanRestructuring`, `waiveLoanAccountCharges`, `proactiveExcessAmountRefund` |
| **Runtime, 0 db_asserts** | `childLoanRepayment`, `loanDeathForeclosure`, `postTransaction` |
| **Sim only** | `childLoanDisbursement`, `childLoanReopening`, `loanRecurringPaymentBatchApi` |
| **Ran-only, undeclared** | `loanAccountClosure`, `loanAdvanceRepayment` |
| **Theatre** | `childLoanForeclosure`, `childLoanTransactionReversal`, `childWaiveLoanAccountCharges`, `loanAccountExcessAmountRefund` |
| **No case** | `loanDisbursementCancellation`, `childLoanDisbursementCancellation`, `loanAccountRestructuring`, `reverseTransaction` |

**Death-FC nuance — do not read one as the other.** The *insurance writer* is genuinely strong
(`dcf.group_parent_last_child_e2e` 6 asserts, `dcf.vikram_fc_rstcre_dfc_e2e` 5). It is the
*intake orchestration* `loanDeathForeclosure` (107 processors) that has no value assert.

Two cases document their own emptiness in `why`, and both are worth keeping honest rather than
quietly upgrading:

- `batch.loan_advance_repayment` — *"read 1, wrote 1, reported COMPLETED — and `excess_amount` is
  still 10276.00. So the account was processed and the money did not move."*
- `batch.loan_account_closure` — *"asserts that it RAN … and nothing about the resulting state,
  deliberately."*

## Worklist — money first

Every column resolved with `kg.py schema`, none from memory.

**Tier A — money write path, zero assert**

| # | Flow | Assert | Fails on |
|---|---|---|---|
| 1 | `loanDisbursementCancellation` `loans_orc.xml:3937` | `loan_disbursement_cancellation_details` `.excess_amount` `.cross_sell_amount` `.bpi_amount_to_be_paid` `.bpi_waived_amount` `.cancellation_status` vs the simulation | cancellation posting an excess or BPI waiver that disagrees with what the user was shown |
| 2 | `reverseTransaction` `product_transaction_orc.xml:89` | per-transaction double-entry + reversal linkage. **`kg.py schema account_entry` returns `unknown table` — resolve live before writing** | a reversal booking one leg |
| 3 | `loanAccountExcessAmountRefund` `loans_orc.xml:4516` | `.total_refund_amount` equals the excess removed from `loan_account_payments_details.excess_amount` | refunding more than the loan held |
| 4 | `childLoanTransactionReversal` `group_mfi_orc.xml:392` | `loan_due_details.paid_amount` returns to pre-repayment **per row**; exactly one offsetting payments row | totals netting out while the per-installment split is wrong |
| 5 | `childLoanForeclosure` `group_mfi_orc.xml:259` | `*_amount_to_be_paid` + `*_waived_amount` = `*_amount` for each component | a waived component still billed |
| 6 | `childLoanDisbursementCancellation` `group_mfi_orc.xml:524` | `loan_due_details` per installment; `waiver__loan_due_details.waived_amount` per id | dues left on a cancelled child |
| 7 | `childWaiveLoanAccountCharges` `group_mfi_orc.xml:186` | `waiver__loan_due_details.waived_amount` = the reduction in the linked due | audit row written, due not reduced |
| 8 | `loanAccountRestructuring` `loans_orc.xml:5858` | `.new_emi` `.new_tenure` `.new_roi` `.old_*` vs request; installment count = `new_tenure` | `UPDATE_TENURE` silently applying the EMI branch |
| 9 | `loanAdvanceRepayment` `loans_orc.xml:2599` | excess decreases by exactly the settled due; `paid_amount` rises by the same | **goes red on the current fixture — establish stale-fixture vs seeding gap first, do not file a defect on one local reading** |
| 10 | `loanAccountClosure` `loans_orc.xml:2585` | closure amounts **scoped to one seeded LAN** — the case rejected two population-wide asserts for good reason | tolerance path posting GL that disagrees with the closure row |

**Tier B — the run already exists, only the assert is missing (cheap)**

11 `childLoanRepayment` per-component appropriation · 12 `loanDeathForeclosure` intake amounts ·
13 `postTransaction` double-entry scoped by `client_reference_number` · 14 `childLoanDisbursement`
installment count = tenure, per-installment due = child EMI (catches the parent-schedule
cross-loan FK class) · 15 `loanRecurringPaymentBatchApi` `presentation_bounce_charge_details`
(catches a bounce charge applied twice, or on a *successful* presentation — money charged to a
borrower, visible on their statement).

Excluded deliberately: 24 bulk-file jobs, 41 master-data CRUD, 83 read APIs. Largest raw counts,
but configuration and read surface, not money movement.

## Highest-value next action

**Give `reverseTransaction` and `postTransaction` a per-transaction double-entry assert.** Not the
largest gap — the *shared* one. Every Tier A item funnels through one or both, so one assert on the
ledger primitive raises the floor under cancellation, excess refund, child reversal and closure
tolerance at once. Each of the other fourteen buys exactly one flow.

## Tooling defect found and fixed

`bucket()` in `scripts/lib/accounting_flow_domains.py` matched `path_hints` with a bare substring
test, so `penalInterestAccrualCalculation` matched the `interestaccrualcalculation` hint and landed
in `interest_accrual`. That domain reported **4/4 = 100%** off a denominator padded with two
production-dead APIs, while `penal_interest` reported an empty 0/0.

The sibling matcher `_path_hint_matches` already had the boundary guard, and its docstring names
this exact case. Fixed to use it: `interest_accrual` 4→2, `penal_interest` 0→2.

Still open: `dpi` and `writeoff_settlement` report `gap: 0` on a zero denominator, which reads as
green.

## Pairs with

`.cursor/eod-bod-coverage-plan.md` (the 24 live batch jobs) · `.cursor/gaps-and-risks.md`
GAP-095 / GAP-101 / GAP-103 (the silent-success family) ·
`.cursor/rules/run-the-real-thing-locally.mdc` (red before green)
