# DPI money proof — mandatory (STANDING)

**Lesson (SDCP-10497 + audit 2026-06-26):** `batch.dpi_*` SUCCESS is not money proof. Harness must assert **row-level** state via SQL helpers.

## Before DPI ship / QA hand-off

```bash
bash scripts/bin/dpi-booking-posting-guard.sh
bash scripts/bin/dpi-money-proof.sh          # post-EOD + billing UD
# full: bash scripts/bin/agent-ops.sh verify-dpi-proof
```

## Ship-loop auto-guards (money tier)

- `dpic.posting_calendar_regression` — multi-day booking replay
- `dpic.cross_eod_replay_134497` — billing client_ref idempotency
- `dpic.billing_ud_next_emi` — `verify_dpi_billing_ud.sql` (next EMI due, aggregated txn)

## Known remaining gaps (not in default ship)

- Maturity monthly billing anchor (`DpiBillingBatchService` while-loop)
- NPA GL legs at booking batch (only consumer NPA movement tested)
- Calc `carry_over_amount` / month-end row split
- Booking cross-EOD replay isolated (billing replay only)

Track in `scripts/workspace-backlog.json` WS-016+.

Rule: `.cursor/rules/dpi-money-proof-gate.mdc`
