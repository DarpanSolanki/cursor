---
name: reference-forward-merge-chain
description: Declared train forward-merge order — use it before porting a fix, allocating a migration version, or calling a branch "regressed"
metadata:
  type: reference
---

Trains forward-merge along a declared order (Darpan, 2026-08-05), validated against git ancestry
in `trustt-platform-accounting`:

```
3.4.2.3 → 3.4.2.4 → 3.4.2.5 → 3.4.2.6 → 3.5.1 → 3.5.1.1 → 3.5.2 → 3.5.2.2 → 3.5.3 → 3.6.1 → 3.7.1
```

Each version carries `mfi_integration_v…` then `mfi_release_v…`.

SoT: `scripts/lib/forward_merge_chains.json` · CLI `scripts/lib/forward_merge.py` ·
narrative `.cursor/release-trains.md` § Declared forward-merge chain.

**Three things this changes:**

1. **Do not hand-port downstream.** A fix on 3.5.1.1 reaches 3.7.1 by forward merge. Porting it
   manually creates a duplicate that conflicts on the real merge. `forward_merge.py travel` labels
   each branch `HAS` / `ARRIVES-BY-FORWARD-MERGE` / `NEEDS-EXPLICIT-PORT`.
2. **Allocate numbers against the highest branch.** Flyway migration versions and error codes must
   be free on the *highest* chain branch, not the checked-out one — otherwise the next forward
   merge collides. `forward_merge.py highest --repo trustt-platform-initial-setup`.
3. **Absence upstream is not a regression.** Branches before the fix legitimately lack it. Pairs
   with [[feedback-branches-diverge-both-directions]] and `.cursor/rules/40-knowledge-upkeep.md`.

Two of the four declared lists (L3/L4) omit 3.5.1.1 and stop at 3.5.2.2 — coverage differs,
ordering never contradicts. `forward_merge.py coverage <branch>` prints which lists cover it.
Which source branch each declared list belongs to was never stated; ordering is used, list
identity is not.
