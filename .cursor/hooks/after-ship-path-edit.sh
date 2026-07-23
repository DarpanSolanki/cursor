#!/usr/bin/env bash
# afterFileEdit — flag any ship-path edit; accumulate tiered pending work via register_pending_ship
# (smart ntest_cases from build_impact — never naive registry_case_for_api-only freeze).
set -euo pipefail
ROOT="${CURSOR_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
INPUT=$(cat)
FILE=$(echo "$INPUT" | python3 -c "import json,sys; print(json.load(sys.stdin).get('file_path',''))" 2>/dev/null || true)
[[ -n "$FILE" ]] || exit 0

python3 "$ROOT/scripts/lib/infer_ship_apis.py" --is-ship-path "$FILE" 2>/dev/null || exit 0

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
