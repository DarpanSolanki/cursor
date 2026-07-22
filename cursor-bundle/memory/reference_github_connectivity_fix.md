---
name: reference_github_connectivity_fix
description: "How to fix \"could not read Username for https://github.com\" git fetch/push failures in the darpan workspace"
metadata: 
  node_type: memory
  type: reference
  originSessionId: 80227870-3ec2-4675-8e0f-670133d28a14
---

`git fetch upstream` fails with `fatal: could not read Username for 'https://github.com': No such device or address` because the 17 darpan repos use **HTTPS remote URLs with no credential helper configured**.

Auth itself is fine: `gh` CLI is logged in as **AiTdpBugFixer** (`/home/darpan/.config/gh/hosts.yml`) and **SSH to git@github.com works**. The gap is only that git's HTTPS transport has no helper.

**Fix (one-time, global):**
```
gh auth setup-git
```
This registers `credential.https://github.com.helper = !/usr/bin/gh auth git-credential` in `~/.gitconfig`, after which `git fetch`/`git ls-remote` over the existing HTTPS remotes authenticate via the gh token. Verified working across repos (accounting-v2, batch). Fetch is a read — within boundary; pushing to upstream is still forbidden by [[feedback_darpan_boundary]] (push to `trusttai` upstream = blocked by `push-origin.sh` / hooks anyway).
