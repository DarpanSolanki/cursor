---
name: retrieval-coverage-all-search-surfaces
description: The grep-leak hook only ever saw shell grep — PreToolUse matched Bash only, so agent-native Grep/Glob/Read were unhooked entirely
metadata:
  type: feedback
---

The grep-leak hook only ever saw shell grep — PreToolUse matched Bash only, so agent-native Grep/Glob/Read were unhooked entirely

**Why:** Darpan, 2026-08-07. Closing the retrieval loop on shell `grep` covered the minority surface. `.cursor/settings.json` registered PreToolUse for **Bash only**, so the Grep, Glob and Read tools — the ones an agent actually reaches for — produced no signal at all. The hook even documented the limitation (SU-KG-003) and it was left standing.

**How to apply:** `.cursor/hooks/knowledge-answer.py` is registered on `PreToolUse: Grep|Glob|Read` and prints `file:line` from `scripts/lib/knowledge_index.py` before the search runs; the shell path is covered by `grep_leak_answer.py`. Both silent when nothing is indexed. When adding any new agent capability, ask which surfaces it bypasses — a guard on one tool is not coverage. Costs: fast-exit 8-24ms, answer path 38ms (was 191ms across four python spawns before consolidation).
