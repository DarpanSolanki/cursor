#!/usr/bin/env bash
# Env connectivity smoke — ping configured wrappers; write results into workspace-ops-state.md.
# Usage: env-smoke.sh [--write-state] [--env local|qa1|…]
# Never invents connectivity — records ok|fail|skip|unknown from this run.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
MATRIX="$ROOT/scripts/env/env-matrix.json"
STATE="$ROOT/.cursor/workspace-ops-state.md"
WRITE=0
ONLY=""
TIMEOUT_S="${ENV_SMOKE_TIMEOUT:-5}"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --write-state) WRITE=1; shift ;;
    --env) ONLY="${2:-}"; shift 2 ;;
    -h|--help) sed -n '2,6p' "$0"; exit 0 ;;
    *) echo "unknown: $1" >&2; exit 2 ;;
  esac
done

[[ -f "$MATRIX" ]] || { echo "missing $MATRIX"; exit 1; }

ping_one() {
  local name="$1" wrapper="$2"
  if [[ -z "$wrapper" || "$wrapper" == "unknown" || "$wrapper" == "null" ]]; then
    echo "$name|skip|no wrapper"
    return 0
  fi
  local path="$ROOT/$wrapper"
  if [[ ! -x "$path" && ! -f "$path" ]]; then
    echo "$name|fail|wrapper missing: $wrapper"
    return 0
  fi
  # Lightweight: SELECT 1 via wrapper --sql (read-only)
  local out rc=0
  out="$(timeout "$TIMEOUT_S" bash "$path" --sql "SELECT 1 AS ok;" 2>&1)" || rc=$?
  if [[ $rc -eq 0 ]] && echo "$out" | grep -qE '\bok\b|^\s*1\s*$|rows?'; then
    echo "$name|ok|SELECT 1"
  elif [[ $rc -eq 124 ]]; then
    echo "$name|fail|timeout ${TIMEOUT_S}s"
  else
    # Truncate noise
    local brief
    brief="$(echo "$out" | tr '\n' ' ' | head -c 120)"
    echo "$name|fail|${brief:-rc=$rc}"
  fi
}

mapfile -t ROWS < <(python3 - "$MATRIX" "$ONLY" <<'PY'
import json, sys
from pathlib import Path
m = json.loads(Path(sys.argv[1]).read_text())
only = sys.argv[2] or ""
envs = m.get("environments") or {}
for name, meta in envs.items():
    if only and name != only:
        continue
    w = meta.get("db_wrapper") or "unknown"
    print(f"{name}\t{w}")
PY
)

RESULTS=()
echo "=== env-smoke ==="
# Probes are independent network round trips; serial cost 9 envs x TIMEOUT_S.
TMPD="$(mktemp -d)"
trap 'rm -rf "$TMPD"' EXIT
i=0
for row in "${ROWS[@]}"; do
  name="${row%%$'\t'*}"
  wrap="${row#*$'\t'}"
  ping_one "$name" "$wrap" > "$TMPD/$i" &
  i=$((i + 1))
done
wait
for ((j = 0; j < i; j++)); do
  line="$(cat "$TMPD/$j" 2>/dev/null)"
  [[ -n "$line" ]] || continue
  RESULTS+=("$line")
  echo "  $line"
done

if [[ "$WRITE" == 1 ]]; then
  mkdir -p "$ROOT/.cursor"
  utc="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  # Append or replace ## Env smoke section
  if [[ -f "$STATE" ]]; then
    python3 - "$STATE" "$utc" "${RESULTS[@]}" <<'PY'
import sys
from pathlib import Path
path = Path(sys.argv[1])
utc = sys.argv[2]
results = sys.argv[3:]
text = path.read_text(encoding="utf-8") if path.is_file() else "# Workspace ops state\n"
marker = "## Env smoke"
block = [marker, "", f"Updated: {utc}", "", "| Env | Result | Detail |", "|-----|--------|--------|"]
for r in results:
    parts = r.split("|", 2)
    while len(parts) < 3:
        parts.append("")
    block.append(f"| {parts[0]} | {parts[1]} | {parts[2]} |")
block.append("")
block.append("Sessions: read this section instead of re-probing. Re-run: `bash scripts/bin/env-smoke.sh --write-state`")
block.append("")
new = "\n".join(block)
if marker in text:
    pre, rest = text.split(marker, 1)
    # drop old section through next ## or EOF
    idx = rest.find("\n## ", 1)
    if idx >= 0:
        text = pre.rstrip() + "\n\n" + new + rest[idx+1:]
    else:
        text = pre.rstrip() + "\n\n" + new
else:
    text = text.rstrip() + "\n\n" + new
path.write_text(text, encoding="utf-8")
print(f"→ wrote env smoke into {path}")
PY
  else
    {
      echo "# Workspace ops state (auto-generated — do not edit)"
      echo ""
      echo "Updated: $utc"
      echo ""
      echo "## Env smoke"
      echo ""
      echo "Updated: $utc"
      echo ""
      echo "| Env | Result | Detail |"
      echo "|-----|--------|--------|"
      for r in "${RESULTS[@]}"; do
        IFS='|' read -r n res det <<<"$r"
        echo "| $n | $res | $det |"
      done
      echo ""
      echo "Sessions: read this section instead of re-probing. Re-run: \`bash scripts/bin/env-smoke.sh --write-state\`"
    } >"$STATE"
    echo "→ created $STATE"
  fi
fi
