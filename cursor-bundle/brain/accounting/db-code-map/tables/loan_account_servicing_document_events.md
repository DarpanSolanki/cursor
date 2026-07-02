# `mfi_accounting.loan_account_servicing_document_events`

> Async queue of document-generation events triggered by servicing actions (foreclosure receipt, NOC, prepayment receipt, etc.). 13 cols. Drained by `loanAccountServicingDocumentEventsJob`.

## Schema (live, 13 cols)

| Column | Meaning |
|---|---|
| `id` (PK) | |
| `identifier_type` | Source event type (e.g. `FORECLOSURE`, `NOC`, `PART_PREPAYMENT_RECEIPT`) |
| `identifier_type_id` | FK into the source event table |
| `document_name`, `document_type` | What to generate |
| `document_fields` | JSON payload for the report engine |
| `status` | PENDING / IN_PROGRESS / COMPLETED / FAILED |
| `retry_count`, `error_message` | Retry tracking |
| `created_*`, `updated_*` | Audit |

## Writers

- Servicing flows that need a doc generated (foreclosure receipt, prepayment receipt, etc.) INSERT a PENDING row
- `loanAccountServicingDocumentEventsJob` UPDATEs status as it processes

## Readers

- `loanAccountServicingDocumentEventsJob` (the replayer)

## Related Requests

- `loanAccountServicingDocumentEventsJob` (scheduled in batch service)

## Related flows

- [Foreclosure](../../../flows/foreclosure-and-closure.md) — receipt PDF
- [Part-prepayment](../../../flows/loan-servicing/part-prepayment.md) — prepayment confirmation PDF

## Gotchas

1. **Async pattern** — failure here doesn't block the underlying servicing flow; doc generation retries via `retry_count`.
2. **Stuck PENDING rows** = doc-events job not running or fails on the row. Check `error_message`.
