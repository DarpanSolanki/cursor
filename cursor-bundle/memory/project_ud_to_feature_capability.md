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
- `cursor-bundle/brain/guides/feature-development-playbook.md` — UD→behavioural-rules → KG gap-analysis → 12-layer placement matrix → tiered design → code/build → qa-handoff → fold-into-brain+KG.
- `.cursor/skills/` feature / accounting skills (and related playbooks) — activate on UD/BRD/FSD/PRD/"implement this feature".
- Wired into `AGENTS.md` + `.cursor/rules/` topic map.

**Anchor facts:**
- The one existing UD→implementation precedent is **DPI v1** (`UDs/` → `cursor-bundle/brain/dpic/` / `scripts/dpic/`) — the playbook cites it as the worked example.
- "UD only" honestly means: scope + design + impact + plan + QA scenarios come purely from UD+KG+brain; the **code-writing step still drops to the checkouts** (precedence-ladder rung 6) — by design, not a gap.

**Why:** A UD is a different workflow shape from a bug fix; without this, each feature re-derived the approach by hand (as DPI was).
**How to apply:** When a UD/feature lands, invoke `ud-to-feature`; respect the same rails as bug-fixes ([[feedback_no_inmem_mutation_after_cas]], no-flow-break, [[feedback_keep_knowledge_current]] fold-back). Pairs with [[reference_system_kg]] for scoping and [[feedback_qa_handoff_package]] for delivery.
