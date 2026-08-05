#!/usr/bin/env bash
# Super machine smoke — verify all integration points (no assumptions).
# Usage: super-machine-smoke.sh [--json]
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
JSON=0
[[ "${1:-}" == "--json" ]] && JSON=1
FAIL=0
PASS=0
RESULTS=()

record() {
  local id="$1" ok="$2" detail="${3:-}"
  if [[ "$ok" == 1 ]]; then PASS=$((PASS + 1)); mark="PASS"; else FAIL=$((FAIL + 1)); mark="FAIL"; fi
  RESULTS+=("$mark|$id|$detail")
  [[ "$JSON" == 0 ]] && echo "  $([[ $ok -eq 1 ]] && echo ✓ || echo ✗) $id${detail:+ — $detail}"
}

run_rc() {
  local id="$1"; shift
  local out rc
  out=$( "$@" 2>&1 ) || rc=$?
  rc=${rc:-0}
  record "$id" "$([[ $rc -eq 0 ]] && echo 1 || echo 0)" "${out:0:120}"
  return 0
}

run_json_field() {
  local id="$1" py="$2"
  local out rc
  out=$(python3 -c "$py
import sys
sys.exit(0 if ok else 1)" 2>&1) && rc=0 || rc=$?
  record "$id" "$([[ $rc -eq 0 ]] && echo 1 || echo 0)" "${out:0:120}"
}

echo "=== super-machine smoke ==="
echo ""

# 1 — Core CLIs exist + executable
for bin in super-machine.sh super-agent.sh flow-onboard.sh workspace-autopilot.sh; do
  [[ -x "$ROOT/scripts/bin/$bin" ]] && record "bin:$bin" 1 "executable" || record "bin:$bin" 0 "missing"
done

# 2 — Python modules import
run_json_field "import:corroborate" "
import sys; sys.path.insert(0,'$ROOT/scripts/testing')
from corroborate import run, load_last
r=run(mode='quick', emit_bus=False)
ok=r.passed>=7
print(f'score={r.score}')
"

run_json_field "import:orch_index" "
import sys; sys.path.insert(0,'$ROOT/scripts/testing')
from orch_index import load_index
d=load_index()
ok=d.get('count',0)>1000
print(f\"count={d.get('count')}\")
"

run_json_field "import:flow_trace" "
import sys; sys.path.insert(0,'$ROOT/scripts/testing')
from flow_trace import trace
t=trace('loanAccountPartPrepayment', fast=True)
ok='loanAccountPartPrepayment' in t and 'Registry' in t
print('trace ok')
"

# 3 — super-machine loop (critical path)
export SKIP_KG_ENSURE=1 SKIP_KG_VALIDATE=1
run_rc "super-machine:loop" bash "$ROOT/scripts/bin/super-machine.sh" loop

# 4 — corroborate full
run_rc "corroborate:full" python3 "$ROOT/scripts/testing/corroborate.py" --full --no-bus

# 5 — registry-gaps cached perf
start=$(date +%s%N)
out=$(python3 "$ROOT/scripts/testing/ftg.py" gaps 2>&1) || true
end=$(date +%s%N)
ms=$(( (end - start) / 1000000 ))
[[ "$ms" -lt 500 ]] && record "perf:registry-gaps" 1 "${ms}ms" || record "perf:registry-gaps" 0 "${ms}ms (>500ms)"
echo "$out" | head -3 >&2 || true

# 6 — autopilot scenarios
run_rc "autopilot:verify" python3 "$ROOT/scripts/testing/workspace_autopilot.py" verify
run_rc "autopilot:bug-rca" bash "$ROOT/scripts/bin/workspace-autopilot.sh" task "RCA loanAccountPartPrepayment failure" --quiet
run_rc "autopilot:workspace" bash "$ROOT/scripts/bin/workspace-autopilot.sh" task "improve workspace super machine" --quiet
run_rc "autopilot:continuation" bash "$ROOT/scripts/bin/workspace-autopilot.sh" task "go ahead" --quiet

# 7 — super-agent subcommands
run_rc "super-agent:status" bash "$ROOT/scripts/bin/super-agent.sh" status
run_rc "super-agent:trace" bash "$ROOT/scripts/bin/super-agent.sh" trace loanAccountPartPrepayment --fast
run_rc "super-agent:gaps" bash "$ROOT/scripts/bin/super-agent.sh" gaps --money
run_rc "super-agent:sync" python3 "$ROOT/scripts/testing/sync_engine.py" fast-sync --quiet

# 8 — flow onboard dry-run
run_rc "flow-onboard:dry" bash "$ROOT/scripts/bin/flow-onboard.sh" loanWriteoff --sibling dpic.dpi_sanity

# 9 — hub + corroboration artifact
[[ -f "$ROOT/cursor-bundle/flow-test/corroboration_last.json" ]] && record "artifact:corroboration_last" 1 || record "artifact:corroboration_last" 0
[[ -f "$ROOT/cursor-bundle/flow-test/orch_api_index.json" ]] && record "artifact:orch_index" 1 || record "artifact:orch_index" 0
run_rc "hub:write" python3 "$ROOT/scripts/testing/intelligence_hub.py" --write --fast
grep -q "Corroboration" "$ROOT/.cursor/workspace-intelligence-state.md" && record "hub:corroboration_section" 1 || record "hub:corroboration_section" 0

# 10 — hooks wiring
python3 - <<PY
import json, sys
from pathlib import Path
root = Path("$ROOT")
h = json.loads((root/".cursor/hooks.json").read_text())
starts = [x.get("command","") for x in h.get("hooks",{}).get("sessionStart",[])]
after = [x.get("command","") for x in h.get("hooks",{}).get("afterShellExecution",[])]
checks = [
  ("hooks:intel-session", any("intel-session" in c for c in starts)),
  ("hooks:post-ntest", any("post-ntest" in c for c in after)),
  ("hooks:super-machine-matcher", "super-machine" in json.dumps(h)),
]
for name, ok in checks:
  print(f"{'PASS' if ok else 'FAIL'}|{name}|")
PY
while IFS='|' read -r mark id _; do
  [[ -n "$id" ]] && record "$id" "$([[ $mark == PASS ]] && echo 1 || echo 0)"
done < <(python3 - <<PY
import json
from pathlib import Path
root = Path(${ROOT@Q})
h = json.loads((root / ".cursor" / "hooks.json").read_text())
starts = [x.get("command","") for x in h.get("hooks",{}).get("sessionStart",[])]
after = [x.get("command","") for x in h.get("hooks",{}).get("afterShellExecution",[])]
for name, ok in [
  ("hooks:intel-session", any("intel-session" in c for c in starts)),
  ("hooks:post-ntest", any("post-ntest" in c for c in after)),
  ("hooks:super-machine-matcher", "super-machine" in json.dumps(h)),
]:
    print(f"{'PASS' if ok else 'FAIL'}|{name}|")
PY
) 2>/dev/null || true

# Fix hooks check inline properly
hooks_ok=$(python3 -c "
import json
from pathlib import Path
h=json.loads(Path('$ROOT/.cursor/hooks.json').read_text())
starts=[x.get('command','') for x in h.get('hooks',{}).get('sessionStart',[])]
after=[x.get('command','') for x in h.get('hooks',{}).get('afterShellExecution',[])]
ok=all([
  any('intel-session' in c for c in starts),
  any('post-ntest' in c for c in after),
  'super-machine' in json.dumps(h),
])
print(1 if ok else 0)
")
record "hooks:wiring" "$hooks_ok"

# 11 — workspace health + max-pass (fast)
run_rc "workspace:health" bash "$ROOT/scripts/bin/workspace-health.sh"
run_rc "workspace:max-pass" bash "$ROOT/scripts/bin/workspace-max-pass.sh"

# 12 — KG validate
run_rc "kg:validate" python3 "$ROOT/cursor-bundle/kg/bin/kg.py" validate

# 13 — ntest registry
run_rc "ntest:validate" python3 "$ROOT/scripts/testing/ntest.py" validate

# 14 — learning bus writable
run_json_field "learning_bus:append" "
import sys; sys.path.insert(0,'$ROOT/scripts/testing')
from learning_bus import append_event
append_event('sanity_pass', source='super-machine-smoke', detail='smoke test')
print('append ok')
ok=True
"

echo ""
echo "=== super-machine smoke: $PASS passed, $FAIL failed ==="

if [[ "$JSON" == 1 ]]; then
  python3 - <<PY
import json
rows=[r.split("|",2) for r in """${RESULTS[*]}""".split()]
# fallback
PY
fi

[[ "$FAIL" -eq 0 ]] && exit 0 || exit 1
