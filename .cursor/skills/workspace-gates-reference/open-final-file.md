<!-- VERBATIM archive of former alwaysApply `.cursor/rules/open-final-file.mdc`. Do not soften. Edit thematic rules; keep this as mandate proof. -->

# Open final file vs Review diff

When sharing a **shipped / ops / forwardable** file (especially `scripts/sql/**`, release packs, handoff artifacts, HTML guides):

1. **Default — path only:** print the plain absolute/relative path. User opens the file themselves. Do **not** call MCP `open_resource`, do **not** run `open-final.sh --open` / `OPEN_FINAL=1`, and do **not** force an IDE buffer.
2. **Opt-in IDE open:** only when the user explicitly says "open it" / "open in IDE" / "open final" — then MCP `open_resource` or `bash scripts/bin/open-final.sh --open <path>`.
3. **Diff / Review:** only when the user asks for change review — `[Review](id#changes)` is **diff chrome**, not the final file.

Skill: `.cursor/skills/open-final-file/SKILL.md`. Standing preference: `cursor-bundle/memory/feedback_no_auto_open_documents.md`.
