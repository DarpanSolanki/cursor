#!/usr/bin/env bash
# Log rg/grep/cat/sed/git-show into service trees when KG may already answer.
# Fast-exit in bash, then one Python SoT (grep_leak_answer.py) — DUMP + SERVICE
# patterns live there so this wrapper cannot drift.
#
# LIMITATION (SU-KG-003 CLOSED): Cursor IDE Grep tool is NOT hookable via
# beforeShellExecution — only shell invocations matching hooks.json matcher.
# Prefer MCP trustt-kg for LOOKUPs. Footnote: cursor-bundle/memory/SELF-REPORT.md § KG.
set -euo pipefail
ROOT="${CURSOR_PROJECT_DIR:-${CLAUDE_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}}"
INPUT=$(cat || true)
# ── fast-exit: no python spawn unless the payload looks like a service-tree probe ──
[[ "$INPUT" =~ (rg|grep|cat|sed\ -n|git\ show) ]] || exit 0
[[ "$INPUT" =~ (trustt-platform-|novopay-platform-|novopay-mfi-|orchestration|_orc\.xml|Processor\.java|src/main/java|src/test/java|in/novopay/|deploy/application) ]] || exit 0
printf '%s' "$INPUT" | python3 "$ROOT/.cursor/hooks/grep_leak_answer.py"
exit $?
