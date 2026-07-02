# `mfi_accounting.transaction_metadata`

> Free-form key/value bag for a transaction. One row per `transaction_master`.

## Purpose

Stores arbitrary caller-supplied metadata that doesn't fit the structured columns of `transaction_master`. Used for tracing, replay context, custom integration tags.

## Schema

Typical columns (verify with `tools/inspect-table.sh transaction_metadata`):

| Column | Meaning |
|---|---|
| `id` | PK |
| `transaction_master_id` | FK |
| `key`, `value` (or JSON column) | Per-call metadata |
| `created_on` | |

## Writers

- `CreateTransactionMetadataProcessor` — `postTransaction` REAL mode

## Readers

- Statement / 360-view aggregators

## Related Requests

- `postTransaction`
- `getTransactionPartitionDetails` (joined for context)
