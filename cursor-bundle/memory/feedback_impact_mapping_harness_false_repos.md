---
name: feedback_impact_mapping_harness_false_repos
description: "Ship/impact gap — novopay-*.sh/md and scripts/dpic must not invent service repos/apis or force sticky money close on harness push."
metadata:
  node_type: memory
  type: feedback
---

**Miss (2026-08-05):** Harness push lagged on impact mapping and tried money ship-loop for work that only touched workspace scripts/docs.

**Root causes (proven):**
1. `infer_repo_from_path` treated path *parts* starting with `novopay-`/`trustt-` as repos — so `scripts/bin/novopay-service.sh` and `novopay-framework.md` made `is_workspace_push_safe_paths` False → sticky money close on harness push.
2. `DOMAIN_PRIMARY_API` needle `"/dpi"` matched `scripts/dpic/` and `dpi-*.md` → invented `getLoanAccountOverviewDetails` for harness paths.

**Fix:** suffix-free repo dirs only; domain hints skipped for `scripts/`/`.cursor/`/`cursor-bundle/`; `/dpi/` trailing slash; harness/kb checked before repo in push-safe.

**Proof:** `python3 scripts/lib/test_impact_mapping_harness.py` + `test_ship_push_workspace_safe.py`.

Pairs with [[feedback_worktree_bypasses_all_gates]], ship_push_gate workspace-safe skip.
