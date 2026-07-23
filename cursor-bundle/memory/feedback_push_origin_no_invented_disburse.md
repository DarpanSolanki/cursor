# Push-origin hang on invented disburseLoan (SP-308 aftermath)

**Standing (2026-07-23):** Pushing knowledge/SMS notification changes must **never** invent `disburseLoan` and run `disburse-quick`.

## What stuck

`push-origin.sh` → auto `workspace-close` → money tier → `ntest run disbursement.quick` → `disburse-quick.sh` (multi-minute E2E). Triggered because pending ship misclassified notification L0/L1 as money and `kg_ship_resolve` defaulted `MessageBroker.xml` → `disburseLoan`.

## Fixes

- `kg_ship_resolve.py`: remove MessageBroker→disburseLoan default; map installment notification paths to due/bounce job apis
- `infer_ship_apis.py`: notification SMS paths = **service** not money
- `push-origin.sh`: knowledge-only HEAD skips auto workspace-close
- Regression: `scripts/lib/test_kg_ship_resolve_notification.py`
