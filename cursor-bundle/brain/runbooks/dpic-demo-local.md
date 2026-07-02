# DPIC — local demo & dev testing (product 6367)

> **Product** 6367 · **loan_product** 2886 · **scheme** 300 (id **2655**) · **customer** 10002233  
> Scripts: `scripts/dpic/` · Live demo: `scripts/dpic/demo/run_demo.sh phase1`…`phase4`

## Quick start (learned 2026-06-16)

```bash
# 1) One-time / after QA dump restore
bash scripts/dpic/run_setup.sh

# 2) Preflight only (DB + services)
bash scripts/dpic/run_preflight.sh

# 3) Live demo — ONE phase at a time (not `all`)
bash scripts/dpic/demo/run_demo.sh status
bash scripts/dpic/demo/run_demo.sh phase1   # ~25s
bash scripts/dpic/demo/run_demo.sh phase2   # ~5s
bash scripts/dpic/demo/run_demo.sh phase3   # ~3s
bash scripts/dpic/demo/run_demo.sh phase4   # ~5s
```

State: `scripts/scratch/dpic_demo_state.env` · Registry correlators sync after phase1.

## Critical product setup — negative PRIN/INT (not a schedule-generator bug)

| Config | Wrong (QA dump) | Correct (local setup) |
|--------|-----------------|------------------------|
| `loan_product.installment_multiples_of` | `THOUSAND` | `ZERO` |
| `installment_rounding_type` | `RND_OFF_INST_RUP` | keep |
| Effect on ₹50k / 24mo / 16% | PMT ~₹2448 → EMI **₹3000** | EMI ~₹2462 |
| Symptom | Negative tail `loan_due_details` PRIN/INT | All `due_amount ≥ 0` |

**Fix:** `setup_local_dev_product_6367.sql` section **A0** — run via `bash scripts/dpic/run_setup.sh`.  
Phase1 asserts zero negative rows after disburse (`demo_assert_no_negative_schedule`).

## Services

| Service | Port | Branch (local) | Needed for |
|---------|------|------------------|------------|
| accounting-v2 | 8002 | `feature/delayed_payment_interest` | phase1–4 |
| task | 8019 | `mfi_integration_v3.3.1.1` | phase4 reversal |
| actor | 8003 | `mfi_integration_v3.3.1.1` | phase4 (user 53) |

## Phase map

| Phase | What | Prereq |
|-------|------|--------|
| 1 | Disburse + fast EOD (quarantine portfolio) | setup once |
| 2 | Overview/Summary/Basic APIs — DPI keys | phase1 state |
| 3 | `loanRepayment` CASH + `dpi_amount` on payment | phase1 |
| 4 | `loanAccountTransactionReversal` INITIATE→APPROVE | phase3 + task |

### Phase 4 gotchas

- `user_id` **53** (`DEMO_REVERSAL_USER_ID`) — user 3 has null `getUserBasicDetails` locally
- Headers: **`operation_mode=SELF`** on INITIATE and APPROVE
- `dpi_amount` on reversal row — templates + `GetTransactionReversalTaskDetailsProcessor` (`387643f16`)
- DB: `mfi_task.task_activity.activity_initiated_user_role_code` — `setup_local_task_reversal_prereqs.sql`

### Phase 3 gotchas

- `loanRepayment` uses **platform business date** when calendar > demo anchor (avoids **132280**)
- `DPI_BILLED_INTEREST` placeholder on product catalogue **3** — setup SQL section H

## Speed (vs legacy `run_eod.sh`)

- Fast EOD: `run_eod_dpi_only.sh` + portfolio quarantine — ~18s for 4 milestones
- Phase 3: skips `demo_status.sql` unless `DEMO_SHOW_STATUS=1`
- Phase 2: curl-only API keys (no ntest during presentation)

## Verification SQL

```sql
-- Negative schedule (must be 0 after phase1)
SELECT count(*) FROM mfi_accounting.loan_due_details
WHERE loan_account_id = :id AND is_deleted = false AND due_amount < 0;

-- EMI distribution (healthy: 1×3120 first + 22×~2462 + 1×~2441 last)
SELECT installment_amount, count(*) FROM mfi_accounting.loan_installment_details
WHERE loan_account_id = :id AND is_deleted = false GROUP BY 1;
```

Canned: `scripts/db-local.sh --canned 20-dpic-negative-dues --param loan_account_id=<id>`

## Related

- EOD booking failures: [`dpic-eod-booking-local.md`](dpic-eod-booking-local.md)
- Docs: `docs/dpic/LOCAL_DEV_GUIDE.md`, `docs/dpic/QA_DEMO_MONDAY.md`
- KG: `kg cases loanAccountTransactionReversal` · `kg flow dpiAccrualBooking`
