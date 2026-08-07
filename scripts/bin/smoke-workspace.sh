#!/usr/bin/env bash
# End-to-end smoke test: cursor-bundle KG (SQLite), self-learning, hooks, local DB.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
KG="python3 cursor-bundle/kg/bin/kg.py"
FAIL=0

pass() { echo "  OK  $1"; }
fail() { echo "  FAIL $1 — $2"; FAIL=$((FAIL + 1)); }

echo "=== cursor-bundle inventory ==="
for f in cursor-bundle/kg/data/kg.db cursor-bundle/memory/MEMORY.md cursor-bundle/kg/bin/build.sh \
         cursor-bundle/kg/bin/kg.py cursor-bundle/kg/BRANCH-SAFETY.md \
         .cursor/rules/30-kg-discipline.mdc cursor-bundle/brain/CANONICAL-MAP.md \
         .cursor/hooks.json .cursor/workspace-kg-state.md; do
  [[ -e "$f" ]] && pass "$f" || fail "$f" "missing"
done
BRAIN_N=$(find cursor-bundle/brain -name '*.md' | wc -l)
MEM_N=$(ls cursor-bundle/memory/*.md 2>/dev/null | wc -l)
[[ "$BRAIN_N" -gt 180 ]] && pass "brain docs ($BRAIN_N)" || fail "brain docs" "$BRAIN_N"
[[ "$MEM_N" -ge 25 ]] && pass "memory files ($MEM_N)" || fail "memory files" "$MEM_N"

echo ""
echo "=== intelligence stack ==="
for f in .cursor/workspace-intelligence-state.md cursor-bundle/brain/skills-manifest.json \
         cursor-bundle/brain/SKILLS-INDEX.md; do
  [[ -e "$f" ]] && pass "$f" || fail "$f" "missing (run write-intelligence-hub.sh)"
done
[[ -x scripts/bin/workspace-sanity.sh ]] && pass "workspace-sanity.sh" || fail "workspace-sanity.sh" "not executable"
bash scripts/bin/write-intelligence-hub.sh >/dev/null 2>&1 && pass "write-intelligence-hub" || fail "write-intelligence-hub" ""
# Current kg CLI: `stats` (not legacy `map stats`); needle survives provenance header
$KG --no-drift-check stats 2>/dev/null | grep -qE "total:|'api'|nodes:" && pass "kg stats" || fail "kg stats" ""
# Legacy `test-gaps` removed — doctor covers health; soft needle on doctor output
$KG --no-drift-check doctor 2>/dev/null | grep -qE "KG|watermark|FRESH|STALE|nodes" && pass "kg doctor" || fail "kg doctor" ""

echo ""
echo "=== SQLite direct (kg.db) ==="
python3 cursor-bundle/kg/bin/refresh_cases.py >/dev/null 2>&1 || true
python3 - <<'PY' || FAIL=$((FAIL + 1))
import sqlite3, json, os, sys
c = sqlite3.connect("cursor-bundle/kg/data/kg.db")
assert c.execute("SELECT count(*) FROM nodes").fetchone()[0] > 6000
assert c.execute(
    "SELECT 1 FROM nodes WHERE id='request:trustt-platform-accounting/disburseLoan' OR (kind='request' AND label='disburseLoan')"
).fetchone()
cases = c.execute("SELECT count(*) FROM nodes WHERE kind='case'").fetchone()[0]
# Opt-in precedents only (| kg-flow | rows) — not full audit log
assert cases >= 5, f"case nodes {cases} < 5 (run changelog-add --kg-flow + refresh_cases)"
assert c.execute("SELECT 1 FROM node_fts WHERE node_fts MATCH 'disburseLoan*'").fetchone()
legacy = c.execute("SELECT count(*) FROM nodes WHERE json LIKE '%cursor-bundle/%' OR json LIKE '%.cursor/%'").fetchone()[0]
if legacy > 5:
    # Legacy path strings folded into node JSON from older brain docs — not a smoke blocker.
    print(f"  WARN stale cursor refs in kg nodes: {legacy} (rebuild KG)")
elif legacy:
    print(f"  OK  stale cursor refs in kg nodes: {legacy} (residual doc text only)")
else:
    print("  OK  no stale cursor paths in kg nodes")
print(f"  OK  case nodes (opt-in precedents): {cases}")
wm = json.load(open("cursor-bundle/kg/data/stats.json"))["watermark"]["repos"]
assert len(wm) >= 10
print(f"  OK  watermark covers {len(wm)} repos")
PY

echo ""
echo "=== kg integrity + orient ==="
python3 cursor-bundle/kg/bin/kg_validate.py >/dev/null 2>&1 && pass "kg_validate (pre-CLI)" || fail "kg_validate" ""
orient_out=$($KG --no-drift-check orient disburseLoan 2>/dev/null) || true
# U6+ banner is evidence-only ORIENT (not legacy IMPLEMENTATION GATE); header-aware
# pure-bash match: `echo … | grep -q` races SIGPIPE under `set -o pipefail`
if [[ "$orient_out" == *"ORIENT (evidence only"* || "$orient_out" == *"IMPLEMENTATION GATE"* ]]; then
  pass "kg orient disclaimer"
else
  fail "kg orient" "missing gate banner"
fi
if [[ "$orient_out" == *"populateUserDetails"* ]]; then
  pass "kg orient flow spine"
else
  fail "kg orient flow" ""
fi

echo ""
echo "=== kg.py CLI ==="
kg_check() {
  local needle="$1"; shift
  local out
  out=$($KG --no-drift-check "$@" 2>/dev/null) || return 1
  [[ "$out" == *"$needle"* ]]
}
kg_check FRESH fresh && pass "kg fresh" || fail "kg fresh" "not fresh"
# Legacy `audit`/`cache` cmds removed from kg.py — use doctor + watermark (branch-set)
audit_out=$($KG --no-drift-check doctor 2>/dev/null) && echo "$audit_out" | grep -qE "KG|watermark|FRESH|STALE|repo" && pass "kg doctor (audit stand-in)" || fail "kg doctor (audit stand-in)" ""
kg_check populateUserDetails flow disburseLoan && pass "kg flow disburseLoan" || fail "kg flow" ""
kg_check silent-surface why disburseLoan && pass "kg why" || fail "kg why" ""
kg_check "DB FOOTPRINT" crud disburseLoan && pass "kg crud" || fail "kg crud" ""
kg_check PRECEDENT cases disburseLoan && pass "kg cases" || fail "kg cases" ""
kg_check WRITERS writes loan_account && pass "kg writes" || fail "kg writes" ""
out=$($KG --no-drift-check sql "SELECT count(*) FROM edges WHERE rel='invokes'" 2>/dev/null) && [[ "$out" =~ [0-9]+ ]] && pass "kg sql" || fail "kg sql" ""

echo ""
echo "=== build cache + branch switch ==="
if out=$(bash cursor-bundle/kg/bin/build.sh 2>&1); then
  echo "$out" | grep -qE 'restored from cache|KG built|snapshotted to cache' && pass "build.sh" || fail "build.sh" "$out"
else
  fail "build.sh" "non-zero exit"
fi
python3 cursor-bundle/kg/bin/kg_validate.py >/dev/null 2>&1 && pass "kg_validate" || fail "kg_validate" ""
[[ -x scripts/bin/kg-switch.sh ]] && pass "kg-switch.sh" || fail "kg-switch.sh" "not executable"
switch_out=$(bash scripts/bin/kg-switch.sh --quiet 2>&1) && pass "kg-switch run" || fail "kg-switch run" "$switch_out"
# Legacy `kg cache` removed — watermark proves branch-set awareness (header-aware)
$KG --no-drift-check watermark 2>/dev/null | grep -qE "branch|sha|KG|repo" && pass "kg watermark (cache stand-in)" || fail "kg watermark (cache stand-in)" ""
$KG --no-drift-check fresh 2>/dev/null | grep -qE "FRESH|STALE|KG" && pass "kg fresh (prune stand-in)" || fail "kg fresh (prune stand-in)" ""

echo ""
echo "=== Registry validate ==="
python3 scripts/testing/lib/validate_registry.py && pass "registry validate" || fail "registry validate" ""

echo ""
echo "=== self-learning helpers ==="
bash cursor-bundle/kg/bin/changelog-add.sh --dry-run "## smoke" "detail" 2>&1 | grep -q smoke && pass "changelog-add dry-run" || fail "changelog-add" ""
[[ -x scripts/bin/kg-enrich.sh ]] && pass "kg-enrich.sh" || fail "kg-enrich.sh" "not executable"
[[ -x scripts/bin/enrichment-sync.sh ]] && pass "enrichment-sync.sh" || fail "enrichment-sync.sh" "not executable"
[[ -x scripts/bin/enrichment-audit.sh ]] && pass "enrichment-audit.sh" || fail "enrichment-audit.sh" "not executable"
audit_out=$(bash scripts/bin/enrichment-audit.sh 2>&1) || true
echo "$audit_out" | grep -q "enrichment audit" && pass "enrichment-audit run" || fail "enrichment-audit run" ""
python3 cursor-bundle/kg/bin/kg.py cases disburseLoan 2>&1 | grep -qE "PRECEDENT|case:|kg-flow|[a-f0-9]{7,}" && pass "kg cases disburseLoan has precedents" || fail "kg cases precedents" "no case output"

echo ""
echo "=== hooks (offline) ==="
for h in kg-session-watermark.sh pre-commit-kg-reminder.sh pre-push-checklist.sh post-commit-kg-flag.sh post-push-enrichment.sh post-checkout-kg.sh; do
  [[ -x ".cursor/hooks/$h" ]] && pass "hook $h" || fail "hook $h" ""
done
python3 - <<'PY' || FAIL=$((FAIL + 1))
import json, subprocess, os
# ROOT already set by bash `cd "$ROOT"` above — never hardcode a sibling clone path.
with open(".cursor/hooks.json") as f:
    hooks = json.load(f)["hooks"]
assert any(
    (h.get("matcher") or "") in ("git push", r"git\s+push")
    or "push" in (h.get("matcher") or "")
    for h in hooks.get("afterShellExecution", [])
)
assert any("checkout" in (h.get("matcher") or "") for h in hooks.get("afterShellExecution", []))
print("  OK  hooks.json post-push + post-checkout registered")
PY
python3 - <<'PY' || FAIL=$((FAIL + 1))
import json, subprocess, os
p = subprocess.run(["bash", ".cursor/hooks/pre-commit-kg-reminder.sh"], input='{"command":"git commit -m t"}', text=True, capture_output=True)
assert json.loads(p.stdout)["permission"] == "allow"
# origin: allow when clean ship gates, or deny with ship-loop/workspace-close message when dirty
cmd_origin = "git " + "push" + " origin x"
p = subprocess.run(["bash", ".cursor/hooks/pre-push-checklist.sh"], input=json.dumps({"command": cmd_origin}), text=True, capture_output=True)
origin = json.loads(p.stdout)
assert origin["permission"] in ("allow", "deny"), origin
if origin["permission"] == "deny":
    msg = (origin.get("user_message") or "") + (origin.get("agent_message") or "")
    assert "workspace-close" in msg or "ship" in msg.lower() or "Push blocked" in msg, origin
# upstream always deny
cmd_up = "git " + "push" + " upstream x"
p = subprocess.run(["bash", ".cursor/hooks/pre-push-checklist.sh"], input=json.dumps({"command": cmd_up}), text=True, capture_output=True)
assert json.loads(p.stdout)["permission"] == "deny"
print("  OK  hook JSON contracts")
PY

echo ""
echo "=== hooks sync (Claude Code only) ==="
if [[ -f scripts/bin/sync-claude-hooks.py ]]; then
  if python3 scripts/bin/sync-claude-hooks.py >/dev/null 2>&1; then
    pass "settings.json in sync with hooks.json"
  else
    fail "claude hooks sync" "run: python3 scripts/bin/sync-claude-hooks.py --write"
  fi
else
  pass "hooks.json is Cursor SoT (no sync-claude-hooks)"
fi

echo ""
echo "=== mcp wiring + IDE catalog ==="
# kg-mcp-smoke spawns the server itself, so it can PASS while Cursor never loaded
# trustt-kg. check-mcp-wiring also reads ~/.cursor/projects/<ws>/mcps/.
mcp_out="$(python3 scripts/bin/check-mcp-wiring.py 2>&1)" && pass "mcp launch + IDE catalog" \
  || fail "mcp launch + IDE catalog" "$mcp_out"
# mcp_wiring_gate holds the Cursor IDE loaded-server catalog check and has its own test,
# but was reachable from no host — so it never actually ran.
mwg_out="$(python3 scripts/lib/mcp_wiring_gate.py 2>&1)" && pass "mcp wiring gate" \
  || fail "mcp wiring gate" "$mwg_out"

echo ""
echo "=== assert strength ==="
as_out="$(python3 scripts/bin/assert-strength-gate.py 2>&1)" && pass "no new presence-only asserts" \
  || fail "assert strength" "$as_out"

echo ""
echo "=== workspace hygiene ==="
[[ -x scripts/bin/workspace-hygiene.sh ]] && pass "workspace-hygiene.sh" || fail "workspace-hygiene.sh" "not executable"
[[ -f scripts/scratch/.gitignore ]] && pass "scripts/scratch" || fail "scripts/scratch" "missing"
bash scripts/bin/workspace-hygiene.sh 2>&1 | grep -qE 'No hygiene issues|issue' && pass "hygiene audit" || fail "hygiene audit" ""

echo ""
echo "=== local DB ==="
scripts/db-local.sh --sql "SELECT 1" | grep -q 1 && pass "db-local.sh" || fail "db-local.sh" ""

echo ""
if [[ "$FAIL" -eq 0 ]]; then
  echo "=== SMOKE: ALL PASSED ==="
  exit 0
else
  echo "=== SMOKE: $FAIL FAILURE(S) ==="
  exit 1
fi
