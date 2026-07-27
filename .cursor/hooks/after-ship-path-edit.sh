#!/usr/bin/env bash
# afterFileEdit — flag any ship-path edit; accumulate tiered pending work via register_pending_ship
# (smart ntest_cases from build_impact — never naive registry_case_for_api-only freeze).
set -euo pipefail
ROOT="${CURSOR_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
INPUT=$(cat)
FILE=$(echo "$INPUT" | python3 -c "import json,sys; print(json.load(sys.stdin).get('file_path',''))" 2>/dev/null || true)
[[ -n "$FILE" ]] || exit 0

python3 "$ROOT/scripts/lib/infer_ship_apis.py" --is-ship-path "$FILE" 2>/dev/null || exit 0

# ── X4 ORIENT-BEFORE-EDIT GATE ─────────────────────────────────────────────
# Ship-path file edited → require kg orient/flow within last 60 min this session.
python3 - <<'ORIENT_PY' "$ROOT"
import sys, json, time
from pathlib import Path
root = Path(sys.argv[1])
session_file = root / ".cursor" / "kg-orient-session.json"
MAX_AGE = 3600  # 60 minutes
banner = None
if not session_file.is_file():
    banner = "KG ORIENT REQUIRED — no kg orient/flow recorded this session. Run: python3 cursor-bundle/kg/bin/kg.py orient <apiName>"
else:
    try:
        state = json.loads(session_file.read_text(encoding="utf-8"))
        last_ts = state.get("last_orient_ts", 0)
        age = int(time.time()) - last_ts
        if age > MAX_AGE:
            banner = f"KG ORIENT STALE ({age//60}m ago) — re-run: python3 cursor-bundle/kg/bin/kg.py orient {state.get('last_orient_api','<apiName>')}"
    except Exception:
        banner = "KG ORIENT REQUIRED — session state unreadable"
if banner:
    flag = root / ".orient-required"
    flag.write_text(banner + "\n", encoding="utf-8")
    print(f"\n{'='*70}\n⚠  ORIENT-BEFORE-EDIT GATE: {banner}\n{'='*70}\n", file=sys.stderr)
    sys.exit(1)
ORIENT_PY

python3 - <<'PY' "$FILE" "$ROOT"
import sys
from pathlib import Path

sys.path.insert(0, str(Path(sys.argv[2]) / "scripts/lib"))
from register_pending_ship import register_paths  # noqa: E402

f, root = Path(sys.argv[1]), Path(sys.argv[2])
p = f if f.is_absolute() else root / f
try:
    rel = str(p.relative_to(root))
except ValueError:
    rel = str(p)
register_paths(root, [rel], source="afterFileEdit")
PY
exit 0
