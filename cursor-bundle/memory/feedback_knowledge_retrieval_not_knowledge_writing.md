---
name: knowledge-retrieval-not-knowledge-writing
description: Gaps kept recurring because every enhancement round added knowledge and write-gates; nothing closed the retrieval loop — the workspace logged 999 grep-leaks and never read its own counter
metadata:
  type: feedback
---

Gaps kept recurring because every enhancement round added knowledge and write-gates; nothing closed the retrieval loop — the workspace logged 999 grep-leaks and never read its own counter

**Why:** Darpan, 2026-08-07, after TDPQA-241 rediscovered the notification-message Redis cache by reading platform-lib line by line. The knowledge existed and was correct — `.cursor/redis-key-registry.md:101` and GAP-058 both described it exactly. `.cursor/kg-grep-leak.jsonl` had **999** entries recording precisely this class of bypass, and its only consumer was `workspace-doctor.sh`, which nothing runs. Three structural causes, none of them 'missing knowledge': routing is keyed on topic nouns (I did not know it was a 'Redis' problem until after I solved it); the fact sat behind a Medium gap that the bootstrap digest does not carry; and no glob routed on migration paths, so editing the notifications migration surfaced nothing.

**How to apply:** when a workspace gap recurs, ask whether the knowledge was missing or merely unreached — check `kg-grep-leak.jsonl` first. Adding another memory file is the wrong reflex if the fact was already written down. The fix that works is feedback at the moment of bypass: the grep-leak hook now answers with `scripts/lib/knowledge_index.py` (term → file:line over .cursor + memory, ~50ms) instead of only counting, and `masterdata-row-change-cache-evict.md` routes on `**/flyway/**`. Never again declare the workspace 'enhanced' without naming what measures it.
