# DPIC local dev scripts

LMS path for **product 6367** / **scheme 300** (id **2655**), customer **10002233**.

**Guides:** [`docs/dpic/LOCAL_DEV_GUIDE.md`](../../docs/dpic/LOCAL_DEV_GUIDE.md) · [`demo/README.md`](demo/README.md) · [`cursor-bundle/brain/runbooks/dpic-demo-local.md`](../../cursor-bundle/brain/runbooks/dpic-demo-local.md)

## Quick start (live demo — one phase at a time)

```bash
make -C scripts dpic-preflight    # DB + services + EMI config
make -C scripts dpic-setup        # first time / after QA dump
make -C scripts dpic-status       # LAN + phase readiness
make -C scripts dpic-phase1       # ~25s
make -C scripts dpic-phase2       # ~5s
make -C scripts dpic-phase3       # ~3s
make -C scripts dpic-phase4       # ~5s
```

Or: `bash scripts/dpic/demo/run_demo.sh phase1` … `phase4`

**Automation only:** `make -C scripts dpic-demo` (all phases — not for presentation)

## Scripts

| Script | Purpose |
|--------|---------|
| `run_preflight.sh` | DB + product EMI check + accounting/task/actor reachability |
| `run_setup.sh` | Product-doc TAR seed + product 6367 links + verify + task schema |
| `run_disburse.sh` | `disburseLoan` via `disburse_loan_sanity.py` |
| `run_eod.sh` | Full EOD (slow — prefer demo `run_fast_eod_all.sh`) |
| `run_full_happy_path.sh` | Setup → disburse → EOD (legacy) |
| `run_qa_demo.sh` | Automation → `run_demo.sh all` |
| `run_demo_api_verify.sh` | ntest API verify from `scratch/dpic_demo_state.env` |

## SQL

| File | Purpose |
|------|---------|
| `sql/setup_local_dev_product_6367.sql` | Links, placeholders, **EMI ZERO fix (A0)** |
| `sql/verify_prerequisites.sql` | DB gate incl. EMI + DPI_BILLED_INTEREST |
| `sql/setup_local_task_reversal_prereqs.sql` | Task schema for phase4 |

## Learnings (product setup)

`loan_product` **2886** with `installment_multiples_of=THOUSAND` rounds ₹50k/24mo EMI to **₹3000** → negative tail PRIN/INT in `loan_due_details`. Setup sets **ZERO**. Not a schedule-generator defect.

## Env

| Variable | Default | Purpose |
|----------|---------|---------|
| `SKIP_SETUP` | `1` in phase1 | Set `0` for first-time DB seed |
| `DEMO_SKIP_PREFLIGHT` | `0` | Skip service checks in phase1 |
| `STATE_FILE` | `scripts/scratch/dpic_demo_state.env` | LAN between phases |
