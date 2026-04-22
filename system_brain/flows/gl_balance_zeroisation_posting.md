# GL Balance Zeroisation (accounting-v2; non-`postTransaction` entry)

## Entry point
- Orchestration request: `glBalanceZeroisation` in `novopay-platform-accounting-v2/deploy/application/orchestration/product_transaction_orc.xml`
- It does NOT call the `postTransaction` orchestration request. Instead it directly creates `transaction_master` + `transaction_partition_details` + `transaction_details` via the GL zeroisation processor chain.

## Routing (code-verified write path)
- Condition: `function_sub_code = TRANSACTION`
- Condition: `function_code = DEFAULT`

## Processor chain (ORC wiring; code-verified)
1. `populateUserDetails`
2. `populateCurrentDateProcessor`
3. `setCommonAttributesProcessor`
4. `clientReferenceNumberDedupProcessor`
- de-dupes on `client_reference_number = gl_transaction_reference_number`
5. `validateAndPopulateDataForGLZeroisation`
6. `getTransactionCatalogueIdProcessor`
7. `generateTransactionReferenceNumberProcessor`
8. `createTransactionMasterProcessor`
- uses `total_posting_amount` + `currency`
9. `createTransactionMetadataProcessor`
10. `createPartitionDetailsForGLZeroisation`
11. `createTransactionPartitionDetailsProcessor`
12. `createTransactionDetailsProcessor` (ledger line persistence, sign + skip behavior)

## What `validateAndPopulateDataForGLZeroisation` computes
Inputs read from `ExecutionContext`:
- `dr_gl_code`
- `cr_gl_code`
- `amount`

Key derived outputs (code-verified):
- `accounting_map: Map<internalAccountNumber, netAmount>`
- debit internal account netAmount = `-amount`
- credit internal account netAmount = `amount`
- `account_number_dr_cr_map: Map<internalAccountNumber, CrDrIndicator>`
- if `netAmount < 0` => `CrDrIndicator.D`
- else => `CrDrIndicator.C`
- `total_posting_amount = sum(amount)`
- `transaction_type` / `transaction_sub_type` from config:
- `zeroisation.transaction.catalogue.type` (default `FINANCIAL_YEAR`)
- `zeroisation.transaction.catalogue.subtype` (default `ZEROISATION`)

## How the partition/details are created
`createPartitionDetailsForGLZeroisation` (code-verified):
- builds `transaction_partition_details_list`
- uses `ExecuteTransactionRulesProcessor.createPartitionDetails(...)` with:
- amount = `accountingSummaryDTO.getNetAmount().abs()`
- Cr/Dr = `accountNumberDrCrDTO.getCrDrIndicator()`
- glCode = mapped from internal account definition

`createTransactionPartitionDetailsProcessor` (code-verified):
- persists partitions
- builds `account_gl_map: Map<accountNumber, glCode>` used by `createTransactionDetailsProcessor`

## Debit/Credit + sign mapping for `transaction_details`
`in.novopay.accounting.transaction.processor.CreateTransactionDetailsProcessor` applies:
- for each entry in `accounting_map`:
- if `netAmount > 0` => `cr_dr_indicator = CrDrIndicator.C` and persists `netAmount = abs(netAmount)`
- if `netAmount < 0` => `cr_dr_indicator = CrDrIndicator.D` and persists `netAmount = abs(netAmount)`
- if `netAmount == 0` => skips creating a `transaction_details` row for that account

## Notes for debugging
- If you see missing GL lines, confirm `accounting_map` entries are non-zero (netAmount==0 lines are skipped).
- If you see wrong line direction, confirm `dr_gl_code/cr_gl_code` -> internal account mapping and ensure `amount` sign expectations match the ORC inputs.

