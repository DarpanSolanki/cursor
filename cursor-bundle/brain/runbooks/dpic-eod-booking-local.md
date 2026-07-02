# DPIC EOD — local booking / billing failures

> LMS-only path: `loanAccountDpdCalcJob` → `dpiAccrualCalculation` → `dpiAccrualBooking` → `dpiBilling`. Scripts: `scripts/dpic/`. Product **6367** / scheme **2655** / office **1** (internal accounts required).

## Symptom → first check

| Symptom | First SQL / log |
|---------|-----------------|
| Booking `readCount>0`, `writeCount=0` or `writeSkipCount=readCount` | `grep "postTransaction\|333\|office_id\|varchar" accounting-mfi.log` |
| Booking fails on 2nd+ row after first appears to post | `SELECT character_maximum_length FROM information_schema.columns WHERE table_name='dpi_accrual_details' AND column_name LIKE '%ref_number%';` — must be **64** |
| Booking `readCount=0` after prior failure | `SELECT * FROM mfi_accounting.batch_failure_audit WHERE context_value='<loan_account_id>';` then `scripts/dpic/sql/helpers/clear_batch_failure_audit.sql` |
| Calc rows exist, booking never runs | `grep "registered job: dpiAccrualBooking" accounting-mfi.log`; confirm calc finished before booking (avoid fixed 2s sleep race in `run_eod.sh`) |
| GL rules error 134207 placeholder | Product must link catalogues **1327–1330** + placeholders — `scripts/dpic/run_setup.sh` |

## Root causes (verified 2026-06-12, loan 8055060)

1. **`office_id` / `operation_mode` null** — DPI booking/billing batch only set `originating_office_id`. Interest booking sets both. Fix: `8d0df267f`.
2. **Txn ref `varchar(32)`** — `postTransaction` returns 37-char `reference_number`; `dpi_accrual_details.accrual_transaction_ref_number` was 32 → flush fails on 2nd row (error surfaces at `getTransactionCatalogueIdProcessor`). Fix: `V000187` + `@Column(64)` (`7e6f0e38` / `8d0df267f`). Local pre-Flyway: `scripts/dpic/sql/helpers/fix_dpi_txn_ref_column_length.sql`.
3. **Office has no internal accounts** — `resolvePlaceholder` needs IAD rows per office. Office **1** has DPI IADs; office **2** may have none (global unique `internal_account.code` blocks naive clone).

## Verification after fix

```sql
SELECT count(*) total, count(accrual_posting_date) booked, count(billing_posting_date) billed
FROM mfi_accounting.dpi_accrual_details
WHERE loan_account_id = <id> AND is_deleted = false;

SELECT component_type, due_amount, due_date
FROM mfi_accounting.loan_due_details
WHERE loan_account_id = <id> AND component_type = 'DPI' AND is_deleted = false;
```

## KG / changelog

Shipped fix case: `kg cases dpiAccrualBooking` · changelog `8d0df267f` + `7e6f0e38`.
