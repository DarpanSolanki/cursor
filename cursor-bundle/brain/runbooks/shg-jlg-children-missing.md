# Runbook — SHG/JLG children missing

## Symptoms

- Parent loan_account is `ACTIVE`; `getChildLoanAccountList` returns empty.
- 360 view shows the group exists but no member-level loans.
- A specific group member's loan is missing while siblings exist.

## First SQL

```sql
-- Parent
SELECT id FROM mfi_accounting.account
 WHERE account_number = ? AND parent_account_id IS NULL;

-- Pending CLB events for the parent
SELECT id, event_type, event_status, created_on, updated_on,
       SUBSTRING(data, 1, 200) AS data_preview
  FROM mfi_accounting.loan_account_events_queue
 WHERE parent_account_id = <parent_id> AND event_type = 'CLB';

-- All children currently present
SELECT child.account_number, child.fraction, child.loan_status, child.disbursement_status
  FROM mfi_accounting.loan_account child
  JOIN mfi_accounting.account ca ON ca.id = child.account_id
 WHERE ca.parent_account_id = <parent_id>;

-- All pending events for the parent (any type)
SELECT id, event_type, event_status, created_on
  FROM mfi_accounting.loan_account_events_queue
 WHERE parent_account_id = <parent_id> AND event_status = 'P'
 ORDER BY id;
```

## Decision tree

### A. CLB row exists with `event_status = 'P'`

The replayer didn't run, or it ran and failed. **Both stay at `P` forever** — the processor catches all exceptions and only logs them ([`ChildLoanEventsProcessingProcessor.java:70-72`](../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/loan/grouploan/events/queue/ChildLoanEventsProcessingProcessor.java#L70-L72)).

Steps:
1. Check `mfi_batch.batch_schedule WHERE name = 'childLoanEventProcessingBatchJob'` — `last_run_on`, `last_completion_status`.
2. If `last_completion_status = COMPLETED` recently, the job ran but failed silently on this row. **Check the application log** for `ChildLoanEventsProcessingProcessor` ERROR around the relevant timestamp. Common causes:
   - Bad JSON in `data` column
   - Missing `transaction_accounting_rule` row for child posting
   - Missing `internal_account` instance for office (engine error `134182`)
   - Missing `product_transaction_catalogue_placeholder` (engine error `134207`)
3. After fixing the root cause, manually re-fire the batch (it picks up rows with `event_status = 'P'` again on next run).
4. **DO NOT manually flip event_status='C'** without children existing — it suppresses the only signal that fan-out is incomplete.

### B. CLB row exists with `event_status = 'C'` but no children

The job marked the row complete without inserting children. Inspect the JSON data:
1. Verify `data` is a valid JSON array with one object per child (each containing `external_ref_number`, `fraction`, etc.).
2. If the data was corrupt at queue time, the parent disbursement flow has a bug (`CreateClmtLoanAccountEventsProcessor`).
3. For one-off recovery, manually reset `event_status = 'P'` on the row (after fixing data if needed) — the next batch run replays.

### C. No CLB row at all

The parent disbursement never reached `PARENT_SUCCESS`, so `CreateClmtLoanAccountEventsProcessor` never ran. **This is actually a disbursement-stuck case** for the parent — see [`disbursement-stuck.md`](disbursement-stuck.md).

### D. Some children present, some missing

Either:
1. The CLB event ran partially (some children inserted, then failed before completing the batch). Check `audit_log` for the CLB run — count children expected vs created.
2. A subsequent `CANCL` event removed specific children. Check `loan_account_events_queue` for `event_type = 'CANCL'` rows.

### E. Children present but parent `ACTIVE` while children `APPROVED`

Per-child `childLoanDisbursement` ran (children created with `loan_status = APPROVED`) but the per-child status update to `ACTIVE` didn't fire. Look at `bookChildLoanProcessor` log — likely a bank-call issue per child.

## Cross-cutting checks

```sql
-- All "stuck-P" events across the system (catch any leak)
SELECT parent_account_id, event_type, COUNT(*) AS stuck
  FROM mfi_accounting.loan_account_events_queue
 WHERE event_status = 'P'
   AND created_on < NOW() - INTERVAL '1 hour'
 GROUP BY parent_account_id, event_type
 ORDER BY stuck DESC;
```

If many parents are affected, the batch service is paused / mis-tenanted / crashing — escalate.

## Code anchors

- Replayer: [`ChildLoanEventsProcessingProcessor.java`](../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/loan/grouploan/events/queue/ChildLoanEventsProcessingProcessor.java)
- Event-queue entity + type map: [`LoanAccountEventsQueueEntity.java:50-66`](../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/account/loans/entity/LoanAccountEventsQueueEntity.java#L50-L66)
- EMI splitter: [`GroupLoanUtility.java`](../../novopay-platform-accounting-v2/src/main/java/in/novopay/accounting/loan/grouploan/utility/GroupLoanUtility.java)

## Related

- SHG/JLG model: [`../accounting/06-shg-jlg-group-loans.md`](../accounting/06-shg-jlg-group-loans.md)
- Group loan flow: [`../flows/shg-jlg-group-loan.md`](../flows/shg-jlg-group-loan.md)
- Disbursement stuck: [`disbursement-stuck.md`](disbursement-stuck.md)
