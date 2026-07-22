# Decision: multi-profile / domain-scoped KG overlays

**Status:** DEFERRED (2026-07-22) — Upgrade 6 ships the light guardrail only.  
**Owner:** workspace KG (`cursor-bundle/kg/`)  
**Related:** `BRANCH-SAFETY.md`, `scripts/lib/kg_state_banner.py`, telemetry in `.cursor/workspace-kg-state.md`

## Why not now

One live KG already blends mixed trains; the failure mode is agents **sailing past** PROVISIONAL warnings, not cache mechanics. Composite-key LRU already restores a full branch-set in ~1s. Building per-domain overlays before we measure gate pressure would add build/ops surface without proven demand.

## Guardrail in force (meanwhile)

Money / cross-service tasks with WIP watermark or key mismatch → autopilot **HARD STOP** (`KG STATE` + options: kg-switch / `KG_STRICT=1` / explicit user ack). Every trigger logs `trigger=gate` in telemetry. MCP/CLI answers carry `[KG @… set=… WIP:n]`.

## Trigger criteria to revisit (build profiles)

Revisit multi-profile KG when **any** measurable signal holds:

1. **≥8 `trigger=gate` hits in a rolling 7-day window** in `.cursor/workspace-kg-state.md` telemetry (agents repeatedly blocked on mixed/WIP sets), **or**
2. **≥3 consecutive cache `miss` streaks** recurring in the same week (sync thrash on mixed checkouts), **or**
3. A **wrong-train mis-claim** reaches human review (JIRA/QA/release) where provenance header + gate were present but an agent still treated WIP KG as release-train truth.

Until then: do **not** start profile code.

## Design sketch (if triggered)

- Keep one **spine** build + composite-key LRU (already proven).
- Add optional **overlays** keyed by domain (`dfc`, `disburse`, `dpi`, …) = subset of repos from `train_banner.DOMAIN_REPOS` + same cache restore path.
- Autopilot / `kg-switch --domain X` restores overlay when task domain is known; money gate still applies if overlay WIP.
- Cost estimate: ~1–2 eng-days for overlay stamp + switch wiring; +disk ≈ N× current cache slot size (LRU still caps). Latency target: restore ≤2s (same mechanism as today).

## What stays true until then

Task A gate + provenance header + telemetry are the product. Profiles are an optimization, not a substitute for acknowledging mixed/WIP KG.
