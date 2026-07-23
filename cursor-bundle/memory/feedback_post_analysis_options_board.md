# Post-analysis OPTIONS BOARD (planning engine)

**Standing (2026-07-23):** After analysis / RCA / Jira triage / performance review / “what’s next?”, agents must emit a full **L0 + L1 + L2 + L3** options board before a single recommended next step.

## Why

SP-308 analysis ended with “gather prod evidence” only and omitted available **code** L0/L1 options (N+1 `getCustomerDetails`, consumer thread tuning). User correction: planning must surface **every** option tier after analysis — including code fixes — not bury them behind evidence-only next actions.

## Rules

- Emit **L0 + L1 + L2 + L3** every time (`N/A — <one line>` only if truly inapplicable).
- Include code/config/ops options when they exist in the codebase.
- Evidence/prod checks may be a **prerequisite under a tier**, never a substitute for the board.
- Still discuss-before-updating — board is selectable; do not mutate until user picks a tier.

## Enforcement

- Autopilot directive: `OPTIONS BOARD (mandatory after analysis): …` in `scripts/testing/workspace_autopilot.py`
- Always-on: `.cursor/rules/00-workspace-core.mdc` § Post-analysis OPTIONS BOARD
- Gate E: `.cursor/rules/10-quality-gates.mdc`
- Skill: `.cursor/skills/architect-thinking/tiered-solutions.md`
- Brain: `cursor-bundle/brain/rules/tiered-solution-approach.md`
