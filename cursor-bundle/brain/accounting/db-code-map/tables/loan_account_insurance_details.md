# `mfi_accounting.loan_account_insurance_details`

> Per-loan bound insurance policy (life or health). 32 cols. Set at disbursement; updated during death-foreclosure / cancellation.

## Schema (live, 32 cols — selected)

| Column | Meaning |
|---|---|
| `id` (PK), `loan_account_id` | |
| `applicable_for` | BORROWER / CO_BORROWER / SPOUSE etc. |
| `insurance_product_code`, `insurance_provider_code` | masterdata FKs (HDFC Life / HDFC Ergo / Bajaj Ergo) |
| `premium_calc_code` | Calc-matrix code |
| `policy_type` | LIFE / HEALTH |
| `insured_gender`, `insured_age`, `insured_name`, `insured_dob`, `insured_address`, `insured_mobile_no`, `insured_pob` | Insured-person details |
| `insured_duration_frequency`, `insured_duration` | Coverage period |
| `sum_assured`, `premium_amount`, `total_tax_amount` | Money |
| `policy_number` | Provider-issued |
| `policy_start_date`, `policy_end_date` | |
| `claim_amount` | Set on death-foreclosure FTR |
| `status` | ACTIVE / CLAIMED / CANCELLED / EXPIRED |
| `is_posted` | Has insurance premium been GL-posted? |
| `is_deleted` | Soft-delete |
| `approved_*`, `created_*`, `updated_*` | Audit |

## Writers

- Disbursement: `outboundDisbursement<Provider>InsuranceJob` + inbound counterpart write/update
- `bulkSGToPostDisbursementInsuranceUpdateJob` — bulk updates
- Death-foreclosure inbound — UPDATE `claim_amount`, `status=CLAIMED`
- Cancellation: `outboundDisbursementCancellation<Provider>InsuranceJob` — UPDATE `status=CANCELLED`

## Readers

- `getLoanAccountInsuranceList` Request
- Death-foreclosure flow (read provider routing)
- 360 view

## Related Requests

- `disburseLoan`, `loanDeathForeclosure`, `loanDisbursementCancellation`
- All insurance jobs in `loans_insurance_orc.xml`
- `validateInsurance`, `getInsurancePremiumAmount`

## Related flows

- [Death foreclosure](../../../flows/loan-servicing/death-foreclosure.md)
- [Disbursement](../../../flows/disbursement-end-to-end.md) — insurance bound here
- [Disbursement cancellation](../../../flows/loan-servicing/disbursement-cancellation.md)

## Gotchas

1. **One loan can have multiple rows** — separate policies for borrower / co-borrower / spouse.
2. **`is_posted=false`** = premium GL hit not yet booked; usually rectified via `bulkSGToPostDisbursementInsuranceUpdateJob`.
3. **`claim_amount`** populated only on FTR (Free To Recover) — for FTNR (Free To Not Recover), stays NULL/0.
