---
name: reference-enforcement-hooks
description: "How the workspace ACTIVELY enforces skills/KG/brain-doc usage and discipline — via hooks in .claude/settings.json, not passive memory."
metadata: 
  node_type: memory
  type: reference
  originSessionId: c83d0444-fd8e-4367-9d60-f7b569d2994c
---

Memory/feedback files are **passive** (advisory context) — the harness does not execute them, so they cannot force behaviour. Active enforcement lives in **six hooks** at `/home/darpan/darpan/.claude/settings.json`:

1. **SessionStart** → `kg-session-watermark.sh` — runs `kg fresh` at session open: is the KG branch-correct for the live checkout? See [[reference_system_kg]] branch-safety.
2. **UserPromptSubmit** → `route-engineering-ask.sh` — on any substantive ask (RCA/fix/new-impl/analysis/LMS keyword) injects the §2 ladder: **brain-find → skill → `kg` → code last**, requires naming what was used. Silent on trivial. Operationalises [[feedback_brain_first_then_code]], [[feedback_deep_rca_before_fix]].
3. **PreToolUse (Edit\|Write\|NotebookEdit)** → `boundary-guard.sh` — **mechanically DENIES** writes outside `/home/darpan/darpan/` (+ memory dir + `/tmp`). Makes the #1 boundary rule an enforced gate, not advice. Syntactic path check (`realpath -ms`, no symlink-follow), **fail-OPEN** on any error so it can never brick editing. [[feedback_darpan_boundary]].
4. **PreToolUse (Edit\|Write)** → `pre-tool-discipline-reminder.sh` — reprints the 4 proof gates + KG safety gate + keep-docs-current. [[feedback_proof_backed_agent_discipline]], [[feedback_no_half_fixes_accounting]], [[feedback_keep_knowledge_current]], [[feedback_no_inmem_mutation_after_cas]].
5. **PreToolUse (Bash)** → `git-rule-guard.sh` — **self-gates** to real `git push` only; injects the pre-push checklist (build-green / author=DarpanSolanki / changelog / origin-not-upstream / fwd-port / awaiting-QA). [[feedback_build_before_push]], [[feedback_darpan_git_via_darpansolanki]].
6. **PostToolUse (Bash)** → `post-commit-reminder.sh` — self-gates to real `git commit`; reminds: prepend CHANGELOG (→ KG case), next `kg` query auto-folds the fix, status='pushed; awaiting QA'. [[feedback_changelog]].

The two git hooks **self-gate inside the script** (jq-extract `.tool_input.command` + grep for `git push`/`git commit`) — the settings `if:` filter doesn't reliably parse compound commands, so the script is the reliable gate; silent on every other Bash call (perf).

Tooling: in-boundary static `claude/bin/jq` (1.7.1) for precise field extraction — no system `apt` (boundary). `sqlite3` CLI absent; KG runs on python3 stdlib sqlite3. To review/disable: `/hooks`. Newly-added hooks need `/hooks` opened once (or restart) for the settings watcher to pick them up.
