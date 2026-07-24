#!/usr/bin/env bash
# Tiered KG enrichment — rebuild only when the graph must change.
#
# Tiers (see .cursor/rules/20-ship-gates.mdc):
#   full   — orchestration/code watermark drift or missing kg.db
#   cases  — brain CHANGELOG newer only (shipped-fix precedents)
#   skip   — KB-only edits; graph already current
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
CHANGELOG="$ROOT/cursor-bundle/brain/changelog/CHANGELOG.md"
KG_DB="$ROOT/cursor-bundle/kg/data/kg.db"
PENDING="$ROOT/.cursor/.pending-kg-rebuild"
LOG="$ROOT/.cursor/enrichment-sync.log"
BIN="$ROOT/cursor-bundle/kg/bin"
mkdir -p "$ROOT/.cursor"

log() { echo "[$(date -u +%H:%M:%S)] $*" | tee -a "$LOG"; }

_tier="skip"
_reason="graph current"

if [[ ! -f "$KG_DB" ]]; then
  _tier="full"
  _reason="kg.db missing"
else
  _doctor="$("$ROOT/cursor-bundle/kg/bin/kg.py" doctor 2>&1 || true)"
  if echo "$_doctor" | grep -q "WATERMARK DRIFT:"; then
    _tier="full"
    _reason="repo branch/sha drift since last build"
  elif echo "$_doctor" | grep -E "STALE:.*orchestration|deploy/application/orchestration" >/dev/null 2>&1; then
    _tier="full"
    _reason="orchestration newer than kg.db"
  elif [[ -f "$CHANGELOG" ]] && [[ "$CHANGELOG" -nt "$KG_DB" ]]; then
    _tier="cases"
    _reason="CHANGELOG newer than kg.db (case precedents only)"
  fi
fi

case "$_tier" in
  full)
    log "enrichment-sync: tier=FULL — $_reason"
    bash "$BIN/build.sh" >>"$LOG" 2>&1
    rm -f "$PENDING"
    bash "$ROOT/.cursor/hooks/kg-session-watermark.sh" enrichment-sync >/dev/null 2>&1 || true
    log "enrichment-sync: done (full)"
    ;;
  cases)
    log "enrichment-sync: tier=CASES — $_reason"
    if [[ ! -f "$ROOT/cursor-bundle/kg/data/kg.jsonl" ]]; then
      log "enrichment-sync: kg.jsonl missing — escalating CASES→FULL"
      bash "$BIN/build.sh" >>"$LOG" 2>&1
    else
      python3 "$BIN/refresh_cases.py" >>"$LOG" 2>&1
    fi
    rm -f "$PENDING"
    bash "$ROOT/.cursor/hooks/kg-session-watermark.sh" enrichment-sync >/dev/null 2>&1 || true
    log "enrichment-sync: done (cases)"
    ;;
  skip)
    if [[ -f "$PENDING" ]]; then
      log "enrichment-sync: tier=SKIP — pending commit flag but no graph/case drift ($_reason)"
      log "enrichment-sync: hint — prepend brain CHANGELOG via changelog-add.sh if you shipped code"
    fi
    ;;
esac

exit 0
