# postManualJournalEntry — finance correction GL

## Symptom
Manual journal fails validation, posts unbalanced legs, or lacks CI/regression coverage (High test-coverage gap).

## Entry
- **Request:** `postManualJournalEntry` (accounting orchestration)
- **Related:** `reverseTransaction`, `glBalanceZeroisation` (year-end / correction cluster)

## What it does
Maker/checker (when enabled) → validate GL accounts / amounts → persist manual journal detail rows → nested or direct posting into `transaction_master` / `transaction_details` / GL balance paths.

## Tables (typical)
`manual_journal_entry_details`, `manual_journal_entry_gl_details`, `transaction_master`, `transaction_details`, `general_ledger` / balance tables

## Ops notes
- No `src/test` hits historically — treat as high-blast finance path; verify with `kg flow postManualJournalEntry` + DB asserts on legs.
- Prefer additive template fields; never loosen debit/credit balance checks.

## See also
- `.cursor/test-coverage-map.md`
- `.cursor/skills/accounting-knowledge/gl-and-placeholders.md`
