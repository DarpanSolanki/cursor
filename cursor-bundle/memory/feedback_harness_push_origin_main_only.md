---
name: feedback_harness_push_origin_main_only
description: >-
  Workspace harness (scripts/dpic, dpi-sanity, agent-ops DPI prep) pushes only
  to origin/main — never to mfi_integration_v* train branches.
---

# Harness → origin/main only (2026-07-28)

## Standing rule

**Workspace harness / DPI test tooling lives on `main`.**

| Do | Don't |
|----|-------|
| Commit + `git push origin main` for `scripts/dpic/**`, `scripts/bin/dpi-sanity.sh`, DPI prep in `agent-ops-lib.sh`, harness memory | Push harness fixes only to `mfi_integration_v3.4.2.4` (or any train branch) |
| If harness was committed on a train branch by mistake → **cherry-pick / merge into `main`**, push `main` | Leave harness SoT on a train branch |

## Why

- Service product code tracks `mfi_integration_vX.Y.Z` / feature trains.
- Harness is workspace-shared (`DarpanSolanki/cursor` repo) and must stay on **`main`** so every train checkout can use the same scripts.
- `reference_dpi_feature_branch.md` already says: Workspace harness → `scripts/dpic/` on workspace **`main`**.

## Agent checklist before push

```bash
cd /home/darpan/Documents/sliProd
git checkout main
# … harness edits …
git push origin main   # or scripts/bin/push-origin.sh if used for this repo
```

Confirm branch before push: `git rev-parse --abbrev-ref HEAD` must be **`main`**.

Provenance: user correction 2026-07-28 — harness had been pushed on `mfi_integration_v3.4.2.4`; brought to `main` via cherry-pick + fail-fast overlay.
