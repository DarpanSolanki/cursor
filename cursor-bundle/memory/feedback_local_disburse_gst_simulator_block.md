# Local disburse dies on the GST simulator — drop the fee tax group, not the simulator

**Trigger:** TDPQA-240 (2026-08-04). Every local `disburseLoan` — INDL *and* SHG — returned
HTTP `code=0 / SUCCESS` while leaving the loan at `loan_status=APPROVED`,
`disbursement_status=LAN_CREATED`, `loan_amount=0`, 0 installments, 0 dues, `crr_counts={}`.

That is the "environment blocker" signature in `disburse-loan-sanity-suite.md`. It is **not**
product-specific and **not** the LOS/Kafka path — direct HTTP disburse fails the same way.

## Root cause

`postTransaction` calls GST before schedule/dues generation. The chameleon simulator returns
**HTTP 500** for `POST /simulate/xml/PS_GST_xelerateBusinessService`:

```
[ERROR] AbstractSoapPostWebServiceExecutor  Error while calling URL:
        http://localhost:8018/simulate/xml/PS_GST_xelerateBusinessService, Status Code: 500
[ERROR] GSTCalculatorService  Error while calling GST API
```

The `simulator_config` / `simulator_response` rows for it **do exist** (`mfi_simulator`,
config id 56, XML, response_code 200) — the 500 comes from inside the simulator, so repairing
the row is not the quick fix.

## Fix — remove the tax group from the fee, so GST is never called

GST is invoked because the charge's price setup carries `tax_group_id`. Null it for the fee
codes and the whole disburse path completes:

```sql
-- mfi_accounting.price_setup: 11 PROC_FEE, 25 ForceClosure, 27 ForeClosure,
-- 736 ForeClosure_New, 1 Part_Pre_Fees  (all tax_group_id = 4 on local)
UPDATE mfi_accounting.price_setup SET tax_group_id = NULL WHERE id IN (1,11,25,27,736);
```

Back the old values up first (`_tdpqa240_price_setup_tax_backup` was the pattern) and **restore
them when done** — this changes fee/tax composition for every local flow.

Then evict the Redis caches (DB 5) — a restart alone does **not** clear them:

```bash
redis-cli -n 5 --scan --pattern "*rice*" | xargs -r redis-cli -n 5 DEL
redis-cli -n 5 --scan --pattern "*tax*"  | xargs -r redis-cli -n 5 DEL
```

Safe for interest/force-bill tests: it removes GST legs, it does not touch interest accrual,
billing or the termination-suspense pass-through.

## Also

`agent-ops.sh before-test disburseLoan` hard-fails on "LOS required for Kafka-path disburse"
and tries to compile `trustt-platform-los`, which is currently broken
(`VerifyPreviousAccountNumberProcessor:200`). Pass `DISBURSE_ENTRY=http` to skip it.

## Pairs with

[[feedback_foreclosure_local_fixture_gates]] · [[feedback_dpic_harness_gotchas]]
