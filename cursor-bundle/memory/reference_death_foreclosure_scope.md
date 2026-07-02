---
name: reference_death_foreclosure_scope
description: "Death foreclosure / mainline — prod train mfi_release_v3.4.2; DPI unmerged on feature branch"
metadata:
  node_type: memory
  type: reference
  updated: 2026-06-29
---

## Branch reality (user-confirmed 2026-06-29)

```
mainline (integration → release)          DPI (NOT merged)
────────────────────────────────          ─────────────────────────────
mfi_integration_v3.3.1.2  (dev/fix)       feature/delayed_payment_interest
        ↓                                         ↓
mfi_release_v3.4.2        (prod in ~days)   QA testing only — NOT in 3.4.2 prod
```

| Workstream | Branch policy | In prod 3.4.2? |
|------------|---------------|----------------|
| **Death foreclosure, disburse, LOS sync, general accounting** | **Mainline only** — `mfi_integration_*` / `mfi_release_*` — **same train on all repos** | Yes (when merged to release) |
| **DPI / DPIC** | `feature/delayed_payment_interest` **only** when user explicitly says DPI | **No** — not merged to mainline |

**Do not** grep, KG-orient, or ship-test DPI feature code for DCF/production tickets.

## Active work: death foreclosure

- **Issues:** Production + QA observations (e.g. SDCP-10494 outstanding/claim; QA3 GL BLD/UNBLD legs).
- **Fix train:** `mfi_integration_v3.3.1.2` (current integration) → forward-port to **`mfi_release_v3.4.2`** before prod cut.
- **Repos:** accounting-v2, los, lib (if touched) — all on **mainline**, not DPI feature.

## Session entry (death foreclosure / mainline)

1. `bash sync_branches_v2.sh mfi_integration_v3.3.1.2` — **all repos** (manifest has **no** DPI overrides).
2. `bash scripts/bin/kg-switch.sh` — watermark: accounting `@ mfi_integration_*`, not `feature/delayed_payment_interest`.
3. For **prod RCA** on QA3 build `mfi_release_v3.4.2_*`: `git fetch upstream` → read `upstream/mfi_release_v3.4.2` (or named tag), not local DPI checkout.
4. Orient: `system_brain/flows/death_foreclosure.md` → `kg flow loanDeathForeclosure` → orchestration XML.
5. Tests: `dcf.principal_split_sim`, `foreclosure.individual_child` — **not** `dpic.*`.

## DPI (separate — only when user says DPI)

- Branch: `feature/delayed_payment_interest` — **unmerged** to mainline.
- Entry: `ensure-dpi-branches.sh` + `reference_dpi_feature_branch.md`.
- Never block or confuse DCF ship loop with DPI read_smoke / overview failures.

## Common mistakes

- Mixed workspace: accounting on integration, actor/lib on DPI feature → wrong cross-service RCA.
- Assuming DPI foreclosure waiver behaviour exists on mainline DCF path (it does not on 3.3.1.2 / 3.4.2 without merge).
- Fixing on integration but verifying against DPI-feature-only APIs.

## QA LANs (DCF)

- QA4 **6007564726** — original ticket (outstanding/claim).
- QA3 **6005077725** — retest GL legs on release build shape.
