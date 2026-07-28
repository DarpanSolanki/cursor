# DPIC testing harness gotchas (mandatory — agents must read before declaring harness FAIL = product bug)

**Standing rule:** When a `dpic.*` ntest or `run_dpi_*_e2e.sh` fails, classify **harness vs product** before touching Java.

## Two clocks (most common agent trap)

| Clock | Source | Used for |
|-------|--------|----------|
| **Fixture JOB_TIME** | registry env / `dpi_fixture_constants.sh` | `dpiAccrualCalculation`, `dpiAccrualBooking`, `dpiBilling` batch `--job-time` |
| **Platform business date** | `PlatformDateUtil` / wall-clock IST today | `loanRepayment`, `loanAccountTransactionReversal`, `loanAccountPartPrepayment` timestamps |

**Never** set `repayment_time` from `JOB_TIME`. Use `dpic_platform_repay_ms()` from `scripts/dpic/lib/dpic_harness_lib.sh`.

SQL `UPDATE mfi_masterdata.configuration SET prop_value=...` for `current.business.date` does **not** reliably refresh JVM cache — do not depend on it for repayment; use wall-clock platform date for money APIs.

## API contract vs registry asserts

| API | Harness rule |
|-----|----------------|
| `getLoanAccountOverviewDetails` | `dpi_paid_amount` / `dpi_waived_amount` **omitted** when no DPI rows in due query — do **not** `path_exists` them. Use `total_accrued_dpi_amount` + `payment_details_list[].dpi_amount`. |
| `getLoanAccountSummaryDetails` | `dpi_details` block defaults zeros — different from overview. |
| `loanAccountPartPrepayment` | JTF nest: `request.loan_account_part_prepayment.{loan_account_number,...}` — flat keys → **130241**. |
| `loanRepayment` | JTF nest: `request.loan_repayment_details.{account_number,...}`; `function_sub_code=WITHOUT_MAKER_CHECKER`. |

## Error code → likely layer

| Code | Likely layer | Fix |
|------|--------------|-----|
| **132280** | Harness | `repayment_time` ≠ platform today → `dpic_platform_repay_ms` |
| **134243** | Harness/fixture | Repay amount > unsettled + advance EMI → `dpic_compute_safe_repay_amount` / `DPI_REPAY_CAP` |
| **130241** | Harness | JTF nest missing |
| **134207** | Harness/fixture | NPA PTC placeholder — regular slab or different LAN |
| **134303** | Product (TDPQA-188) | `due_amount` equality included unbilled BPD — fixed in validator |

## Assert discipline

- **DPI paid after repay:** assert `loan_account_payments_details.dpi_amount > 0` (SQL), not `overview.dpi_paid_amount` (optional key).
- **DPI overdue after repay:** overview `dpi_overdue_amount` is OK when key always present for overdue DPI.
- **Do not** add product default keys to pass `path_exists`.

## Missing helpers (fixed 2026-07-28)

Demo E2E scripts reference `demo_*` functions in `scripts/dpic/demo/lib/demo_runtime.sh` (sourced via `common.sh`). If you see `command not found` for `demo_require_reversal_services`, the harness is incomplete — not a product failure.

## Preflight (run before money E2E)

```bash
source scripts/dpic/lib/dpic_harness_lib.sh
dpic_harness_preflight
```

## Ship gate honesty

| Tier | When |
|------|------|
| Unit (`DPICalculationServiceGraceTest`, `DpiAccrualRateSealTest`, `RepaymentApproppriationLiqInstlTest`) | Product invariant for 180/184/186 |
| `dpic.overview_api` | API contract smoke |
| `dpic.repayment_e2e` | Full money path — needs ACTIVE fixture + safe repay amount |
| Registry FAIL on path_exists only | **Harness** until contract proven |

Agents: print `HARNESS` vs `PRODUCT` in failure summary. Do not block ship on harness-only registry drift.
