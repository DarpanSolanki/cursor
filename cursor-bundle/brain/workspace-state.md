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
| ~~`feature/delayed_payment_interest`~~ | **RETIRED 2026-08-06** | Dead — DPIC ships on `3.7.1`. Never check out; parking a repo there forces the whole KG watermark `[PROVISIONAL]` |

## Point-in-time snapshot (2026-08-06)

Regenerate rather than hand-edit — `bash scripts/bin/git-workspace-status.sh`. The 2026-07-17
revision had the DPI rows **inverted** (it named `actor` as the WIP repo and `initial-setup` as
clean 3.7.1; the truth was the reverse), which sends a DPI task hunting in the wrong repo.

| Repo | Branch | Notes |
|------|--------|-------|
| `trustt-platform-accounting` | `mfi_integration_v3.7.1` @ `566dc68ace` | Canonical for DPI + DFC |
| `trustt-platform-los` | `mfi_integration_v3.4.2.4` @ `44bba2c47a` | Mixed train — scope cross-service carefully |
| `trustt-platform-actor` | `mfi_integration_v3.7.1` @ `770b97aef4` | |
| `trustt-platform-payments` | `mfi_integration_v3.4.2.4` @ `0dae3fc3ed` | Older train |
| `trustt-platform-initial-setup` | `mfi_integration_v3.7.1` @ `4a5864a567` | Moved off retired `feature/delayed_payment_interest` and fast-forwarded to `upstream` tip on 2026-08-06 — **at upstream tip, 0 behind**. Read-only Flyway source (no local commits/pushes) |
| `trustt-platform-webapp` | `mfi_integration_v3.7.1` @ `f0216081f8` | Also moved off the retired branch 2026-08-06; branch created from `upstream` (none existed locally) |

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

