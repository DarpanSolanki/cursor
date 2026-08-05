---
name: feedback_worktree_bypasses_all_gates
description: "Editing a service repo through a git worktree outside the workspace root silently disables EVERY path-based gate. Work in the real repo dir."
metadata:
  node_type: memory
  type: project
---

**Every gate in this workspace keys on the edited file path sitting under the workspace root**
(`/home/darpan/Documents/sliProd`). `git worktree add /tmp/...` to get a second branch
checked out puts edits outside that root, and then — silently, with no warning —
none of these fire:

- `afterFileEdit` → `after-ship-path-edit.sh` → no `.cursor/.pending-ship-work.json`
- the orient-before-edit KG gate
- `ship_push_gate.py --needs-close` → `push-origin.sh` skips the ship loop entirely
- therefore `ship-loop-gate.sh` and everything it runs: `java-comment-lint`,
  `acceptance_coverage.py`, `reuse_query_gate.py`, `money_behavior_parity_gate.py`
- `rule-router` (so the path-scoped rule for that file is never named)

**How this bit:** TDPQA-234 (2026-08-04) was written in `/tmp/.../acct-371`, a worktree added
because the main checkout was on a different train. Every gate stayed silent, and the change
shipped with 16 comment lines against RULE 1 plus a hack the rules forbid.

**How to apply:** do money-path work in the real `trustt-*` directory — switch the branch there
(`sync-branches.sh --train …`) rather than adding a worktree. `is_ship_path()` now re-anchors
worktree paths via `normalize_worktree_path()` in `scripts/lib/infer_ship_apis.py`, but that
only restores the *edit* hooks; if you bypass `push-origin.sh` the ship loop is still skipped.

Related: [[feedback_keep_code_simple]] · [[feedback_ship_test_autonomy_change_map]]
