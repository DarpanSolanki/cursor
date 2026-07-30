# Decision: multi-profile / domain-scoped KG overlays

**Status:** PARTIAL (2026-07-30) — light **align gate** shipped; full domain overlays still deferred.  
**Owner:** workspace KG (`cursor-bundle/kg/`)  
**Related:** `BRANCH-SAFETY.md`, `scripts/bin/kg-align.sh`, `kg.py align`, MCP `kg_align`, telemetry in `.cursor/workspace-kg-state.md`

## Why not full overlays yet

One live KG already blends mixed trains; the failure mode is agents **sailing past** PROVISIONAL warnings *and* analyzing train A from git while KG is stamped on train B. Composite-key LRU already restores a full branch-set in ~1s.

## Shipped (2026-07-30) — align + symbols

| Piece | Purpose |
|-------|---------|
| `kg align --repo/--branch` or `--domain/--train` | Fail-closed watermark vs expected train |
| `scripts/bin/kg-align.sh` | `kg-switch` then align |
| `kg-switch.sh --assert-repo/--assert-branch` | Same assert after restore/build |
| `build_java_symbols.py` | Method nodes for `kg impact Class#method` |
| MCP `kg_align` | Same gate from Cursor MCP |
| Orient/impact banners | Print accounting train from watermark |

## Guardrail in force (meanwhile)

Money / cross-service tasks with WIP watermark or key mismatch → autopilot **HARD STOP** (`KG STATE` + options: kg-switch / `KG_STRICT=1` / explicit user ack). Every trigger logs `trigger=gate` in telemetry. MCP/CLI answers carry `[KG @… set=… WIP:n]`.

**Plus:** before money impact claims, agents must run `kg align` for the train under study (or document explicit ack of misalignment).

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
