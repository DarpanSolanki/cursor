<!-- Relocated verbatim from .cursor/rules/accounting.mdc / accounting-module-knowledge.mdc. Edit these skill topic files; thin accounting.md only routes here. -->

## Accounting knowledge sync

When any code/config change is made under `trustt-platform-accounting/` (fix/enhancement/bug work), the agent must update the matching topic file under `.cursor/skills/accounting-knowledge/` to reflect the new or corrected behavior.

Rules:
- Update only with information verified from the code (processor/service/tasklet/writer/service methods). Do not assume.
- If the change affects only a calculation utility and does not alter batch entrypoints/flows, add a short “behavior correction” note in the most relevant existing section (or add a clearly scoped new subsection).
- If the agent cannot verify the impact quickly, add a clearly labeled `UNVERIFIED:` note and list exactly what needs follow-up reading.
- After the update, run the same entrypoint-vs-rule consistency check (the “missing entrypoints” script) if it was previously used for coverage.

---

## Accounting knowledge sync

When any code/config change is made under `trustt-platform-accounting/` (fix/enhancement/bug work), the agent must update the matching topic file under `.cursor/skills/accounting-knowledge/` to reflect the new or corrected behavior.

Rules:
- Update only with information verified from the code (processor/service/tasklet/writer/service methods). Do not assume.
- If the change affects only a calculation utility and does not alter batch entrypoints/flows, add a short “behavior correction” note in the most relevant existing section (or add a clearly scoped new subsection).
- If the agent cannot verify the impact quickly, add a clearly labeled `UNVERIFIED:` note and list exactly what needs follow-up reading.
- After the update, run the same entrypoint-vs-rule consistency check (the “missing entrypoints” script) if it was previously used for coverage.

---

## Target for future knowledge writes (Upgrade 2)

Update the **matching file under `.cursor/skills/accounting-knowledge/`** — not a mega `.cursor/rules/accounting*.mdc`.
Thin `.cursor/rules/accounting.mdc` is gates + routing only.
Former `accounting-module-knowledge.mdc` was deleted; its body lives in topic files + `_source-accounting-module-knowledge.md`.
