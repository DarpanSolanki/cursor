---
name: feedback_fetch_latest_before_checking_code
description: "When verifying deployed/branch code against a stack trace or RCA, git fetch origin AND upstream first — never trust the local checkout's branch/SHA."
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 80931fd1-e2bd-4b89-b085-afef484aba34
---

When checking code to diagnose an issue (stack-trace line mapping, "is this fix in", branch-current behaviour), the FIRST step is always `git fetch origin && git fetch upstream` in the relevant repo, then read the code from the named deployed branch ref (e.g. `upstream/feature/delayed_payment_interest`), NOT from the working-tree checkout.

**Why:** the local checkout is frequently on a different/stale branch than what the env actually runs. In the 2624020 disbursement RCA, the working tree was on `feature/dpic-v1`, the user first said `mfi_release_v3.5.0`, then the real deployed branch was `feature/delayed_payment_interest` — only on `upstream` (`trusttai`), not `origin`. Mapping the stack trace against the wrong ref gives wrong line numbers and wrong conclusions.

**How to apply:** fetch both remotes, confirm the deployed branch tip (`git log -1 <remote>/<branch>`), then map stack-trace line numbers against `git show <remote>/<branch>:<path>`. Verify the exact lines match (e.g. line 65/130/156) before claiming an RCA. Pairs with the proof-backed evidence-before-claim gate. Related: [[feedback_darpan_git_via_darpansolanki]].

**Train branch push/analyse:** Also apply [[feedback_train_branch_sync_origin_upstream]] — base on upstream tip, reconcile unique origin commits, never push from origin-behind-upstream without STALE+sync.
