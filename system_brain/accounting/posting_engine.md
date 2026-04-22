# Accounting Posting Engine (postTransaction)

## Core entrypoint
The platform’s ledger write path converges on accounting-v2’s orchestration request `postTransaction` (see `product_transaction_orc.xml` in the accounting-v2 module).

## Placeholder -> account/GL resolution
`postTransaction` relies on `ExecutionContext` keys populated by processors to:
- resolve `account_details[]` placeholders into actor account numbers and internal account definitions
- resolve GL codes via account/internal account definitions

## Debit/Credit direction + amount sign mapping (code-verified)
Processor: `in.novopay.accounting.transaction.processor.CreateTransactionDetailsProcessor`

For each entry in `accounting_map`:
- if `netAmount > 0`:
  - `cr_dr_indicator = CrDrIndicator.C`
  - persist `netAmount = abs(netAmount)`
- if `netAmount < 0`:
  - `cr_dr_indicator = CrDrIndicator.D`
  - persist `netAmount = abs(netAmount)`
- if `netAmount == 0`: skip row creation for that account

GL and child-GL:
- `glCode` is read from `executionContext["account_gl_map"]` using the `account_number` key
- `child_gl_code` is set from `executionContext.getBooleanValue("is_child_account")`

## Confidence / gaps
- High: sign mapping + fields used by `CreateTransactionDetailsProcessor` (code-verified).
- Medium/UNVERIFIED: full partition-level D/C and rule engine mapping (not re-read in this session; see `.cursor/rules/accounting.mdc` Module reference).

