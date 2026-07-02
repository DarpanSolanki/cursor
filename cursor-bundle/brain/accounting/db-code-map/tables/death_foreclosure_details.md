# `mfi_accounting.death_foreclosure_details`

> Per-death-claim record. 31 cols. The header for the entire 6-stage death-foreclosure flow.

## Schema (live, 31 cols — selected)

| Column | Meaning |
|---|---|
| `id` (PK), `loan_account_id` | |
| `deceased_person`, `deceased_person_name` | Identity |
| `date_of_death`, `place_of_death`, `cause_of_death`, `date_of_birth` | Death info |
| `claim_type` | NATURAL / ACCIDENTAL / etc. |
| `date_of_diagnosis`, `date_of_accident` | If applicable |
| `death_claim_form_document_id` | FK → DMS doc (the generated PDF) |
| `is_nominee_under_age` | If true, appointee is required |
| `group_id`, `group_name` | SHG/JLG context |
| `excess_amount`, `outstanding_loan_balance`, `balance_claim_amount` | Money |
| `fr_reasons`, `fr_comments` | FTR/FTNR insurer-side info |
| `death_foreclosure_status` | Workflow status |
| `task_id`, `task_status` | Task linkage |
| `reject_reason`, `reject_notes` | If rejected |
| `approved_*`, `created_*`, `updated_*` | Audit (timestamp WITH timezone) |

## Sister tables

- [`death_foreclosure_appointee_details`](death_foreclosure_appointee_details.md) — guardian if nominee minor
- [`death_foreclosure_nominee_details`](death_foreclosure_nominee_details.md) — confirmed nominee at claim time
- [`death_foreclosure_payment_mode_details`](death_foreclosure_payment_mode_details.md) — how nominee will receive money
- `death_foreclosure_details__document` (5 cols) — list of supporting documents
- `death_foreclosure_insurance_staging_details` (67 cols) — outbound-to-insurer + inbound-from-insurer staging

## Writers

- `createOrUpdateDeathForeclosureDetailsProcessor` — INSERT (PENDING) at STAGE_1
- `syncDetailsForDeathForeclosureProcessor` — pre-fills from loan + insurance + nominee
- `excessAmountDeathForeclosureDetailsProcessor` — computes excess
- Insurance inbound jobs — UPDATE `fr_reasons`, `fr_comments`, `balance_claim_amount` on FTR/FTNR

## Readers

- `getDeathForeclosureDetails` Request
- `deathForeclosureDedupCheckProcessor` — refuses if death-fc already in progress
- 360 view

## Related flows

- [Death foreclosure](../../../flows/loan-servicing/death-foreclosure.md) — the 6-stage flow

## Common queries

```sql
-- Active death-fc cases
SELECT a.account_number, dfd.death_foreclosure_status, dfd.deceased_person_name,
       dfd.date_of_death, dfd.task_status, la.loan_status
  FROM mfi_accounting.death_foreclosure_details dfd
  JOIN mfi_accounting.loan_account la ON la.account_id = dfd.loan_account_id
  JOIN mfi_accounting.account a ON a.id = la.account_id
 WHERE dfd.death_foreclosure_status NOT IN ('CLOSED','REJECTED')
 ORDER BY dfd.created_on;
```
