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
| `trustt-platform-accounting` | **`mfi_integration_v3.7.1`** | DPI calc/booking/billing product rules + booking fix `77921d275f` |
| `trustt-platform-initial-setup` | match release train / task | Flyway + go-live seeds |
| Workspace harness | `scripts/dpic/` on workspace **`main`** only (`origin/main`) | Quick regression + column audit — **never push harness to train branches** |

Confirm booking fix in HEAD:

```bash
git -C trustt-platform-accounting merge-base --is-ancestor 77921d275f HEAD && echo OK
```

### `feature/delayed_payment_interest` — RETIRED (2026-08-06)

**DPIC is live on `mfi_integration_v3.7.1`. Do not check out, analyse, or cite this branch.**

It is not "WIP to use when the task says so" — it is dead. A recent merge *into* it from
`upstream/mfi_integration_v3.7.1` is not evidence of use; it was merged into, not worked on.

Leaving a repo parked there poisons every KG answer: the branch is not a release train, so
`kg_composite.repo_state` marks it `provisional` and the whole watermark reads `[PROVISIONAL]`,
which gates money and cross-service conclusions workspace-wide.

Cleared 2026-08-06: `trustt-platform-initial-setup` and `trustt-platform-webapp` were both parked
there and are now on `mfi_integration_v3.7.1` — the watermark reads `[ALIGNED]`. If any repo lands
back on it: `git checkout mfi_integration_v3.7.1 && bash scripts/bin/kg-switch.sh`.


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


## Harness git branch (mandatory)

Push harness changes only to **`origin/main`**. If a fix landed on `mfi_integration_v*`, cherry-pick onto `main` and push `main`. Memory: `feedback_harness_push_origin_main_only.md`.
