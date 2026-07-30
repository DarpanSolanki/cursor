#!/usr/bin/env bash
# Tiered ship loop: workspace validate | service build+health | money full ntest.
# Usage:
#   ship-loop-gate.sh --from-pending
#   ship-loop-gate.sh --api getLoanAccountOverviewDetails [--api ...]
#   ship-loop-gate.sh --from-pending --skip-gate
#   ship-loop-gate.sh --tier workspace|service|money
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"

if [[ "${RUN_GUARDED_ACTIVE:-}" != "1" ]]; then
  exec bash "$ROOT/scripts/bin/run-guarded.sh" --source ship-loop-gate.sh -- \
    env RUN_GUARDED_ACTIVE=1 bash "$0" "$@"
fi

PENDING="$ROOT/.cursor/.pending-ship-work.json"
PASSED="$ROOT/.cursor/.ship-loop-passed.json"
FROM_PENDING=0
SKIP_GATE=0
TIER=""
APIS=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    --from-pending) FROM_PENDING=1; shift ;;
    --skip-gate) SKIP_GATE=1; shift ;;
    --tier) TIER="$2"; shift 2 ;;
    --api) APIS+=("$2"); shift 2 ;;
    -h|--help)
      head -8 "$0" | tail -7
      exit 0
      ;;
    *) echo "Unknown arg: $1" >&2; exit 2 ;;
  esac
done

_read_pending() {
  python3 - <<'PY' "$PENDING"
import json, sys
from pathlib import Path
p = Path(sys.argv[1])
if not p.is_file():
    print(json.dumps({}))
    sys.exit(0)
print(p.read_text(encoding="utf-8"))
PY
}

PENDING_JSON="$(_read_pending)"

# Single Python call: tier, apis, ntest cases, repos
_IMPACT_JSON="$(python3 "$ROOT/scripts/lib/resolve_ship_impact.py" --json \
  --root "$ROOT" --pending "$PENDING" \
  ${TIER:+--tier "$TIER"} \
  $( [[ "$FROM_PENDING" -eq 1 ]] && echo --from-pending ) \
  $( for a in "${APIS[@]}"; do printf ' --api %q' "$a"; done ) 2>/dev/null || echo '{}')"

TIER="$(echo "$_IMPACT_JSON" | python3 -c "import json,sys; print(json.load(sys.stdin).get('tier') or 'workspace')" 2>/dev/null || echo workspace)"
mapfile -t APIS < <(echo "$_IMPACT_JSON" | python3 -c "import json,sys; [print(a) for a in json.load(sys.stdin).get('apis') or []]" 2>/dev/null || true)
mapfile -t _SMART_CASES < <(echo "$_IMPACT_JSON" | python3 -c "import json,sys; [print(c) for c in json.load(sys.stdin).get('ntest_cases') or []]" 2>/dev/null || true)
PENDING_FILES="$(echo "$_IMPACT_JSON" | python3 -c "import json,sys; print(json.load(sys.stdin).get('pending_files') or 0)" 2>/dev/null || echo 0)"
_TESTING_PATHS="$(echo "$_IMPACT_JSON" | python3 -c "import json,sys; print(json.load(sys.stdin).get('testing_paths_touched') or 0)" 2>/dev/null || echo 0)"

if [[ "$PENDING_FILES" -eq 0 && ${#APIS[@]} -eq 0 && "$FROM_PENDING" -eq 1 ]]; then
  echo "ship-loop-gate: no pending ship work — edit a ship-path file or pass --api / --tier" >&2
  exit 2
fi

echo "=== ship-loop-gate: tier=$TIER apis=${APIS[*]:-(none)} cases=${_SMART_CASES[*]:-(none)} files=$PENDING_FILES ==="

_SELECTION_SRC="$(echo "$_IMPACT_JSON" | python3 -c "import json,sys; print(json.load(sys.stdin).get('selection_source') or '?')" 2>/dev/null || echo '?')"
echo "→ selection source: $_SELECTION_SRC (${#_SMART_CASES[@]} case(s))"
if [[ ${#_SMART_CASES[@]} -gt 0 ]]; then
  echo "$_IMPACT_JSON" | python3 -c "
import json, sys
d = json.load(sys.stdin)
for cid in d.get('ntest_cases') or []:
    why = (d.get('case_why') or {}).get(cid, d.get('selection_source', ''))
    print(f'  PLAN {cid}: {why}')
"
fi
export SHIP_LOOP_CASES="${_SMART_CASES[*]:-}"
export RUN_GUARDED_CHAIN_STARTED="$(date +%s)"
if [[ ${#_SMART_CASES[@]} -gt 0 ]]; then
  export RUN_GUARDED_CHAIN_CEILING="$(python3 "$ROOT/scripts/lib/chain_budgets.py" ship-loop-total \
    $(for c in "${_SMART_CASES[@]}"; do printf ' --case %q' "$c"; done) 2>/dev/null || echo 5400)"
  # Live progress contract — init plan + budgets into .cursor/ship-progress.log
  python3 - <<'PY' "$ROOT" "${_SMART_CASES[@]}"
import sys
from pathlib import Path
root = Path(sys.argv[1])
sys.path.insert(0, str(root / "scripts/lib"))
from chain_budgets import case_wall_s, step_budget
from ship_progress import init_plan
cases = sys.argv[2:]
budgets = {c: step_budget("ntest-case", cases=[c]) for c in cases}
init_plan(cases, budgets)
print(f"→ ship-progress initialized n={len(cases)} ceiling={sum(budgets.values())}s (log=.cursor/ship-progress.log)")
PY
fi

# Stack hygiene before any tests (Phase D)
echo "→ stack-doctor (preflight)"
bash "$ROOT/scripts/bin/stack-doctor.sh" --remediate || {
  echo "ship-loop-gate: FAIL — stack-doctor (dirty stack)" >&2
  bash "$ROOT/scripts/bin/stack-doctor.sh" 2>&1 | tail -20 >&2 || true
  exit 1
}

# FIX2: park non-fixture dpiAccrualBooking eligible set for money/DPI suites
if [[ "$TIER" == "money" ]] || [[ "${_SMART_CASES[*]:-}" == *dpic.* ]]; then
  echo "→ suite booking quarantine (park)"
  bash "$ROOT/scripts/dpic/lib/suite_booking_quarantine.sh" park || true
  _suite_q_restore() { bash "$ROOT/scripts/dpic/lib/suite_booking_quarantine.sh" restore >/dev/null 2>&1 || true; }
  trap '_suite_q_restore' EXIT
fi

# Query plan gate — only when pending touches @Query/native SQL/repo methods (conditional).
if [[ "$FROM_PENDING" -eq 1 || "$PENDING_FILES" -gt 0 ]]; then
  if bash "$ROOT/scripts/bin/query-plan-gate.sh" --check-touched >/dev/null 2>&1; then
    echo "→ query-plan-gate: query_touched — running EXPLAIN heuristics"
    if ! bash "$ROOT/scripts/bin/query-plan-gate.sh" --from-pending; then
      echo "ship-loop-gate: FAIL — query-plan-gate (see .cursor/.query-plan-gate-result.json)" >&2
      exit 1
    fi
  else
    echo "→ query-plan-gate: SKIPPED (no query_touched)"
  fi
fi

# Impact-tests gate: service/money ships require impact record keyed to HEAD sha.
# Record is written at END of ship-loop after tests pass — never by workspace-close.
# Selection is NOT expanded from cache — impact_tests.build_plan is sole case list.
if [[ "$TIER" == "money" || "$TIER" == "service" ]]; then
  if python3 "$ROOT/scripts/lib/impact_tests.py" --check-ran >/dev/null 2>&1; then
    echo "→ impact-tests cache HIT: $(python3 "$ROOT/scripts/lib/impact_tests.py" --check-ran 2>/dev/null || true)"
  else
    echo "→ impact-tests cache MISS — will record after tests pass"
  fi
fi

# Fail-closed: money tier blocks on NOT-COVERED flows without human waiver.
if [[ "$TIER" == "money" ]]; then
  _PLAN_NC="$(python3 "$ROOT/scripts/lib/impact_tests.py" --json 2>/dev/null | python3 -c "
import json,sys
d=json.load(sys.stdin)
rows=d.get('not_covered_blocking')
if rows is None:
    rows=d.get('not_covered_flows') or []
for row in rows:
    print(row.get('api') or row.get('flow') or '?')
" 2>/dev/null || true)"
  if [[ -n "$_PLAN_NC" ]]; then
    _HUMAN_WAIVER=0
    python3 -c "
import json
from pathlib import Path
w=Path('$ROOT')/'.cursor/.impact-tests-human-waiver.json'
import sys
sys.exit(0 if w.is_file() and json.loads(w.read_text()).get('reason') else 1)
" 2>/dev/null && _HUMAN_WAIVER=1
    if [[ "$_HUMAN_WAIVER" -eq 0 ]]; then
      echo "ship-loop-gate: FAIL — money path NOT-COVERED flows (no registry case):" >&2
      while IFS= read -r api; do
        [[ -n "$api" ]] && echo "  NOT-COVERED flow ${api} impacted — NOT-COVERED" >&2
      done <<< "$_PLAN_NC"
      echo "  Add registry case or: bash scripts/bin/impact-tests.sh --human-waiver 'reason'" >&2
      exit 1
    fi
  fi
fi

# Fail-closed: money tier blocks when selected cases last-ran FAIL (telemetry RED).
if [[ "$TIER" == "money" && ${#_SMART_CASES[@]} -gt 0 ]]; then
  _RED="$(python3 -c "
import sys
sys.path.insert(0, '$ROOT/scripts/testing')
sys.path.insert(0, '$ROOT/scripts/lib')
from ntest_telemetry import red_cases
cases = '''${_SMART_CASES[*]}'''.split()
for row in red_cases(cases):
    print(f\"{row.get('case')}|{row.get('at')}|{row.get('duration_s')}\")
" 2>/dev/null || true)"
  if [[ -n "$_RED" ]]; then
    _RED_WAIVER=0
    python3 -c "
import json
from pathlib import Path
w=Path('$ROOT')/'.cursor/.impact-tests-human-waiver.json'
import sys
if not w.is_file():
    sys.exit(1)
d=json.loads(w.read_text())
sys.exit(0 if d.get('reason') and (d.get('allow_red_cases') or d.get('allow_telemetry_red')) else 1)
" 2>/dev/null && _RED_WAIVER=1
    if [[ "$_RED_WAIVER" -eq 0 ]]; then
      echo "ship-loop-gate: FAIL — selected cases RED (last ntest fail) — must-fix-first:" >&2
      while IFS= read -r row; do
        [[ -n "$row" ]] && echo "  RED $row" >&2
      done <<< "$_RED"
      echo "  Re-run green or waiver with allow_red_cases:true + reason" >&2
      exit 1
    fi
  fi
fi

# Fail-closed: money/service ships must resolve at least one impacted ntest case (or api→case).
# Health/smoke-only fallback for money is forbidden (compile-adjacent push).
if [[ "$TIER" == "money" ]]; then
  if [[ ${#_SMART_CASES[@]} -eq 0 ]]; then
    echo "ship-loop-gate: FAIL — money tier with zero ntest cases. Map path→registry (change_test_map.json / resolve_ship_cases) or pass --api." >&2
    exit 1
  fi
elif [[ "$TIER" == "service" ]]; then
  if [[ ${#_SMART_CASES[@]} -eq 0 && ${#APIS[@]} -eq 0 ]]; then
    # health fallback still allowed below — but only when repos map to health probes
    _HAS_HEALTH=$(echo "$PENDING_JSON" | python3 -c "
import json,sys
d=json.load(sys.stdin)
print(1 if (d.get('health_cases') or d.get('repos')) else 0)
" 2>/dev/null || echo 0)
    if [[ "$_HAS_HEALTH" != "1" ]]; then
      echo "ship-loop-gate: FAIL — service tier with no cases/apis/health repos." >&2
      exit 1
    fi
  fi
fi

# Batch write-skip contract: platform GenericListenerV3 vs job mappers must stay aligned
_BATCH_SKIP_MODE="$(echo "$PENDING_JSON" | python3 -c "
import json, sys
d = json.load(sys.stdin)
files = d.get('files') or []
mapper_files = [f for f in files if 'FailureEntityMapper' in f or 'DpiBatchWriterSkipItemSupport' in f]
infra_files = [f for f in files if any(t in f for t in (
    'infra-batch/', 'GenericListenerV3', 'BatchWriterSkipItemSupport'))]
dpi_dirs = ('batchnew/dpi/', 'DpiAccrual', 'DpiBilling')
if not mapper_files and not infra_files:
    print('skip')
    raise SystemExit
if mapper_files and all(any(m in f for m in dpi_dirs) for f in mapper_files):
    print('dpi-only')
else:
    print('full')
" 2>/dev/null || echo skip)"
# DPI money-tier ship: audit scope follows apis, not stale pending mapper fingerprints
if [[ "$_BATCH_SKIP_MODE" == "full" && ${#APIS[@]} -gt 0 ]]; then
  _all_dpi_apis=1
  for _a in "${APIS[@]}"; do
    case "$_a" in
      dpiAccrualCalculation|dpiAccrualBooking|dpiBilling) ;;
      *) _all_dpi_apis=0; break ;;
    esac
  done
  [[ "$_all_dpi_apis" -eq 1 ]] && _BATCH_SKIP_MODE="dpi-only"
fi
if [[ "$_BATCH_SKIP_MODE" != "skip" ]]; then
  echo "→ batch write-skip contract audit ($_BATCH_SKIP_MODE)"
  if [[ "$_BATCH_SKIP_MODE" == "dpi-only" ]]; then
    bash "$ROOT/scripts/bin/audit-batch-skip-mappers.sh" --dpi-only || exit 1
  else
    bash "$ROOT/scripts/bin/audit-batch-skip-mappers.sh" || exit 1
  fi
fi

_BRANCH_NOTE="$(python3 - <<'PY' "$ROOT"
import sys
from pathlib import Path
sys.path.insert(0, str(Path(sys.argv[1]) / "scripts/lib"))
from branch_topology import active_branch_mix_note
print(active_branch_mix_note() or "")
PY
)"
[[ -n "$_BRANCH_NOTE" ]] && echo "$_BRANCH_NOTE"

if [[ "$TIER" == "money" && "$PENDING_FILES" -gt 0 ]]; then
  _HPS="$(bash "$ROOT/scripts/bin/hot-path-scan.sh" --from-pending 2>/dev/null || true)"
  echo "$_HPS"
  if [[ "${HOT_PATH_SCAN_STRICT:-}" == "1" ]] && [[ "$_HPS" == *"WARN:"* ]]; then
    echo "ship-loop-gate: hot-path-scan STRICT — fix DAO-in-loop or document false positive" >&2
    exit 1
  fi
  echo "→ java-comment-lint (DPI pending)"
  bash "$ROOT/scripts/bin/java-comment-lint.sh" --from-pending || exit 1
fi

if [[ ${#_SMART_CASES[@]} -gt 0 ]]; then
  _IMPACT_SCOPED="$(echo "$_IMPACT_JSON" | python3 -c "import json,sys; d=json.load(sys.stdin); print('yes' if d.get('impact_scoped') or d.get('dpi_scoped') else 'no')" 2>/dev/null || echo no)"
  echo "→ smart ntest (impact-scoped=${_IMPACT_SCOPED}): ${_SMART_CASES[*]}"
fi
[[ ${#APIS[@]} -gt 0 ]] && echo "→ KG-resolved apis: ${APIS[*]}"

_run_ntest() {
  local case_id="$1"
  local label="${2:-}"
  local budget idx n start_ts end_ts rc el phases_json
  budget="$(python3 "$ROOT/scripts/lib/chain_budgets.py" ntest-case --case "$case_id" 2>/dev/null || echo 300)"
  n="${#_SMART_CASES[@]}"
  idx=0
  local i c
  for i in "${!_SMART_CASES[@]}"; do
    c="${_SMART_CASES[$i]}"
    [[ "$c" == "$case_id" ]] && idx=$((i + 1)) && break
  done
  [[ "$idx" -eq 0 ]] && idx=1
  python3 "$ROOT/scripts/lib/ship_progress.py" start "$idx" "$n" "$case_id" "$budget"
  start_ts=$(date +%s)
  # Phase: fire+flow (ntest owns fixture/fire/wait/asserts — heartbeat while silent)
  python3 "$ROOT/scripts/lib/ship_progress.py" phase "$idx" "$n" "$case_id" "fire+flow" "ntest run"
  set +e
  if command -v timeout >/dev/null 2>&1; then
    (
      bash "$ROOT/scripts/bin/ntest.sh" run "$case_id"
    ) &
    local child=$!
    local last_hb=$start_ts now
    while kill -0 "$child" 2>/dev/null; do
      sleep 1
      now=$(date +%s)
      el=$((now - start_ts))
      if [[ $((now - last_hb)) -ge 15 ]]; then
        python3 "$ROOT/scripts/lib/ship_progress.py" hb "$idx" "$n" "$case_id" "$el" "$budget" "ntest${label:+ /$label}"
        last_hb=$now
      fi
      if [[ "$el" -ge "$budget" ]]; then
        kill -TERM "$child" 2>/dev/null || true
        sleep 5
        kill -KILL "$child" 2>/dev/null || true
        wait "$child" 2>/dev/null || true
        python3 "$ROOT/scripts/lib/ship_progress.py" end "$idx" "$n" "$case_id" FAIL "$el" '{}'
        set -e
        return 1
      fi
    done
    wait "$child"
    rc=$?
  else
    bash "$ROOT/scripts/bin/ntest.sh" run "$case_id"
    rc=$?
  fi
  set -e
  end_ts=$(date +%s)
  el=$((end_ts - start_ts))
  phases_json="$(python3 -c "import json; print(json.dumps({'fire_flow_ms': ${el} * 1000}))")"
  if [[ "$rc" -eq 0 ]]; then
    python3 "$ROOT/scripts/lib/ship_progress.py" end "$idx" "$n" "$case_id" PASS "$el" "$phases_json"
  else
    python3 "$ROOT/scripts/lib/ship_progress.py" end "$idx" "$n" "$case_id" FAIL "$el" "$phases_json"
    return 1
  fi
}

_run_api_tests() {
  local api
  local ops_fail_ok=1
  [[ "$TIER" == "money" ]] && ops_fail_ok=0
  for api in "${APIS[@]}"; do
    echo "→ agent-ops before-test $api"
    if ! bash "$ROOT/scripts/bin/agent-ops.sh" before-test "$api"; then
      [[ "$ops_fail_ok" -eq 0 ]] && return 1
    fi
    local case_id
    case_id="$(python3 "$ROOT/scripts/lib/infer_ship_apis.py" --registry-case "$api" 2>/dev/null || true)"
    if [[ -n "$case_id" ]]; then
      _run_ntest "$case_id" "api=$api" || return 1
    else
      echo "→ ntest auto $api"
      bash "$ROOT/scripts/bin/ntest.sh" auto "$api" || return 1
    fi
  done
}

_run_smart_cases() {
  local case_id
  for case_id in "${_SMART_CASES[@]}"; do
    [[ -n "$case_id" ]] || continue
    _run_ntest "$case_id" "flow-scoped" || return 1
  done
}

_build_repos() {
  mapfile -t REPOS < <(echo "$PENDING_JSON" | python3 -c "
import json, sys
from pathlib import Path
root = Path('$ROOT')
d = json.loads(sys.stdin.read() or '{}')
repos = set(d.get('repos') or [])
for r in repos:
    if (root / r / 'build.gradle').is_file() or (root / r / 'build.gradle.kts').is_file():
        print(r)
" 2>/dev/null)
  if [[ ${#REPOS[@]} -eq 0 && ${#APIS[@]} -gt 0 ]]; then
    REPOS=("trustt-platform-accounting")
  fi
  local repo
  for repo in "${REPOS[@]}"; do
    local rdir="$ROOT/$repo"
    [[ -d "$rdir" ]] || continue
    echo "→ gradlew build -x test ($repo)"
    (cd "$rdir" && ./gradlew build -x test -q) || return 1
  done
}

_run_case_list() {
  local tier_label="$1"
  shift
  local case_id already
  for case_id in "$@"; do
    [[ -n "$case_id" ]] || continue
    already=0
    for api in "${APIS[@]}"; do
      local mapped
      mapped="$(python3 "$ROOT/scripts/lib/infer_ship_apis.py" --registry-case "$api" 2>/dev/null || true)"
      [[ "$mapped" == "$case_id" ]] && already=1 && break
    done
    [[ "$already" -eq 1 ]] && continue
    _run_ntest "$case_id" "$tier_label" || return 1
  done
}

case "$TIER" in
  workspace)
    echo "→ workspace tier: KG + registry validate"
    if [[ "${WORKSPACE_CLOSE_KG_DONE:-}" != "1" ]]; then
      python3 "$ROOT/cursor-bundle/kg/bin/kg.py" validate >/dev/null
    else
      echo "→ kg validate skipped (already done in workspace-close)"
    fi
    python3 "$ROOT/scripts/testing/ntest.py" validate
    if [[ -x "$ROOT/scripts/bin/kg-mcp-smoke.sh" ]]; then
      echo "→ kg-mcp-smoke (trustt-kg MCP stdio)"
      bash "$ROOT/scripts/bin/kg-mcp-smoke.sh" || exit 1
    fi
    if [[ ${#_SMART_CASES[@]} -gt 0 ]]; then
      mapfile -t _WS_CASES < <(python3 - <<'PY' "$ROOT" "${_SMART_CASES[@]}"
import json, sys
from pathlib import Path
root = Path(sys.argv[1])
reg = json.loads((root / "scripts/testing/registry.json").read_text(encoding="utf-8"))
for cid in sys.argv[2:]:
    if (reg.get(cid) or {}).get("smoke_tier") == "money":
        continue
    print(cid)
PY
)
      if [[ ${#_WS_CASES[@]} -gt 0 ]]; then
        echo "→ workspace tier: flow-scoped ntest (${#_WS_CASES[@]} case(s))"
        _run_case_list "flow-scoped" "${_WS_CASES[@]}" || exit 1
      fi
    elif [[ "$_TESTING_PATHS" == "1" ]]; then
      echo "→ testing paths touched — workspace tier smoke"
      bash "$ROOT/scripts/bin/ntest.sh" smoke --tier workspace || exit 1
    fi
    if [[ -x "$ROOT/scripts/bin/ops-bin-hygiene.sh" ]]; then
      echo "→ ops bin hygiene"
      bash "$ROOT/scripts/bin/ops-bin-hygiene.sh" || exit 1
    fi
    echo "→ acceptance ratchet + money verify_mode"
    python3 "$ROOT/scripts/lib/registry_proposals.py" check || exit 1
    ;;
  service)
    echo "→ ntest validate (service tier)"
    python3 "$ROOT/scripts/testing/ntest.py" validate || exit 1
    _build_repos || exit 1
    if [[ ${#_SMART_CASES[@]} -gt 0 ]]; then
      _run_smart_cases || exit 1
    elif [[ ${#APIS[@]} -gt 0 ]]; then
      _run_api_tests || exit 1
    else
      mapfile -t _HEALTH < <(echo "$PENDING_JSON" | python3 -c "
import json,sys
d=json.load(sys.stdin)
seen=set()
for c in d.get('health_cases') or []:
    if c not in seen:
        seen.add(c); print(c)
repos=d.get('repos') or []
svc_map={'trustt-platform-accounting':'health.accounting','trustt-platform-actor':'health.actor','trustt-platform-task':'health.task','trustt-platform-payments':'health.payments'}
for r in repos:
    h=svc_map.get(r)
    if h and h not in seen:
        seen.add(h); print(h)
" 2>/dev/null)
      if [[ ${#_HEALTH[@]} -gt 0 ]]; then
        echo "→ service tier: health probe(s) for touched repo(s)"
        _run_case_list "health" "${_HEALTH[@]}" || exit 1
      else
        echo "→ service tier: quick smoke (no flow resolved)"
        bash "$ROOT/scripts/bin/ntest.sh" smoke --quick || exit 1
      fi
    fi
    ;;
  money)
    echo "→ ntest validate (money tier)"
    python3 "$ROOT/scripts/testing/ntest.py" validate || exit 1
    _build_repos || exit 1
    if [[ ${#_SMART_CASES[@]} -gt 0 ]]; then
      _run_smart_cases || exit 1
    elif [[ ${#APIS[@]} -gt 0 ]]; then
      _run_api_tests || exit 1
    else
      echo "ship-loop-gate: FAIL — money tier empty cases/apis (no health/smoke fallback)" >&2
      exit 1
    fi
    ;;
  *)
    echo "Unknown tier: $TIER" >&2
    exit 2
    ;;
esac

if [[ -f "$ROOT/.cursor/.pending-kg-rebuild" ]]; then
  echo "→ reminder: cursor-bundle/kg/bin/changelog-add.sh --kg-flow + .cursor/changelog.md"
fi

# Hard discipline (minimal fix · hot-path · verify_mode · KG · no bare assumptions)
if [[ "$TIER" == "money" || "$TIER" == "service" ]]; then
  echo "→ ship-discipline check ($TIER)"
  python3 "$ROOT/scripts/lib/ship_discipline_gate.py" check || exit 1
  echo "→ acceptance-coverage check ($TIER)"
  python3 "$ROOT/scripts/lib/acceptance_coverage.py" check --from-pending || exit 1
fi

if [[ "$SKIP_GATE" -eq 0 && "${SHIP_LOOP_SKIP_KNOWLEDGE_GATE:-}" != "1" ]]; then
  profile="$(python3 "$ROOT/scripts/lib/ship_push_gate.py" --close-profile 2>/dev/null || echo minimal)"
  echo "→ ship-knowledge-gate.sh --profile $profile"
  bash "$ROOT/scripts/bin/ship-knowledge-gate.sh" --profile "$profile" || exit 1
fi

python3 - <<'PY' "$ROOT" "$TIER" "${APIS[@]}"
import json, sys, datetime
from pathlib import Path

sys.path.insert(0, str(Path(sys.argv[1]) / "scripts/lib"))
from ship_fingerprint import load_pending, repo_head_shas
from ship_push_lock import update_pending_ship
from ship_outbox import record_gate_passed, log_outbox_error
from impact_tests import build_plan, mark_ran

root = Path(sys.argv[1])
tier = sys.argv[2]
apis = sys.argv[3:]
now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
pending = load_pending()
head_shas = repo_head_shas(pending)
passed = {
    "passed_at": now,
    "tier": tier,
    "apis": apis,
    "repos": pending.get("repos") or [],
    "repo_head_shas": head_shas,
}
p = root / ".cursor/.pending-ship-work.json"
if p.is_file():
    try:
        pend = json.loads(p.read_text(encoding="utf-8"))
        passed["repos"] = pend.get("repos") or passed["repos"]
        passed["tier"] = pend.get("tier") or tier

        def _mark_passed(data: dict) -> dict:
            data["ship_loop_passed_at"] = now
            return data

        update_pending_ship(root, _mark_passed, pending_path=p)
    except Exception:
        pass
if tier in ("money", "service"):
    plan = build_plan(from_pending=True, draft_stubs=False)
    mark_ran(plan, result="pass")
try:
    record_gate_passed(
        tier=passed.get("tier") or tier,
        apis=list(passed.get("apis") or apis),
        extra={"repos": passed.get("repos") or [], "repo_head_shas": head_shas},
    )
except Exception as ex:
    log_outbox_error(ex, "record_gate_passed")
(root / ".cursor/.ship-loop-passed.json").write_text(
    json.dumps(passed, indent=2) + "\n", encoding="utf-8"
)
(root / ".cursor/.pending-ship-nudge").unlink(missing_ok=True)
import os
if os.environ.get("SHIP_LOOP_SKIP_KNOWLEDGE_GATE") != "1":
    p.unlink(missing_ok=True)
label = ", ".join(apis) if apis else f"tier={tier}"
print(f"ship-loop PASS at {now} ({label}) head_shas={head_shas}")
PY

echo "=== ship-loop-gate: PASS ==="
# Auto-draft regression pin for money/service ships (human promotes)
if [[ "$TIER" == "money" || "$TIER" == "service" ]]; then
  python3 "$ROOT/scripts/lib/registry_proposals.py" draft --force 2>/dev/null | head -20 || true
fi
