# Reversals + Manual Journal (accounting-v2)

## Core reversal engine: `reverseTransaction`
- Orchestration request: `reverseTransaction` in `product_transaction_orc.xml`
- Runs `reverseTransactionProcessor`:
  - `in.novopay.accounting.transaction.reverse.processor.ReverseTransactionProcessor#process(...)`

### How it finds the original transaction (code-verified)
Order:
1. `transaction_reference_number` from ExecutionContext (if present)
   - DAO lookup: `TransactionMasterDAOService.findOneByTransactionReferenceNumber(...)`
2. else `client_reference_number` from ExecutionContext (if present)
   - DAO lookup: `TransactionMasterDAOService.findOneByClientReferenceNumber(...)`
3. else fatal: `NovopayFatalException("130121")`

Failure guard:
- if the original master is already reversed (`originalTransactionMasterEntity.getReversed()==true`) → fatal `134071`

### How it reverses debit/credit (code-verified)
It creates a new `TransactionMasterEntity` with:
- reference prefixed: `referenceNumber = "R_" + original.referenceNumber`
- client reference prefixed: `clientReferenceNumber = "R_" + original.clientReferenceNumber`
- `reversal=true`, `reversed=false`

Then it:
1. reverses `transaction_partition_details` debit/credit by swapping `CrDrIndicator` (`C`<->`D`) while copying partition fields
2. reverses `transaction_details` debit/credit similarly

### Bank-leg reversal for `miscFundTransfer` (code absence in this repo snapshot)
- In this repo snapshot, `in.novopay.accounting.transaction.reverse.processor.ReverseTransactionProcessor` contains no code path referencing `miscFundTransfer` (and performs no external bank/reversal API calls).
- The `reverseTransaction` engine implemented here is accounting-only: it swaps `CrDrIndicator` for `transaction_partition_details` and `transaction_details`, and persists the reversal `TransactionMasterEntity` + reversed rows.

## Manual journal posting: `postManualJournalEntry`
- Orchestration request: `postManualJournalEntry` in `product_transaction_orc.xml`
- Dedupe guard:
  - `ClientReferenceNumberDedupProcessor` throws fatal `134067` on duplicate `(client_code, client_reference_number)`

## Manual journal reversal: `reverseManualJournalEntry`
- Orchestration request: `reverseManualJournalEntry` in `product_transaction_orc.xml`
- Uses `reverseTransactionProcessor` in maker-checker / approve control paths

## Confidence / gaps
- High: original transaction lookup + partition/details debit/credit swap behavior.

