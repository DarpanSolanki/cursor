---
name: feedback_stale_branch_mapping_docs
description: Hand-maintained branch/repo tables rot and can invert — regenerate from live git, and never trust a doc's checkout claim
metadata:
  type: feedback
---

Darpan spotted a `[PROVISIONAL] initial-setup=delayed_payment_` banner and predicted stale mappings
across the workspace. He was right, and the failure was worse than drift — it was **inverted**.

`cursor-bundle/brain/workspace-state.md` (2026-07-17) claimed `trustt-platform-actor` was the WIP
repo on `feature/delayed_payment_interest` and `trustt-platform-initial-setup` was clean on
`mfi_integration_v3.7.1`. Live state was the exact reverse.

**Why:** an agent trusting that table looks for DPI WIP code in a repo that does not have it, and
treats the actual WIP repo as a release train — then reports "field/API missing" from the wrong
train, which `30-kg-discipline.md` § DPI branch gate explicitly forbids.

**How to apply:**

- **Never state a repo's branch from a doc.** Read live git, or `kg watermark`. Docs describe intent
  (canonical trains); git describes reality. `workspace-state.md` says this at the top — obey it.
- **Prescriptive vs descriptive.** "Canonical accounting branch = 3.7.1" is a target and stays true
  when the checkout differs. "Repo X is on branch Y" is a fact with a shelf life. Only the second
  kind rots; do not "fix" the first to match a checkout.
- **A dead path fails silently.** `git -C <missing-dir>` prints nothing and returns non-zero, which
  reads as "the commit is absent" rather than "you looked in the wrong place". After the 2026-07-15
  `novopay-* → trustt-*` rename, `reference_dpi_feature_branch.md` carried exactly that command.
  `scripts/lib/dead_repo_ref_gate.py` (in `workspace-hygiene.sh`) now catches runnable dead paths
  while leaving ~28k historical mentions alone.
- **Do not mass-rename history.** Changelogs and KG snapshots naming old repos are correct records.
  Rewriting them falsifies the audit trail; only executable positions matter.

Related: [[reference_dpi_feature_branch]] · [[reference_forward_merge_chain]] ·
[[feedback_fetch_latest_before_checking_code]]
