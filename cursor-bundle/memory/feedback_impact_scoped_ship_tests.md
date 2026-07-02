# Impact-scoped ship tests — workspace-wide (standing)

**Never** sweep all `smoke_tier=money` registry cases for a touched apiName. Ship-loop runs **minimal cases for the diff**.

## Engine

`scripts/lib/resolve_ship_cases.py` — single resolver used by `infer_ship_apis.ntest_cases_for_impact` → `build_impact` → `ship-loop-gate.sh` → `register_pending_ship.py`.

## Rules

1. **Ship-auto** (default on ship): `type=batch`, `type=health`, `quick=true` API without `regression`/`certify`/`demo` tags, `disbursement.quick`.
2. **Never auto**: `ship_scope: manual|release|ci`, tags `regression`, `certify`, `doctor`, `demo`, `perf`, full DPI/DCF suites, `disbursement.jlg|shg`.
3. **Path-triggered flows**: foreclosure write, death FC, DPI go-live/grace/multi, repayment e2e — only when path hints match.
4. **DPI slice**: calc / booking / billing batches + targeted `dpic.*` — not `dpic.ud_compliance`.
5. **Full regression**: `dpi-sanity.sh`, `verify-dpi`, `ntest run dpic.ud_compliance`, `workspace.doctor.full` — manual/CI only.

## Domain path hints (examples)

| Path touch | Ship cases |
|------------|------------|
| `disburse`, `neft`, `clmt` | `disbursement.quick` |
| `individualChildLoanForeclosure` | `foreclosure.individual_child` |
| `deathForeclosure`, `dcf_` | `foreclosure.dpi_waiver_smoke` |
| `dpiAccrualCalculation` + go-live | `batch.dpi_calc`, `dpic.go_live_ud` |
| `dpiAccrualBooking` + posting | `batch.dpi_booking`, `dpic.go_live_ud` |
| Shared util only (no flow path) | **no** extra API smokes |

## Verify

```bash
python3 scripts/lib/infer_ship_apis.py --path <changed-file> --ntest-cases
python3 scripts/lib/infer_ship_apis.py --path <f1> --path <f2> --impact-json
```
