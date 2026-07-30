# Decision: multi-profile / domain-scoped KG overlays

**Status:** PARTIAL (2026-07-30) — **align gate + L1 ship routing + L2 require-align** shipped; full domain overlays still deferred.  
**Owner:** workspace KG (`cursor-bundle/kg/`)  
**Related:** `BRANCH-SAFETY.md`, `scripts/bin/kg-align.sh`, `kg-self-enhance.sh`, `kg.py align` / `--require-repo`, MCP `kg_align` v1.5.0

## Why not full overlays yet

One live KG already blends mixed trains; the failure mode is agents **sailing past** PROVISIONAL warnings *and* analyzing train A from git while KG is stamped on train B. Composite-key LRU already restores a full branch-set in ~1s.

## Shipped (2026-07-30) — align + symbols + L1/L2

| Piece | Purpose |
|-------|---------|
| `kg align --repo/--branch` or `--domain/--train` | Fail-closed watermark vs expected train |
| `--require-repo/--require-branch` on impact/flow/orient/why/crud/writes | Same gate inline on money look-ups |
| `KG_ALIGN_REPO` + `KG_ALIGN_BRANCH` / `KG_REQUIRE_ALIGN=1` | Env-driven fail-closed |
| `scripts/bin/kg-align.sh` / `kg-self-enhance.sh` | Switch+align; validate+rebuild after curated edits |
| Knowledge-only ship paths include `scripts/bin/kg-*` | Knowledge HEAD skips sticky money/DPIC auto-close |
| MCP `require_repo`/`require_branch` on look-ups | Cursor agents pass train under study |
| `build_java_symbols.py` | Method nodes for `kg impact Class#method` |

## Guardrail in force (meanwhile)

Money / cross-service tasks with WIP watermark or key mismatch → autopilot **HARD STOP** (`KG STATE` + options: kg-switch / `KG_STRICT=1` / explicit user ack). Every trigger logs `trigger=gate` in telemetry. MCP/CLI answers carry `[KG @… set=… WIP:n]`.

**Plus:** before money impact claims, agents must run `kg align` **or** pass `--require-repo/--require-branch` for the train under study (or document explicit ack of misalignment).

## Trigger criteria to revisit (build profiles)

Revisit multi-profile KG when **any** measurable signal holds:

1. **≥8 `trigger=gate` hits in a rolling 7-day window** in `.cursor/workspace-kg-state.md` telemetry (agents repeatedly blocked on mixed/WIP sets), **or**
2. **≥3 consecutive cache `miss` streaks** recurring in the same week (sync thrash on mixed checkouts), **or**
3. A **wrong-train mis-claim** reaches human review (JIRA/QA/release) where provenance header + gate were present but an agent still treated WIP KG as release-train truth.

**Note (2026-07-30):** Gate telemetry already exceeds (1) in recent days — align gate addresses the dominant mis-claim class without overlay disk cost. Revisit overlays if align+sync thrash remains high.

## Design sketch (if triggered)

- Keep one **spine** build + composite-key LRU (already proven).
- Add optional **overlays** keyed by domain (`dfc`, `disburse`, `dpi`, …) = subset of repos from `train_banner.DOMAIN_REPOS` + same cache restore path.
- Autopilot / `kg-switch --domain X` restores overlay when task domain is known; money gate still applies if overlay WIP.
- Cost estimate: ~1–2 eng-days for overlay stamp + switch wiring; +disk ≈ N× current cache slot size (LRU still caps). Latency target: restore ≤2s (same mechanism as today).

## What stays true until then

Task A gate + provenance header + telemetry + **`kg align`** are the product. Profiles are an optimization, not a substitute for acknowledging mixed/WIP KG or wrong-train watermark.
