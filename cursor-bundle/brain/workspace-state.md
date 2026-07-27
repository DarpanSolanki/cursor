# Workspace state — analysis-ready

**Last refreshed:** 2026-07-17 (sliProd; initial-setup row refreshed).

## Live authority (do not trust this table alone)

```bash
python3 cursor-bundle/kg/bin/kg.py watermark   # branch@sha KG reflects vs live HEAD
bash scripts/bin/git-workspace-status.sh      # writes .cursor/git-workspace-state.json
```

If this file disagrees with `kg watermark` / git status, **live state wins**.

## Canonical trains (2026-07-10)

| Concern | Canonical accounting branch | Notes |
|---------|----------------------------|--------|
| DPI harness / QA | **`mfi_integration_v3.7.1`** | Booking fix `77921d275f`; see `cursor-bundle/memory/reference_dpi_feature_branch.md` |
| DFC / SDCP-10199 | **`mfi_integration_v3.7.1`** | 3.4.2.x tips are ancestors; runbook `runbooks/sdcp-10199-group-parent-last-child-dfc.md` |
| Unmerged DPI WIP only | `feature/delayed_payment_interest` | Use **only** when task explicitly says WIP |

## Point-in-time snapshot (2026-07-17)

| Repo | Branch | Notes |
|------|--------|-------|
| `trustt-platform-accounting` | **`mfi_integration_v3.7.1`** | Canonical for DPI + DFC; live HEAD `8a1a7cd077` at refresh |
| `trustt-platform-los` | `mfi_integration_v3.4.2.4` | Mixed train — scope cross-service carefully |
| `trustt-platform-actor` | `feature/delayed_payment_interest` | ⚠ WIP / provisional |
| `trustt-platform-payments` | `mfi_integration_v3.4.2` | Older train |
| `trustt-platform-initial-setup` | `mfi_integration_v3.7.1` | Clean at fresh upstream tip `e4ade8c3f8`; read-only Flyway source (no local commits/pushes) |

**Workspace root:** `/home/darpan/Documents/sliProd` (not `/home/darpan/darpan`).

## Workspace rails (post GAP-G / FINAL SYNC — 2026-07-27)

| Rail | Where | Rule |
|------|-------|------|
| Universal invariants | `scripts/testing/flowtest/invariants.py` + `finish_scenario` | Money flowtests always snapshot+assert GL/AIR/BPI-after-FB |
| Selection tiering | `scripts/lib/impact_tests.py` | Direct-impact = full; sibling blast = invariant-smoke; dcf.* family ≤3 representative full |
| FIX-PLAN gate | `scripts/lib/ship_discipline_gate.py` | Money ships need `fix_plan` budget block |
| LAN taxonomy | `scripts/lib/loan_taxonomy.py` + `cursor-bundle/kg/curated/loan_taxonomy.json` | SHG=parent+children; JLG/INDL=childless — refuse child scenario on JLG |
| Penal scope | `flow_coverage.json` `scope=out` | Penal calc/booking permanently out of YES denominator |
| Orient-before-edit | `kg.py` touch + `after-ship-path-edit` | Fail-closed if money path edited without KG orient this session |
| Incremental KG | `kg_after_edit.py` + watermark | Light patch on edit; fail-closed STALE when branch-set drifts — full `kg-switch` when needed |
| Canonical test CLI | `scripts/bin/ntest.sh` | Prefer over raw `ntest.py` |

## Agent entry

1. `cursor-bundle/memory/MEMORY.md`
2. Domains: `scripts/lib/accounting_flow_domains.json`
3. JIRA reopen: `cursor-bundle/brain/jira/JIRA-INDEX.md`
4. `kg orient <apiName>` then orchestration XML

## Cross-repo train mismatch (ASK-H08)

Accounting claims on `mfi_integration_v3.7.1` are valid for **accounting only**. LOS, payments, and DPI feature branches are **mixed** — do not assert cross-service contracts without aligning trains or scoping the claim.

