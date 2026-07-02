---
name: project_ud_to_feature_capability
description: "The workspace now has a green-field UD→feature pipeline (ud-to-feature skill + feature-development-playbook guide), not just bug-fix/RCA rails."
metadata: 
  node_type: memory
  type: project
  originSessionId: 1ff149a3-d946-4cfd-b9b5-4dc0c4974585
---

The darpan workspace was originally tuned almost entirely for bug-fix / RCA / accounting-debugging (rca-workflow, qa-handoff, lan-360, state-machine-safety, etc.). On 2026-06-11 a **green-field UD→feature capability** was added so a Product UD (User Document / BRD / FSD / PRD, usually `.docx` + sample-calc `.xlsx`) can be taken end-to-end from spec → verified design → code → QA, driven by brain + KG before any code is opened.

**What was added (all in-boundary):**
- `claude/guides/feature-development-playbook.md` — the green-field substrate: UD→behavioural-rules table → KG gap-analysis (`kg search/flow/crud/impact/writes/cases`) → **12-layer placement matrix** (entity·Flyway·constants·DAO·service·processor·orchestration-XML·batch·GL/appropriation·reversal/lifecycle·surfacing·events) → tiered design + rails → code/build/diff → open-Qs → qa-handoff → fold-into-brain+KG.
- `.claude/skills/ud-to-feature/SKILL.md` — the repeatable pipeline skill driving that guide. Auto-activates on UD/BRD/FSD/PRD/"implement this feature"/`UDs/` references.
- Wired into CLAUDE.md §2 topic map + §4 skill table.

**Anchor facts:**
- The one existing UD→implementation precedent is **DPI v1** ([UDs/](../../darpan/UDs/) → `claude/dpic/`) — the playbook cites it at every step as the worked example.
- "UD only" honestly means: scope + design + impact + plan + QA scenarios come purely from UD+KG+brain; the **code-writing step still drops to the checkouts** (precedence-ladder rung 6) — by design, not a gap.

**Why:** A UD is a different workflow shape from a bug fix; without this, each feature re-derived the approach by hand (as DPI was).
**How to apply:** When a UD/feature lands, invoke `ud-to-feature`; respect the same rails as bug-fixes ([[feedback_no_inmem_mutation_after_cas]], no-flow-break, [[feedback_keep_knowledge_current]] fold-back). Pairs with [[reference_system_kg]] for scoping and [[feedback_qa_handoff_package]] for delivery.
