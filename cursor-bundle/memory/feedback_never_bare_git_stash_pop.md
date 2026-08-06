---
name: feedback_never_bare_git_stash_pop
description: Never use bare `git stash`/`git stash pop` in this workspace — stash@{0} is usually someone else's; and check tracked status before rm
metadata:
  type: feedback
---

On 2026-08-06 a bare `git stash pop`, used to restore files after an old-vs-new comparison, popped a
**pre-existing user stash** from commit `74b1c57` instead of the one just created. It conflicted and
left `<<<<<<<` markers in `scripts/testing/workspace_autopilot.py` — a syntax error in the file
every single task executes. The workspace root carries **6 long-lived stashes**; `stash@{0}` is
almost never yours.

**Why:** bare `git stash pop` always takes `stash@{0}`. A scoped `git stash -- <paths>` can also
silently no-op (nothing matching to stash), so the later `pop` reaches for whatever was on top.

**How to apply:**

- **Never** `git stash` / `git stash pop` bare here. To compare a file against another commit, do
  not stash at all — `git show <sha>:<path>` to a scratch file, or `git checkout <sha> -- <path>`
  followed by `git checkout HEAD -- <path>`.
- If a stash is genuinely needed: `git stash push -m "<label>" -- <paths>`, then pop **by name**
  (`git stash pop stash^{/<label>}`), and confirm `git stash list | wc -l` is unchanged afterwards.
- **Comparing an old version must not run from a different cwd.** An earlier attempt copied the old
  `kg.py` to `/tmp` and ran it there; it could not resolve `kg.db` and reported a false "DIFFERS".
  Compare in place.
- **Check tracked status before `rm`.** Cleaning up stash residue also deleted
  `scripts/bin/workspace-doctor.sh`, which was tracked. `git ls-files --error-unmatch <path>`
  first, or `git clean -n` to see only true untracked files.
- After any recovery, verify three things explicitly: the file parses, zero conflict markers
  remain, and `git stash list | wc -l` matches what it was before.

Related: [[feedback_keep_code_simple]] · [[reference_router_v2_minimal_path]]
