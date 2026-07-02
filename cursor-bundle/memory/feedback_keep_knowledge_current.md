---
name: feedback_keep_knowledge_current
description: "Standing rule — keep the brain docs (engines/, platform/, accounting/, ALL reference docs the KG indexes) in sync with the latest code; update on new findings AND correct staleness, then rebuild the KG."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 7fc30f42-df07-4d0a-8093-68fff3c6147e
---

The brain docs under `claude/` are the **depth layer the core KG points into** — if they drift from the latest code, the whole graph degrades. Keeping them current is a first-class duty, both directions:

1. **New implementation found** → update the **single relevant** existing doc (engines/, platform/, accounting/, dpic/, runbooks/, flows/, services/, system/, …). Don't spawn a new loose file — plug into the existing structure (the KG architecture forbids markdown islands; see [[reference_system_kg]]).
2. **Doc found stale vs latest code** (wrong processor order, renamed class, changed amount/formula, superseded fact, old branch/SHA) → **correct it in the same turn you notice it**, while working that area. Stale knowledge silently misleads future sessions.

**Why:** the workspace is meant to be self-maintaining — the value is that every doc is always true to the deployed code.

**The WIP-vs-stable gate (auto-update is JUDGMENT-gated, not a blind daemon):** before folding a found code change into the docs/KG, decide if it is *correct and stable enough to be knowledge*. **Skip the doc update (knowledge stays as-is) if ANY hold:** the code is on a **feature/WIP branch** (`feature/*`, `SDCP/SP/HSQA-*`, `sli_*`) rather than the release train (`mfi_(integration|release)_v*`); it is behind a feature flag; it carries `TODO`/`FIXME`/commented-out/`@Deprecated`; it is **not reachable from any `<Request>`** in the flow spine (`kg flow`); or the working tree is dirty/uncommitted. Otherwise — merged on a release-train branch, reachable, stable, and it makes sense as durable knowledge — **fold it in: update the single relevant doc + rebuild the KG, same turn.** A script can't judge semantic correctness; this gate is applied with judgment, not automated rewriting of curated docs. If a change is real but provisional (WIP), note it as pending (e.g. in `dpic/` or `gaps-and-risks.md`) rather than rewriting the stable doc.

**Branch watermark (knowledge is current "up to which branch"):** `build.sh` stamps each repo's `branch@sha` (+ build time) into `claude/kg/data/stats.json`. `claude/kg/bin/kg watermark` shows, per repo, the branch the knowledge reflects vs live HEAD — and flags **feature/WIP branches as PROVISIONAL** and any **branch/commit drift** since the build. `kg doctor` summarises watermark drift alongside mtime freshness.

**Anchor a feature/customer branch to its UPSTREAM release base (the smart part):** a feature/customer branch (anything not `mfi_(integration|release)_v*`) = **base release branch + a WIP delta**. The watermark computes, per repo, **which upstream release branch it was forked from** (most-recent common ancestor) and how many commits sit on top — e.g. accounting `feature/delayed_payment_interest` ← base `mfi_release_v3.5.0` (+101), webapp `sli_dpic` ← `mfi_integration_v3.3.0` (+4); the SAME feature branch can have a DIFFERENT base per repo. **So when using the KG for a WIP repo: treat the knowledge as if on its release base (that's the stable substrate — and the release line whose forward-merge/behaviour rules apply), and treat only `git diff <base>..HEAD` as the provisional, in-development delta.** Base is always resolved against **UPSTREAM** refs (source of truth — never the local/origin copy). `kg watermark` prints the base + the "anchor KG to <base>" guidance.

**How to apply (every time):**
- While working any flow: diff the doc's claims against the live code / `kg flow <request>`. Fix drift you find, in the same turn — **after** clearing the WIP-vs-stable gate.
- After a stable code change: update the matching doc(s) AND run `claude/kg/bin/build.sh` (re-folds docs, rebuilds `kg.db`, re-stamps the watermark).
- **Proactively hunt drift:** `kg stale` lists docs citing repo files that no longer exist; `kg doctor` flags sources newer than the graph + watermark drift; `kg watermark` flags WIP-branch / branch-changed knowledge. Triage these when touching the area.
- New standing fact/correction about *how to work* → a `feedback_*` memory + `MEMORY.md`.

Complements the proof-backed gates (CLAUDE.md Rule 7) and [[feedback_proof_backed_agent_discipline]]: verify, then **persist** what you verified into the doc + graph.
