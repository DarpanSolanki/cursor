---
name: feedback_forward_port_release_train
description: How to check & forward-port a fix across the release train safely — upstream is source of truth; verify the live merge DAG and divergence before porting; never break a higher branch with an incorrect push.
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 7fc30f42-df07-4d0a-8093-68fff3c6147e
---

Fixes land on a lower branch but must ride the **forward-merge train** to the higher release branches that other environments run. **UPSTREAM (khoslalabs) is the source of truth — NOT origin** (the DarpanSolanki fork). A fix on a lower branch that hasn't forward-propagated means those envs still have the bug.

**Always check git for the LIVE pattern — never assume the train order** (it evolves as new version branches appear). Tooling: `claude/kg/bin/fwd-port.sh`:
- `fwd-port.sh <repo> <sha> [floor]` — which upstream branches MISS this fix (exact via `merge-base --is-ancestor`).
- `fwd-port.sh --train <repo>` — the live forward-merge DAG from upstream merge commits (`X --> Y` = X merged into Y).
- `fwd-port.sh --diverge <repo> <sha> <target>` — **does the higher branch already have its own version of the touched files?** If DIVERGED → do NOT blind-merge; reconcile manually (this is the "other branch's implementation is different/wrong" case).
- `fwd-port.sh --path <repo> <from-branch>` — the forward chain a fix must ride.
- `fwd-port.sh --audit <repo>` — all case-graph fixes not yet in the latest upstream release (the forward-port worklist).
Get the `<sha>` from `claude/kg/bin/kg cases <flow>` / `kg error <code>`.

**Workflow:** `kg cases` → `fwd-port <sha>` (gaps) → `--train`/`--path` (verify live direction) → `--diverge` per target (clean vs reconcile) → forward-port along the train → push to **origin** only, exact branch, on explicit confirm → PR to upstream. Record the outcome in the CHANGELOG (`forward-ported to 3.4/3.5` or `branch-specific — do NOT forward-port`) so it becomes a queryable case.

**Correctness (validated 2026-06-10 — avoid false positives):**
- **Fetch upstream first.** Stale refs are the #1 false-positive source; the tool warns if upstream was fetched >12h ago. Run `git -C <repo> fetch upstream`.
- **Branch discovery is anchored** to real `^mfi_(integration|release)_v[0-9.]+$` refs (excludes `_bkup`/`_eks`/suffix branches that previously produced phantom "MISSING" against non-existent refs).
- **Ancestry is reliable here** because forward propagation is **merge-based** (≈200/200 merges on release branches), not cherry-pick — so `merge-base --is-ancestor` never gives a false "has fix" or false "absent" for a genuinely-merged fix.
- **Gap list caveat:** plain `fwd-port <repo> <sha>` lists branches **version-ordered**, so parallel/older lines (e.g. `3.3.1.0.x` vs `3.3.1.1`) also show `absent` — that is exact-but-not-actionable. The **real forward targets are the merge DAG**: `fwd-port.sh --path <repo> <fix-branch>`. Decide forward-ports from `--path`, not version order.

**Don't break code with an incorrect push.** A `pre-push` guard is installed in every repo (`claude/kg/bin/install-pre-push.sh`): it BLOCKS pushes to upstream/khoslalabs and WARNS on direct release-train pushes. Reinforces boundary Rule 1 (push only to origin, on confirm). See [[feedback_darpan_git_via_darpansolanki]], [[reference_system_kg]].
