# Mixed release trains — scoped sync (do not blind-switch all repos)

**Problem:** Workspace repos often sit on different trains (accounting `3.7.1`, LOS `3.4.2.2`, DPI feature, platform-lib `3.4.2.3`). Blind `sync_branches_v2.sh <one-branch>` across **all** repos breaks the other domain.

**Rule:** Sync **only the repos required for the task domain**. Then `bash scripts/bin/kg-switch.sh` so KG watermark matches that scoped checkout.

## Snapshot recipe (2026-07-10 evidence)

| Task domain | Accounting | LOS | platform-lib | initial-setup / webapp / actor | Do **not** force |
|-------------|------------|-----|--------------|--------------------------------|------------------|
| **DFC / SDCP-10199 / death FC** | `mfi_integration_v3.7.1` | leave (or `3.4.2.2` if LOS sync needed) | leave | leave | Do not pull all repos to 3.7.1 |
| **Disburse / NEFT on 3.4.2.2** | `mfi_integration_v3.4.2.2` (or named QA tag) | `mfi_integration_v3.4.2.2` | match train | leave DPI feature alone | Do not force accounting to 3.7.1 for disburse RCA on 3.4.2.2 |
| **DPI harness / go-live** | `mfi_integration_v3.7.1` (booking fix `77921d275f`) | leave | leave | `feature/delayed_payment_interest` **only** when task says WIP | Do not analyze DPI APIs from older integration without the booking SHA |

## Commands (scoped — never invent a full-workspace train)

```bash
# Example: DFC work on 3.7.1 only (accounting)
git -C novopay-platform-accounting-v2 fetch origin upstream
git -C novopay-platform-accounting-v2 checkout mfi_integration_v3.7.1
git -C novopay-platform-accounting-v2 pull --ff-only origin mfi_integration_v3.7.1
bash scripts/bin/kg-switch.sh

# Full-workspace sync ONLY when user explicitly asks for one branch everywhere:
bash sync_branches_v2.sh mfi_integration_v3.7.1 DarpanSolanki /home/darpan/Documents/sliProd
bash scripts/bin/kg-switch.sh
```

## Cross-repo claim gate

Before asserting a **cross-service** contract (LOS↔accounting, lib↔accounting):

1. Print branch@sha for **each** involved repo (`git-workspace-status.sh` or the loop in `darpan.mdc`).
2. If trains differ → scope the claim to the named train **or** align those repos first.
3. KG `watermark` showing `WIP` / `provisional` → treat `flow`/`crud` as branch-local, not production contract.

## Related

- Ask tracker: `cursor-bundle/brain/workspace/ASK-TRACKER-2026-07-10.md` (ASK-H08)
- DFC runbook: [`sdcp-10199-group-parent-last-child-dfc.md`](sdcp-10199-group-parent-last-child-dfc.md)
- DPI branch gate: `.cursor/rules/30-kg-discipline.mdc`
