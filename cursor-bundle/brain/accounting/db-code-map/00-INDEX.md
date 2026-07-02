# Table coverage index — `mfi_accounting`

179 tables total. Coverage status below.

✅ = curated doc in `tables/`
🟡 = partial / stub
⬜ = not yet covered (use `tools/inspect-table.sh <name>` for live data)

## Tier 1 — Core LMS (~27 tables) ✅

### Loan account family
| Table | Coverage |
|---|:-:|
| `account` | ✅ [tables/account.md](tables/account.md) |
| `loan_account` | ✅ [tables/loan_account.md](tables/loan_account.md) |
| `loan_due_details` | ✅ [tables/loan_due_details.md](tables/loan_due_details.md) |
| `loan_installment_details` | ✅ [tables/loan_installment_details.md](tables/loan_installment_details.md) |
| `loan_repayment_schedule_details` | ✅ [tables/loan_repayment_schedule_details.md](tables/loan_repayment_schedule_details.md) |
| `loan_account_payments_details` | ✅ [tables/loan_account_payments_details.md](tables/loan_account_payments_details.md) |
| `loan_account_billing_details` | ✅ [tables/loan_account_billing_details.md](tables/loan_account_billing_details.md) |
| `loan_account_events_queue` | ✅ [tables/loan_account_events_queue.md](tables/loan_account_events_queue.md) |
| `loan_account_derived_fields` | ✅ [tables/loan_account_derived_fields.md](tables/loan_account_derived_fields.md) |

### Transaction family
| Table | Coverage |
|---|:-:|
| `transaction_master` | ✅ [tables/transaction_master.md](tables/transaction_master.md) |
| `transaction_partition_details` | ✅ [tables/transaction_partition_details.md](tables/transaction_partition_details.md) |
| `transaction_metadata` | ✅ [tables/transaction_metadata.md](tables/transaction_metadata.md) |
| `transaction_details` | ✅ [tables/transaction_details.md](tables/transaction_details.md) |
| `transaction_accounting_rule` | ✅ [tables/transaction_accounting_rule.md](tables/transaction_accounting_rule.md) |
| `transaction_catalogue` | ✅ [tables/transaction_catalogue.md](tables/transaction_catalogue.md) |

### GL family
| Table | Coverage |
|---|:-:|
| `general_ledger` | ✅ [tables/general_ledger.md](tables/general_ledger.md) |
| `child_general_ledger` | ✅ [tables/child_general_ledger.md](tables/child_general_ledger.md) |
| `internal_account` | ✅ [tables/internal_account.md](tables/internal_account.md) |
| `internal_account_definition` | ✅ [tables/internal_account_definition.md](tables/internal_account_definition.md) |
| `placeholder_master` | ✅ [tables/placeholder_master.md](tables/placeholder_master.md) |
| `account_balance` | ✅ [tables/account_balance.md](tables/account_balance.md) |

### Accrual + NPA + TB
| Table | Coverage |
|---|:-:|
| `interest_accrual_details` | ✅ [tables/interest_accrual_details.md](tables/interest_accrual_details.md) |
| `penal_interest_accrual_details` | ✅ [tables/penal_interest_accrual_details.md](tables/penal_interest_accrual_details.md) |
| `asset_criteria_master` | ✅ [tables/asset_criteria_master.md](tables/asset_criteria_master.md) |
| `asset_criteria_slabs` | ✅ [tables/asset_criteria_slabs.md](tables/asset_criteria_slabs.md) |
| `asset_classification_master` | ✅ [tables/asset_classification_master.md](tables/asset_classification_master.md) |
| `loan_product_asset_criteria` | ✅ [tables/loan_product_asset_criteria.md](tables/loan_product_asset_criteria.md) |
| `trial_balance` | ✅ [tables/trial_balance.md](tables/trial_balance.md) |

## Tier 2 — Servicing (~32 tables) ✅

### Servicing event tables (one per servicing flow)
| Table | Coverage |
|---|:-:|
| `loan_account_part_prepayment_details` | ✅ [tables/loan_account_part_prepayment_details.md](tables/loan_account_part_prepayment_details.md) |
| `loan_account_restructuring_details` | ✅ [tables/loan_account_restructuring_details.md](tables/loan_account_restructuring_details.md) |
| `loan_account_rebooking_details` | ✅ [tables/loan_account_rebooking_details.md](tables/loan_account_rebooking_details.md) |
| `loan_account_reopening_details` | ✅ [tables/loan_account_reopening_details.md](tables/loan_account_reopening_details.md) |
| `loan_account_reschedule_details` | ✅ [tables/loan_account_reschedule_details.md](tables/loan_account_reschedule_details.md) |
| `loan_account_excess_amount_refund_details` | ✅ [tables/loan_account_excess_amount_refund_details.md](tables/loan_account_excess_amount_refund_details.md) |
| `loan_account_closure_details` | ✅ [tables/loan_account_closure_details.md](tables/loan_account_closure_details.md) |
| `prepayment_details` | ✅ [tables/prepayment_details.md](tables/prepayment_details.md) |
| `prepayment_charge_details` | ✅ [tables/prepayment_charge_details.md](tables/prepayment_charge_details.md) |
| `loan_provisioning_details` | ✅ [tables/loan_provisioning_details.md](tables/loan_provisioning_details.md) |
| `transaction_reversal_details` | ✅ [tables/transaction_reversal_details.md](tables/transaction_reversal_details.md) |
| `waiver_details` | ✅ [tables/waiver_details.md](tables/waiver_details.md) |
| `waiver__loan_due_details` | ✅ [tables/waiver__loan_due_details.md](tables/waiver__loan_due_details.md) |
| `presentation_bounce_charge_details` | ✅ [tables/presentation_bounce_charge_details.md](tables/presentation_bounce_charge_details.md) |
| `loan_account_servicing_document_events` | ✅ [tables/loan_account_servicing_document_events.md](tables/loan_account_servicing_document_events.md) |

### Charges + tax
| Table | Coverage |
|---|:-:|
| `loan_account_charge_details` | ✅ [tables/loan_account_charge_details.md](tables/loan_account_charge_details.md) |
| `loan_account_tax_details` | ✅ [tables/loan_account_tax_details.md](tables/loan_account_tax_details.md) |

### Insurance + nominee + NOC
| Table | Coverage |
|---|:-:|
| `loan_account_insurance_details` | ✅ [tables/loan_account_insurance_details.md](tables/loan_account_insurance_details.md) |
| `loan_account_nominee_details` | ✅ [tables/loan_account_nominee_details.md](tables/loan_account_nominee_details.md) |
| `loan_account_noc_details` | ✅ [tables/loan_account_noc_details.md](tables/loan_account_noc_details.md) |
| `loan_account_noc_dispatch_details` | ✅ [tables/loan_account_noc_dispatch_details.md](tables/loan_account_noc_dispatch_details.md) |

### Death foreclosure cluster
| Table | Coverage |
|---|:-:|
| `death_foreclosure_details` | ✅ [tables/death_foreclosure_details.md](tables/death_foreclosure_details.md) |
| `death_foreclosure_appointee_details` | ✅ [tables/death_foreclosure_appointee_details.md](tables/death_foreclosure_appointee_details.md) |
| `death_foreclosure_nominee_details` | ✅ [tables/death_foreclosure_nominee_details.md](tables/death_foreclosure_nominee_details.md) |
| `death_foreclosure_payment_mode_details` | ✅ [tables/death_foreclosure_payment_mode_details.md](tables/death_foreclosure_payment_mode_details.md) |

### Disbursement (mechanics + cancellation)
| Table | Coverage |
|---|:-:|
| `loan_disbursement_charge_details` | ✅ [tables/loan_disbursement_charge_details.md](tables/loan_disbursement_charge_details.md) |
| `loan_disbursement_mode_details` | ✅ [tables/loan_disbursement_mode_details.md](tables/loan_disbursement_mode_details.md) |
| `loan_disbursement_transaction` | ✅ [tables/loan_disbursement_transaction.md](tables/loan_disbursement_transaction.md) |
| `loan_repayment_mode_details` | ✅ [tables/loan_repayment_mode_details.md](tables/loan_repayment_mode_details.md) |
| `loan_disbursement_cancellation_details` | ✅ [tables/loan_disbursement_cancellation_details.md](tables/loan_disbursement_cancellation_details.md) |
| `loan_disbursement_cancellation_charge_details` | ✅ [tables/loan_disbursement_cancellation_charge_details.md](tables/loan_disbursement_cancellation_charge_details.md) |

## Tier 2 — minor sister tables not separately curated

These are small auxiliary tables (5-10 cols, mostly document linkage). Use `tools/inspect-table.sh` for live schema. Each is conceptually covered by the parent table's doc.

- `loan_account_rebooking_details__document` — see [`tables/loan_account_rebooking_details.md`](tables/loan_account_rebooking_details.md)
- `loan_account_reopening__document` — see [`tables/loan_account_reopening_details.md`](tables/loan_account_reopening_details.md)
- `loan_disbursement_cancellation_details__document` — see [`tables/loan_disbursement_cancellation_details.md`](tables/loan_disbursement_cancellation_details.md)
- `death_foreclosure_details__document` — see [`tables/death_foreclosure_details.md`](tables/death_foreclosure_details.md)
- `death_foreclosure_insurance_staging_details` (67 cols) — covered conceptually in [death-foreclosure flow doc](../../flows/loan-servicing/death-foreclosure.md) §STAGE_4-5
- `disbursement_cancellation_insurance_staging_details` (39 cols) — covered in [disbursement-cancellation flow](../../flows/loan-servicing/disbursement-cancellation.md) §"Insurance reversal"
- `loan_account_noc_details_block_unblock_reason` — block/unblock audit; see `loan_account_noc_details`
- `transaction_reversal__document`, `prepayment__document`, `manual_journal_entry_details__document`, `waiver__document` — generic doc-linkage tables, all 5 cols
- `loan_account_payments_details__loan_due_details` (linkage)

## Tier 3 — Mandates (~30 tables) ⬜ (use inspect-table.sh)

`enach_presentation_*` (3 tables), `enach_representation_*` (2 tables),
`si_presentation_*` (3 tables), `si_lien_presentation_file_details`, `si_auto_hold_*` (1),
`si_manual_hold_marking_*`, `si_manual_hold_presentation_*`, `si_manual_hold_removal_*`, `si_manual_presentation_*`,
`si_failed_presentation_details`, `lien_presentation_details`,
`repayment_account_details`, `repayment_mandate_details`, `repayment_mandate_details__document`

For mandate flows (NACH, eNACH, SI), see [`../05-flows.md`](../05-flows.md) §3 + [`tables/loan_repayment_mode_details.md`](tables/loan_repayment_mode_details.md).

## Tier 4 — Bulk staging + masters (~50 tables) ⬜

All `file_staging_*` (16), tax cluster (4), pricing cluster (4), interest setup cluster (7), product cluster (6),
insurance product cluster (3), stamp duty (2), currency, holiday (2), working days (2),
manual journal entry (2). Use `tools/inspect-table.sh <name>`.

## Tier 5 — Misc (~20 tables) ⬜ low priority

`accounting_dump`, `bulk_collection_log`, `client_request_response_log`, `batch_failure_audit`,
`flyway_schema_history`, `sequences`, `task_cleanup_detail`, `accts_under_pc_180_staging_table`,
`accts_under_pc_182_staging_table`, `temp_unique_gl_code_office_id`, `opening_balance`,
`portfolio_transfer_details`, `savings_account`, `savings_product`, `savings_product__general_ledger`,
`savings_product_services_offered`, `transaction_category`, `transaction_catalogue__transaction_category`,
`account_interest_details`, `premium_calculation_details`

## Quick search

```bash
# Find a table whose name you partially remember
/home/darpan/darpan/claude/db-tools/bin/db-query.sh mfi_qa3 --sql "
SELECT table_name FROM information_schema.tables
 WHERE table_schema='mfi_accounting' AND table_name LIKE '%<part>%'
 ORDER BY 1;"
```

## Live deep inspection of any table

```bash
/home/darpan/darpan/claude/accounting/db-code-map/tools/inspect-table.sh <name>
```

Always works. Returns: schema + indexes + row count + entity location + processors + Requests.

## Curated count

**59 tables curated** with full code anchors:
- Tier 1: 27 ✅ — core LMS (loan, transaction, GL, accrual, NPA, TB)
- Tier 2: 32 ✅ — every servicing flow's tables (part-prepayment, restructuring, rebooking, reopening, reschedule, refund, closure, prepayment, provisioning, txn reversal, waiver, charges, tax, insurance, nominee, NOC, death-foreclosure cluster, disbursement mechanics + cancellation)

Plus **6 by-flow walkthroughs** in [`by-flow/`](by-flow/) showing tables-touched-per-flow in execution order.
