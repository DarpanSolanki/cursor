#!/usr/bin/env bash
# Log rg/grep into service trees when KG may already answer (T6 grep-leakage counter).
set -euo pipefail
ROOT="${CURSOR_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
INPUT=$(cat || true)
CMD=$(echo "$INPUT" | python3 -c "import json,sys
try:
 d=json.load(sys.stdin); print(d.get('command') or '')
except Exception:
 print('')" 2>/dev/null || true)
[[ -n "$CMD" ]] || exit 0
echo "$CMD" | grep -Eqi '(^|[;|&[:space:]])(rg|grep)([[:space:]]|$)' || exit 0
echo "$CMD" | grep -Eqi 'trustt-platform-|novopay-platform-|novopay-mfi-|orchestration|_orc\.xml|Processor\.java' || exit 0
LOG="$ROOT/.cursor/kg-grep-leak.jsonl"
mkdir -p "$(dirname "$LOG")"
python3 - <<PY
import json, time
from pathlib import Path
root = Path("$ROOT")
cmd = '''$CMD'''
rec = {
  "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
  "cmd": cmd[:500],
  "note": "shell_rg_grep_service_tree",
}
path = root / ".cursor" / "kg-grep-leak.jsonl"
with path.open("a", encoding="utf-8") as f:
    f.write(json.dumps(rec, ensure_ascii=False) + "\n")
# rolling SELF-REPORT line
sr = root / "cursor-bundle" / "memory" / "SELF-REPORT.md"
if sr.is_file():
    n = sum(1 for _ in path.open(encoding="utf-8", errors="replace"))
    line = f"- grep-leak shell counter (cumulative jsonl lines): **{n}** (baseline sessions 172 grep / 50 kg — 2026-07-27)\n"
    txt = sr.read_text(encoding="utf-8")
    if "grep-leak shell counter" in txt:
        import re
        txt = re.sub(r"- grep-leak shell counter.*\n", line, txt, count=1)
    else:
        if "## KG" in txt:
            txt = txt.replace("## KG\n", "## KG\n" + line, 1)
        else:
            txt = txt.rstrip() + "\n\n## KG\n" + line
    sr.write_text(txt, encoding="utf-8")
PY
exit 0
