---
name: open-final-file
description: >-
  Share a forwardable workspace file path (ops SQL, handoff artifact).
  Default: print path only — do NOT auto-open the IDE.
  Open in IDE only when the user explicitly says "open it" / "open in IDE".
triggers:
  - open final
  - final version
  - no diff
  - forward file
  - open in IDE
  - open-final
requires: []
reads: []
writes: []
feeds: []
scripts:
  - scripts/bin/open-final.sh
---

## Routing metadata

<!-- ported from Cursor skill frontmatter -->

- **triggers:** `open final`, `final version`, `no diff`, `forward file`, `open in IDE`, `open-final`
- **requires:** []
- **reads:** []
- **writes:** []
- **feeds:** []
- **scripts:** `scripts/bin/open-final.sh`

# Open final file (path-first — IDE open is opt-in)

Cursor **Agent Review** links (`[Review](…#changes)`) open a **diff-style** view. That is the wrong surface when the user wants the **final file content** (ops SQL, handoff artifact) to read or forward.

**Standing preference (Darpan):** never auto-open documents in the IDE. User clicks the path themselves.

## Default (always)

After creating or simplifying a **forwardable** workspace artifact:

1. **Print the path only** — relative + absolute. Do **not** call MCP `open_resource`, do **not** run `open-final.sh --open`, do **not** force an IDE buffer.
2. Optional: `bash scripts/bin/open-final.sh <path>` (default mode prints absolute path; no IDE open).

```text
Final file: scripts/sql/adhoc/example.sql
Absolute: /home/darpan/Documents/sliProd/scripts/sql/adhoc/example.sql
```

Optional markdown file link (user clicks → editor when supported):

`[example.sql](/home/darpan/Documents/sliProd/scripts/sql/adhoc/example.sql)`

## Opt-in IDE open (only when user asks)

Only if the user explicitly says **"open it"**, **"open in IDE"**, **"open final"**, or similar:

| Option | How | View |
|--------|-----|------|
| MCP | `cursor-app-control` → `open_resource` with `file:///abs/path` | Editor buffer |
| Shell | `bash scripts/bin/open-final.sh --open <path>` or `OPEN_FINAL=1 …` | Editor buffer (`cursor -r`) |

```json
{
  "server": "cursor-app-control",
  "toolName": "open_resource",
  "arguments": {
    "uri": "file:///home/darpan/Documents/sliProd/scripts/sql/adhoc/example.sql"
  }
}
```

URI must be under the workspace (or `~/.claude`). Fragment `#L10` / `#L10:5` is allowed for line/column.

## Review / diff

`[Review](id#changes)` = **diff chrome** — use only when the user asks for change review. Label clearly if both path and Review are linked.

## Do not

- Auto-open HTML guides, SQL, runbooks, or any finished artifact without an explicit open request.
- Invent a product toggle that converts `#changes` Review into a clean buffer.
- Point users at browser URLs for local SQL.
- Use `cursor -d` / merge UI when they asked for final content.
