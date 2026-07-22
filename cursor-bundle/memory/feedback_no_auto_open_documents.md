# No auto-open of documents (STANDING)

**Preference (Darpan, 2026-07-20):** Do **not** automatically open documents in the IDE.

## Rule

- After guides, ops SQL, runbooks, handoff files, HTML: **print the path only**.
- User clicks / opens the file themselves.
- IDE open is **opt-in**: only when they say "open it", "open in IDE", or equivalent.

## Implementation

- Script default: `scripts/bin/open-final.sh` prints paths; opens only with `--open` / `OPEN_FINAL=1`.
- Rule: `.cursor/rules/00-workspace-core.mdc`
- Skill: `.cursor/skills/open-final-file/SKILL.md`

## Do not

- Call MCP `open_resource` for finished artifacts unless explicitly asked.
- Rely on sessionStart or other hooks to open HTML guides (hooks must not open files).
