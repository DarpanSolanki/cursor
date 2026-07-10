---
name: reference_dpi_feature_branch
description: "DPI/DPIC work — mandatory repo checkout matrix; release-train vs feature WIP"
metadata:
  node_type: memory
  type: reference
---

## When the task mentions DPI, DPIC, delayed payment interest, dpiAccrual*, dpiBilling

**Before grepping code or trusting KG flow output**, verify checkout.

### Current release train (default for harness / QA)

| Repo | Branch | Why |
|------|--------|-----|
| `novopay-platform-accounting-v2` | **`mfi_integration_v3.7.1`** | DPI calc/booking/billing product rules + booking fix `77921d275f` |
| `novopay-platform-initial-setup` | match release train / task | Flyway + go-live seeds |
| Workspace harness | `scripts/dpic/` on workspace `main` | Quick regression + column audit |

Confirm booking fix in HEAD:

```bash
git -C novopay-platform-accounting-v2 merge-base --is-ancestor 77921d275f HEAD && echo OK
```

### Legacy feature branch (only if task explicitly says unmerged WIP)

| Repo | Branch |
|------|--------|
| `novopay-platform-accounting-v2` | `feature/delayed_payment_interest` |
| `novopay-platform-initial-setup` | `feature/delayed_payment_interest` |
| `novopay-platform-webapp` | `feature/delayed_payment_interest` (if UI) |

Then: `scripts/bin/kg-switch.sh` so KG watermark matches the branch under test.

## Product rules (3.7.1 — harness-encoded)

1. Grace: stored `overdue_date` gate; first slice start = **due_date**; grace 0 valid
2. Splitting: month-end + EMI due seals (interest parity)
3. Slice ownership: latest EMI due on/before segStart
4. Booking: month-end OR any INT/PRIN EMI due (not installment INT only)
5. Billing: needs `accrual_posting_date`; month-end may stay unbilled until next EMI due
6. Harness FAIL on `sealed_unposted` / `sealed_unbilled`

Coverage map: `scripts/dpic/DPI_TEST_COVERAGE.md`  
Quick: `DPI_REGRESSION_PROFILE=quick bash scripts/dpic/run_dpi_full_regression.sh`

## Agent entry

1. Confirm accounting branch = task branch (usually `mfi_integration_v3.7.1`)
2. `kg orient dpiAccrualCalculation` / `kg cases dpiAccrualBooking` after `kg-switch`
3. Orchestration: `loans_orc.xml` — `dpiAccrualCalculation`, `dpiAccrualBooking`, `dpiBilling`
4. Local: `scripts/dpic/`, `ntest run dpic.full_regression`
