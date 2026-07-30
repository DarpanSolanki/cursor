# Feedback — harness fidelity must match real prod/QA flow

**Date:** 2026-07-30  
**Trigger:** User: ntest/harness often asserts differently from real API flow → local PASS, QA/prod FAIL.

## Rule

Money `ntest` cases must **drive the same entry** as production/QA (batch apiName / HTTP Request / orch), wait real COMPLETED, and assert **values written by that path**.

Smart bypass is allowed when **declared** under `fidelity.seeded` (quarantine, fixture restore, labd gap, synthetic job_time). Masking a known prod failure (truncate `batch_failure_audit`, soft_fail FAILED batches, SQL-mutate Accrued then claim calc works) is **forbidden** as the default Pass path.

## Machine gate

- `scripts/lib/harness_fidelity_gate.py` (`check` / `report`)
- Wired into `ntest validate` + `registry_companion_gate`
- Inventory: `scripts/testing/harness_fidelity_inventory.json`

## Registry shape

```json
"fidelity": {
  "entry": "batch_api|http_api|orch_request|mixed|sim",
  "seeded": [{"key": "quarantine_portfolio", "reason": "..."}],
  "out_of_scope": ["..."],
  "layers_real": ["interestAccrualCalculation"]
}
```

## SHG stitch precedent

`flowtest.shg_int_accrual_stitch`: `CLEAR_BATCH_FAILURE_AUDIT` default **0**; `dateroll.roll` soft_fail default **False**.
