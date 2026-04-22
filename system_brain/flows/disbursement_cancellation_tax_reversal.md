# Disbursement Cancellation Tax Reversal (accounting-v2; code-verified)

## Where it is invoked
- Writer: `in.novopay.accounting.batch.disbursmentcancellation.writer.SGToDisbursementCancellationIWriter#doDisbursementCancellation(...)`
- Invocation point (code-verified):
- it posts `postTransaction` for `transaction_type = LOAN_DISB_CNCL`
- updates payments details + loan/account status
- then calls `initiateCancellationTaxReversalProcessor.execute(executionContext)`

## Core processor: `InitiateCancellationTaxReversalProcessor`
Class: `in.novopay.accounting.loan.cancellation.processor.InitiateCancellationTaxReversalProcessor`

## Inputs it reads from ExecutionContext (code-verified)
- `loan_account_entity`
- `loan_disbursement_charge_details_entity` (list)
- `loan_account_insurance_details_entity` (list)
- `disbursement_tax_details` (list; may be empty)
- `insurance_tax_details` (list)

## What it constructs for external GST reversal
- It builds `gstTaxedAmounts` by pairing:
- each disbursement charge details entity with its tax details entity by `identifierId`
- each insurance details entity with its tax details entity by `identifierId`
- It only includes tax rows when:
- `loanAccountTaxDetailsEntity.getExternalReferenceId()` is non-blank
- The constructed object tuple is used as the payload for the external GST call:
- index 0: amountToBePaid
- index 3: externalReferenceId
- index 4: `"DISBURSEMENT"` or `"INSURANCE"`
- index 5: identifierId
- index 6: `taxCalculatorAdaptor`
- index 7: gstInvoiceNumber

## External call executed (code-verified)
- When `gstTaxedAmounts` is non-empty it calls:
- `taxAmountUtiltyService.doGSTAmountExternalTransaction(executionContext, gstTaxedAmounts, (String) gstTaxedAmounts.get(0)[6], String.valueOf(loanAccountEntity.getOfficeId()), true)`

## Reversal flag update executed (code-verified)
- It updates reversal flags regardless of the external call outcome:
- `loanAccountTaxDetailsDAOService.updateReversalFlagForExternalReferenceId(externalReferenceIds, true)`

## Important behavioral detail (from code)
- External GST call is wrapped in `try/catch` that only logs errors; it does NOT throw.
- Because the reversal-flag update happens after the try/catch block, reversal flags can be set even if the external GST call logged an error.

