# `mfi_accounting.death_foreclosure_appointee_details`

> Guardian for an under-age nominee. 17 cols. Required only when `death_foreclosure_details.is_nominee_under_age = true`.

## Schema (live, 17 cols)

| Column | Meaning |
|---|---|
| `id` (PK) | |
| `death_foreclosure_details_id` | FK |
| `appointee_name`, `appointee_dob`, `appointee_gender` | Identity |
| `appointee_relationship_with_member` | masterdata |
| `appointee_mobile_number`, `appointee_email` | Contact |
| `appointee_address_line_1`, `appointee_address_line_2`, `appointee_landmark`, `appointee_pincode` | Address |
| `appointee_village_id`, `appointee_village_name`, `appointee_district`, `appointee_state` | Geography |
| `is_address_same_as_borrower` | Boolean shortcut |

## Writers

- STAGE_1 of [death-foreclosure](../../../flows/loan-servicing/death-foreclosure.md) when `is_nominee_under_age=true`

## Readers

- Death-fc 360 view, insurer outbound file builder
