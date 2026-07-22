---
name: feedback_cross_branch_no_false_positive
description: Fail-closed rules for kg fixed-elsewhere / fwd-port — never reuse FILE_TOUCH_HINTS; only VERIFIED_FIXED_CLEAN after diverge; watermark FRESH ≠ production contract certainty
metadata:
  node_type: memory
  type: feedback
---

# Cross-branch reuse — fail closed (STANDING)

## What may be reused

**Only** when tool output contains both:
- `VERIFIED_FIXED_CLEAN`
- `RESULT: REUSE_ALLOWED`

Meaning: KG case SHA uniquely resolves, is contained by higher `upstream/<branch>`, is absent from the reported base tip, **and** `sha..target` has **no** later commits on the fix files.

## What must never drive a fix

| Label | Meaning |
|-------|---------|
| `FILE_TOUCH_HINTS` / `CANDIDATE_ONLY` | Same files changed on higher train — **not** the same bug/fix |
| `VERIFIED_FIXED_DIVERGED` | SHA is in history but target files changed later — reconcile, do not blind-port |
| `NOT_VERIFIED_STALE_REFS` | Upstream fetch too old / missing — no reuse decision |
| `CASE_SHA_UNRESOLVED` | Short/ambiguous/missing object — refuse |
| `NO_KNOWN_FIX` | Implement on reported train from RCA, do not invent from higher noise |

Print of `REUSE_FORBIDDEN` = hard stop for cherry-pick/port proposals.

## Watermark honesty

`kg fresh` / watermark FRESH means: KG spine matches **this workspace checkout** (branch@sha, including dirty/WIP). It does **not** mean:
- all repos are on the same release train
- WIP feature tips are production contracts
- a higher-branch file change equals your bugfix

For money RCA: align to **Reported version** train, run `kg fixed-elsewhere --base <that train> --fetch-if-stale`, and treat mixed/WIP watermark lines as scope limits.

## L2 index (why not authority)

A build-time `fixed_in_branches` index on KG cases would go **stale** as soon as upstream moves and would tempt agents to skip live ancestry. Live L0/L1 (`fixed-elsewhere` + `fwd-port`) remain the only reuse authority. Optional future L2 may cache hints with a timestamp, never alone for REUSE_ALLOWED.
