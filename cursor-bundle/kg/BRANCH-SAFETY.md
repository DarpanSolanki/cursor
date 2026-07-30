# KG branch safety (sliProd / cursor-bundle)

One active KG snapshot (`cursor-bundle/kg/data/kg.db`) must always reflect the **live checkout** of every `novopay-*` / `trustt-*` repo under the workspace root.

## Mechanisms

| Mechanism | What it does |
|-----------|----------------|
| **Composite key** | `kg_composite.py` hashes all repos' `branch+HEAD+dirty` + brain doc corpus → 16-char cache key. |
| **LRU cache** | `data/cache/<key>.{db,jsonl,json,manifest.json}` — **24** branch-set snapshots; restore ~1s vs full build ~40–70s. |
| **Integrity guard** | `kg_validate.py` — sqlite `integrity_check`, min nodes/edges, FTS probe; corrupt cache entries deleted on failed restore. |
| **kg switch** | `scripts/bin/kg-switch.sh` / `kg switch` — primary entry after branch change or multi-repo sync. |
| **Auto-sync** | Session start, `git checkout/switch` (Cursor hook + optional per-repo `post-checkout`), `kg.py` knowledge commands on drift. |
| **Watermark** | `build.sh` stamps each repo's `branch@sha` (+ dirty hash, upstream release base for WIP) into `stats.json`. |
| **WIP anchor** | `kg watermark` shows `feature/foo` ← base `mfi_integration_v3.x.y` (+N commits). Treat base as stable; `base..HEAD` provisional. |
| **KG_STRICT** | `KG_STRICT=1` — knowledge commands **exit 2** if sync fails (never answer from stale KG). |

## Commands

```bash
scripts/bin/kg-switch.sh              # sync after branch change (recommended)
python3 cursor-bundle/kg/bin/kg.py switch
python3 cursor-bundle/kg/bin/kg.py cache          # list cached branch-sets
python3 cursor-bundle/kg/bin/kg.py validate       # corruption check
python3 cursor-bundle/kg/bin/kg.py fresh            # session verdict
python3 cursor-bundle/kg/bin/kg.py watermark        # per-repo detail
python3 cursor-bundle/kg/bin/kg.py doctor           # stale sources + drift
cursor-bundle/kg/bin/build.sh                     # rebuild (cache hit = fast)
cursor-bundle/kg/bin/build.sh --force               # ignore cache
scripts/bin/install-kg-git-hooks.sh                # post-checkout in each service repo
KG_NO_AUTO_REBUILD=1 kg flow disburseLoan          # warn-only drift (CI/scripts)
KG_STRICT=1 kg flow disburseLoan                   # refuse stale answers
kg flow disburseLoan --no-drift-check               # skip drift check entirely
```

## Branch-wise impact analysis (required)

Watermarked KG = **one composite branch-set**. It is only correct for impact/flow when it matches the train under study.

```bash
# 1) Put money repos on the train you are analyzing
bash scripts/bin/sync-branches.sh --domain accounting --train mfi_integration_v3.4.2.4 --yes

# 2) Rebuild/restore KG for that checkout + assert watermark
bash scripts/bin/kg-align.sh --repo trustt-platform-accounting --branch mfi_integration_v3.4.2.4
# or: bash scripts/bin/kg-switch.sh --force --assert-repo trustt-platform-accounting --assert-branch mfi_integration_v3.4.2.4

# 3) Impact with fail-closed require (L2)
python3 cursor-bundle/kg/bin/kg.py impact 'InterestAccrualBookingService#adjustChildLoanAccountsInterestAccrual' \
  --require-repo trustt-platform-accounting --require-branch mfi_integration_v3.4.2.4
# env form: KG_ALIGN_REPO=… KG_ALIGN_BRANCH=… kg impact …
# hard fail without pair: KG_REQUIRE_ALIGN=1 kg impact …

# 4) After curated/diag edits — self-enhance
bash scripts/bin/kg-self-enhance.sh --repo trustt-platform-accounting --branch mfi_integration_v3.4.2.4
```

MCP: `kg_align` then `kg_impact`/`kg_orient` with `require_repo` + `require_branch` (v1.5.0+).

### Ship routing (L1)

`scripts/bin/kg-*.sh` + `scripts/lib/kg_*.py` + `cursor-bundle/kg/**` are **knowledge-only**. A knowledge-only HEAD skips money/DPIC auto-close even if sticky pending still lists foreclosure APIs.

**Do not** answer INT/FC money questions from a KG stamped on `3.5.2.2` while reading `origin/3.4.2.4` via git — that is the failure mode this align gate closes.

## Multi-branch parallel work

When repos are on **different** branches simultaneously (e.g. accounting on `feature/delayed_payment_interest`, rest on `mfi_integration_v3.3.1.0`), the composite key captures the **entire workspace state**. Each unique combination gets its own cache slot — switching back restores instantly if that combination was built before.

**Do not** use KG answers when `kg fresh` reports STALE unless you run `kg switch` first (or enable auto-rebuild). Use `kg align` when the question is about a **named train** that may differ from live mix.

## What FRESH does **not** mean

| Claim | Reality |
|-------|---------|
| Production contract certainty | No — FRESH = spine matches **this** checkout, including dirty/WIP |
| All repos same train | No — read `kg watermark` WIP lines + `branch_topology.active_branch_mix_note()` |
| Higher-branch file change = your bugfix | No — only `kg fixed-elsewhere` → `REUSE_ALLOWED` / `VERIFIED_FIXED_CLEAN` |
| Safe to skip RCA | No — reported-version train + live code/DB remain authoritative |

Cross-branch reuse policy: `cursor-bundle/memory/feedback_cross_branch_no_false_positive.md`.

## Scenarios

| Situation | Expected behaviour |
|-----------|---------------------|
| `git switch` in one service repo | `post-checkout` hook + Cursor `afterShellExecution` → `kg-switch` (cache or build). |
| `sync-branches.sh` all repos | Ends with `kg-switch` for the new uniform branch-set. |
| Switch branch in accounting-v2 only | Composite key changes; cache miss → rebuild for that mix. |
| Edit orchestration XML | `kg doctor` STALE; `kg switch --force` or `build.sh --force`. |
| Edit brain doc only | Warn on query; `kg switch` refolds doc nodes. |
| Prepend CHANGELOG | `enrichment-sync.sh` or `kg switch` mints new `case` nodes. |
| Corrupt cache file | Restore fails validate → entry deleted → full rebuild. |
| All repos on feature branches | Watermark PROVISIONAL; WIP-vs-stable gate before brain doc edits. |

## Self-learning

Shipped fixes → `brain/changelog/CHANGELOG.md` → `build_cases.py` → `case:*` nodes → `kg cases <flow>`.

See `.cursor/rules/self-learning-kg.mdc` and `cursor-bundle/memory/feedback_keep_knowledge_current.md`.
