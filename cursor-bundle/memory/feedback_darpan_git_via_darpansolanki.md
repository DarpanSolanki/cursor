---
name: feedback_darpan_git_via_darpansolanki
description: All git operations (push) for repos under the darpan folder must be handled via the DarpanSolanki user
metadata: 
  node_type: memory
  type: feedback
  originSessionId: 80227870-3ec2-4675-8e0f-670133d28a14
---

For every repo under `/home/darpan/darpan/` (the 17 service checkouts), all git operations — **especially push** — must be performed **as the DarpanSolanki user**, not the gh-logged-in account (`AiTdpBugFixer`).

**Why:** the user owns these forks as DarpanSolanki (`origin = https://github.com/DarpanSolanki/<repo>.git`); authorship is already pinned to `DarpanSolanki <darpan@novopay.in>` per [[feedback_darpan_boundary]] / CLAUDE.md rule 4. Pushes must match that identity, not leak AiTdpBugFixer.

**How to apply:**
- Commit identity is already correct (repo-level `user.name=DarpanSolanki`, `user.email=darpan@novopay.in`).
- The credential helper from [[reference_github_connectivity_fix]] (`gh auth git-credential`) serves **AiTdpBugFixer's** token for ALL github.com HTTPS — so it must NOT be the credential used for pushes to DarpanSolanki forks.
- **Both fetch AND push** must go via DarpanSolanki (user confirmed 2026-06-08) — not just push.
- **Chosen setup (2026-06-08, remotes updated 2026-07-15):** dedicated SSH key `~/.ssh/id_darpansolanki` + `~/.ssh/config` host alias `github-darpan` (HostName github.com, IdentitiesOnly). Typical HTTPS remotes on sliProd now: `origin` → `https://github.com/DarpanSolanki/<trustt-repo>.git` and `upstream` → `https://github.com/trusttai/<trustt-repo>.git` (local folders may still be `novopay-*`; map in `scripts/lib/github_repo_map.py`). Upstream push still forbidden. Name map: `docs/setup/github-org-repo-rename-developer-guide.md` / `scripts/lib/github_repo_map.py`.
- The DarpanSolanki **public key is registered and working** (verified 2026-06-09: `ssh -T git@github-darpan` → `Hi DarpanSolanki!`). Pushes to `origin` authenticate as DarpanSolanki. Still **ask before pushing**.
- upstream (`trusttai`, formerly khoslalabs) push stays forbidden regardless.
