---
name: reference_workspace_canonical_setup
description: Canonical paths for the Cursor sliProd LMS workspace (routing SoT — do not follow stale /home/darpan/darpan or .claude paths).
metadata:
  node_type: memory
  type: reference
---

**Canonical workspace root:** `/home/darpan/Documents/sliProd`

| Layer | Path |
|-------|------|
| Agent rules / hooks / skills | `.cursor/` (`hooks.json`, `rules/*.mdc`, `skills/`) |
| Brain + KG + memory | `cursor-bundle/` (`brain/`, `kg/`, `memory/`, `schema/`) |
| Harness / ntest / ops | `scripts/` (`bin/`, `testing/`, `dpic/`, `sql/`) |
| Service checkouts | `trustt-platform-*` / `novopay-*` under the same root |
| Agent entry | `AGENTS.md` (not `CLAUDE.md` as Cursor SoT) |

**Do not use (stale / wrong product):**
- `/home/darpan/darpan/` — old Claude Code home; dead for this workspace
- `.claude/`, `claude-bundle/`, `CLAUDE_PROJECT_DIR` — Claude Code sibling (`sliProdClaude`); Cursor uses `.cursor/` + `cursor-bundle/` + `CURSOR_PROJECT_DIR`
- Hardcoded absolute script paths — resolve via `ROOT="$(cd "$(dirname "$0")/../.." && pwd)"` or `Path(__file__).resolve().parents[N]`

**Working tooling:**
- DB: `scripts/db-qa3.sh` / `scripts/bin/db-local*.sh` (not `claude/db-tools`)
- KG: `python3 cursor-bundle/kg/bin/kg.py` + MCP `trustt-kg` from `.mcp.json` / `.cursor/mcp.json`
- Hooks: `.cursor/hooks.json` → `.cursor/hooks/*.sh`
- Build: `cd <repo> && ./gradlew build -x test` (Java 17)

Sibling clone for compare-only: `/home/darpan/Documents/sliProdClaude` (outside this tree). Never `chdir` harness smoke into it.

Related: [[feedback_darpan_boundary]], [[reference_enforcement_hooks]], [[reference_system_kg]].
