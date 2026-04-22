# Repayment Flow Intelligence (accounting-v2; non-batch)

## Entry point
- Orchestration request: `loanRepayment` (`novopay-platform-accounting-v2/deploy/application/orchestration/loans_orc.xml` + `mfi_orc.xml` variants)
- Group (child) entry: `childLoanRepayment` (`group_mfi_orc.xml`)

## Ledger posting call (code-verified from ORC XML)
### `loanRepayment` (`loans_orc.xml`)
Contains **3** nested `postTransaction` calls:
1. `postTransaction` (TRIAL repayment)
   - Controlled by `trial_mode_post_transaction == true`
   - IParams include:
     - `transaction_type="${transaction_type}"`
     - `transaction_sub_type="${transaction_sub_type}"`
     - `amount="${repayment_amount}"`
     - `value_date="${valueDateLongInStr}"`
2. `postTransaction` (REAL repayment)
   - Controlled by `real_mode_post_transaction == true`
   - IParams include:
     - `transaction_type="${transaction_type}"`
     - `transaction_sub_type="${transaction_sub_type}"`
     - `amount="${repayment_amount}"`
     - `value_date="${valueDateLongInStr}"`
3. `postTransaction` (NPA reverse movement)
   - Controlled by `do_npa_reverse_movement == true`
   - IParams include:
     - `transaction_type="${transaction_type}"`
     - `transaction_sub_type="NPA"` (fixed)
     - `amount="${interest_amount}"`
     - `client_reference_number="${npa_client_reference_number}"`

### `childLoanRepayment` (`group_mfi_orc.xml`)
Contains **2** nested `postTransaction` calls:
1. `postTransaction` (REAL repayment)
   - IParams include:
     - `transaction_type="${transaction_type}"`
     - `transaction_sub_type="${transaction_sub_type}"`
     - `amount="${repayment_amount}"`
2. `postTransaction` (NPA reverse movement)
   - IParams include:
     - `transaction_type="${transaction_type}"`
     - `transaction_sub_type="NPA"` (fixed)
     - `amount="${interest_amount}"`
     - `client_reference_number="${npa_client_reference_number}"`

## How transaction type/sub-type are selected (code-verified from ORC XML)
### `loanRepayment`
Top-level dummy controls set:
- `repayment_mode=CASH|DIRDR|ACH` → `transaction_type="LOAN_REPAYMENT"`, `transaction_sub_type="CASH"`
- `repayment_mode=UPI` → `transaction_type="LOAN_REPAYMENT"`, `transaction_sub_type="UPI"`
- `repayment_mode=NET_BANKING` → `transaction_type="LOAN_REPAYMENT"`, `transaction_sub_type="NET_BANKING"`
- `repayment_mode=EXCESS_AMT` → `transaction_type="LOAN_REPAYMENT"`, `transaction_sub_type="EXCESS_AMT"` (with maker-checker disabled in the XML)

## Confidence / gaps
- High: posting call presence + parameter shapes per `postTransaction` nested API calls (ORC XML traces).
- Medium/UNVERIFIED: the exact processor list for repayment appropriation and how each component amount (PRIN/INT/PENAL/FEE/EXCESS) is mapped to placeholders (requires deeper processor-to-placeholder tracing).

