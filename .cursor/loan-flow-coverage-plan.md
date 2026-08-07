# Loan flow coverage plan (generated — do not hand-edit)

`python3 scripts/testing/loan_flow_worklist.py` regenerates this from the platform
maps and the registry. Every loan-account flow the webapp starts or a batch job runs,
with what is missing and the one action that would move it.

A hand-written task list is stale the week after it is written. This one re-derives
itself, so the number going down is progress rather than a claim.

## Scope

| | Count |
|---|---:|
| Loan flows reachable from the webapp | 125 |
| Loan flows run by a batch job or scheduler | 120 |
| Of those, writing a money table | 72 |
| In the EOD/BOD chain | 12 |
| **Proven covered** (`RUNTIME_VERIFIED`) | **22** |
| **Still to do** | **219** |
| — of which the current fixture could drive today | 217 |
| — of which blocked on a contract or an entry point | 2 |

Coverage means the flow was **run for real and its columns asserted**. A registry
case that has never run is not coverage; `40-knowledge-upkeep.md` calls a
presence-only assert what it is.

## EOD / BOD chain

The jobs production runs unattended, in call order from the entry point. Depth 0 is
the entry; anything deeper runs because something above it called it.

| Depth | Flow | Writes | Case | Action |
|---:|---|---:|---|---|
| 0 | `runBODJobs` | 0 | yes | case exists (eod_bod.run_bod_jobs_kg) but verify_mode is workspa |
| 0 | `runEODJobs` | 3 | yes | case exists (eod_bod.run_eod_jobs_kg) but verify_mode is workspa |
| 1 | `interestAccrualCalculation` | 7 | yes | covered — keep the assert honest when the flow changes |
| 1 | `interestAccrualPosting` | 5 | yes | covered — keep the assert honest when the flow changes |
| 1 | `loanAccountAssetClassificationJob` | 1 | yes | covered — keep the assert honest when the flow changes |
| 1 | `loanAccountAssetCriteriaJob` | 9 | yes | case exists (npa_dpd.loan_account_asset_criteria_kg, batch.asset |
| 1 | `loanAccountBillingJob` | 11 | yes | covered — keep the assert honest when the flow changes |
| 1 | `loanAccountDpdCalcJob` | 1 | yes | covered — keep the assert honest when the flow changes |
| 1 | `loanAdvanceRepayment` | 9 | yes | case exists (batch.loan_advance_repayment) but verify_mode is un |
| 1 | `penalInterestAccrualBooking` | 11 | yes | case exists (batch.penal_interest_accrual_booking) but verify_mo |
| 1 | `penalInterestAccrualCalculation` | 7 | yes | covered — keep the assert honest when the flow changes |
| 2 | `postTransaction` | 7 | yes | covered — keep the assert honest when the flow changes |

## Highest priority — money, scheduled, uncovered

These write a money table and run on a schedule, so a defect lands overnight with
nobody watching.

| Flow | Repo | Entry | Money tables | Action |
|---|---|---|---|---|
| `pushPendingLMSUpdates` | payments | batch | `interest_accrual_details`, `loan_account`, `loan_account_events_queue` | write a read case from the JTF response template |
| `bulkFileToSGEnachRepresentationJob` | accounting | batch | `loan_account`, `loan_account_closure_details`, `loan_account_events_queue` | write a read case from the JTF response template |
| `bulkSGToEnachRepresentationJob` | accounting | batch | `loan_account`, `loan_account_closure_details`, `loan_account_events_queue` | write a read case from the JTF response template |
| `loanAccountClosure` | accounting | batch | `account_balance`, `interest_accrual_details`, `loan_account` | case exists (batch.loan_account_closure) but verify_mode is undeclared |
| `bulkSGToDisbursementCancellationJob` | accounting | batch | `account_balance`, `loan_account` | write a read case from the JTF response template |
| `inboundDeathForeclosureInsuranceJob` | accounting | batch | `loan_account`, `loan_due_details`, `loan_installment_details` | write a read case from the JTF response template |
| `inboundDisbursementCancellationBajajErgoHealthInsuranceJob` | accounting | batch | `account_balance`, `loan_account` | write a read case from the JTF response template |
| `inboundDisbursementCancellationHdfcErgoHealthInsuranceJob` | accounting | batch | `account_balance`, `loan_account` | write a read case from the JTF response template |
| `inboundDisbursementCancellationHdfcLifeLifeInsuranceJob` | accounting | batch | `account_balance`, `loan_account` | write a read case from the JTF response template |
| `outboundDeathForeclosureInsuranceJob` | accounting | batch | `loan_account`, `loan_due_details`, `loan_installment_details` | write a read case from the JTF response template |
| `outboundDisbursementCancellationBajajErgoHealthInsuranceJob` | accounting | batch | `account_balance`, `loan_account` | write a read case from the JTF response template |
| `outboundDisbursementCancellationHdfcErgoHealthInsuranceJob` | accounting | batch | `account_balance`, `loan_account` | write a read case from the JTF response template |
| `outboundDisbursementCancellationHdfcLifeLifeInsuranceJob` | accounting | batch | `account_balance`, `loan_account` | write a read case from the JTF response template |
| `penalInterestAccrualBooking` | accounting | batch | `account_balance`, `loan_account`, `loan_due_details` | case exists (batch.penal_interest_accrual_booking) but verify_mode is  |
| `runInboundDeathForeclosureInsuranceJob` | accounting | batch | `loan_account`, `loan_due_details`, `loan_installment_details` | write a read case from the JTF response template |
| `runInboundDisbursementCancellationBajajErgoHealthInsuranceJob` | accounting | batch | `account_balance`, `loan_account` | write a read case from the JTF response template |
| `runInboundDisbursementCancellationHdfcErgoHealthInsuranceJob` | accounting | batch | `account_balance`, `loan_account` | write a read case from the JTF response template |
| `runInboundDisbursementCancellationHdfcLifeLifeInsuranceJob` | accounting | batch | `account_balance`, `loan_account` | write a read case from the JTF response template |
| `bulkFileToSGManualHoldMarkingJob` | accounting | batch | `loan_account` | write a read case from the JTF response template |
| `bulkFileToSGManualHoldRemovalJob` | accounting | batch | `loan_account` | write a read case from the JTF response template |

## Webapp-initiated, money-writing, uncovered

| Flow | Repo | Money tables | Action |
|---|---|---|---|
| `loanRecurringPaymentBatchApi` | accounting | `loan_account`, `loan_due_details`, `loan_installment_details` | case exists (collections.tdpfr547_dpi_amountmap_sim) but verify_mode i |
| `runEODJobs` | accounting | `loan_account` | case exists (eod_bod.run_eod_jobs_kg) but verify_mode is workspace_onl |
| `loanDisbursementCancellation` | accounting | `interest_accrual_details`, `loan_account`, `loan_account_events_queue` | write a read case from the JTF response template |
| `createOrUpdateGeneralLedger` | accounting | `account_balance` | write a money case: seed the fixture, run the real flow, assert exact  |
| `groupLoanAccountRebooking` | accounting | `loan_account`, `loan_account_events_queue` | write a read case from the JTF response template |
| `individualLoanAccountRebooking` | accounting | `loan_account` | write a read case from the JTF response template |
| `loanAccountExcessAmountRefund` | accounting | `loan_account`, `loan_account_events_queue`, `loan_account_payments_details` | case exists (excess_refund.loan_account_excess_amount_refund_kg) but v |
| `loanAccountRestructuring` | accounting | `loan_account`, `loan_account_events_queue` | write a read case from the JTF response template |
| `loanWriteoff` | accounting | `loan_account`, `loan_account_payments_details`, `loan_due_details` | case exists (flowtest.loan_writeoff) but verify_mode is undeclared — d |
| `generateRepaymentSchedule` | accounting | `loan_due_details`, `loan_installment_details` | write a money case: seed the fixture, run the real flow, assert exact  |
| `getLoanAccountOverviewDetails` | accounting | `interest_accrual_details`, `loan_installment_details` | case exists (dpic.overview_api) but verify_mode is undeclared — drive  |
| `createOrUpdateInternalAccount` | accounting | `account_balance` | write a money case: seed the fixture, run the real flow, assert exact  |
| `fetchDisbursementCancellationSimulationDetails` | accounting | `loan_account_tax_details` | case exists (accounting.disbursement_cancellation_simulation) but veri |
| `fetchLoanAccountChargeDetails` | accounting | `loan_account_tax_details` | write a read case from the JTF response template |
| `fetchLoanForeclosureSimulationDetails` | accounting | `loan_account_tax_details` | case exists (dpic.foreclosure_sim, dpic.foreclosure_bpd_day_window_sim |
| `getLoanAccountBasicDetails` | accounting | `loan_account` | case exists (accounting.loan_basic) but verify_mode is undeclared — dr |

## Blocked, and why

Not laziness — these need something resolved before a test could exist.

- **2** — no JTF request template — no HTTP contract to build a request from

`child*` flows dominate the no-template group: the parent drives them internally,
so there is no gateway contract to build a request from. They are covered by
driving the parent, not by inventing an entry point.

## How to work it

1. Take the top table first — money plus a schedule is the worst place for a gap.
2. Drive the **real** flow locally; `run-the-real-thing-locally.md` is not optional
   here, and seeding the rows the job was meant to write proves nothing.
3. Assert exact column values, and watch the assert fail before the fix.
4. Add the case to `scripts/testing/registry.json` with a real `verify_mode`.
5. Re-run this script — the count moves on its own.

