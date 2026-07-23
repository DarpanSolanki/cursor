# loanWriteoff — final write-off posting

## Symptom
Write-off runs but appropriation/GL splits look wrong, NPE on money keys, or dues don’t match `writeoff_amount`.

## Entry
- **Request:** `loanWriteoff` (accounting `loans_orc.xml`)
- **Nested posting:** `postTransaction` after appropriation
- **High risk:** GAP-062 — EC key mismatch vs `PrepaymentApproppriationProcessor`

## Spine (money path)
1. Validate write-off inputs (`ValidateLoanWriteOffDataProcessor` — uses `value_date`, sets `penalty_amount`)
2. Appropriation branch (`prepaymentApproppriationProcessor`) expects **`total_foreclosure_amount`**, **`penal_amount`**, **`foreclosure_date`**, **`fee_amount`**
3. Orch currently passes **`prepayment_amount`** = `${writeoff_amount}` and may omit aligned keys → wrong splits / NPE
4. `populateAdditionalAmountDetailsProcessor` for PRIN/INT/FEE/PENALTY/(DPI) → nested `postTransaction`

## Tables (typical)
`loan_account`, `loan_due_details`, `transaction_master`, `transaction_details`, write-off detail tables

## Fail closed
Do not “fix” by guessing EC keys — align orch ↔ processor contract (GAP-062) before money ship.

## See also
- `.cursor/gaps-and-risks.md` GAP-062
- `.cursor/skills/accounting-knowledge/flows.md`
