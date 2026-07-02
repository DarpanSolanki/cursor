# `mfi_accounting.presentation_bounce_charge_details`

> Per-bounce charge log. 11 cols. Created when a NACH/eNACH presentation bounces; bounce charges levied here.

## Schema

| Column | Meaning |
|---|---|
| `id` (PK), `loan_account_id` | |
| `mandate_reference_number` | Bounced mandate |
| `mandate_missed_on_date` | Date of bounce |
| `mandate_amount` | Amount that bounced |
| `bounce_charges_applied` | Charge levied |
| `created_*`, `updated_*`, `is_deleted` | Audit |

## Writers

- `loan/charges/processor/...` — INSERT during NACH/eNACH bounce processing
- `enach_representation` flow — picks up bounces and re-presents

## Readers

- 360 view, collection 360
- Bounce-charge reconciliation

## Related flows

- (Tier 3 mandate flows — see [`../00-INDEX.md`](../00-INDEX.md) for mandate table list)

## Gotchas

1. **Drives `loan_account.enach_bounce_count`** denormalisation.
2. **Bounce charge** is itself a charge (entries in `loan_account_charge_details` may follow).
