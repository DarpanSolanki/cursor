#!/usr/bin/env bash
# Workspace clutter audit + optional cleanup.
# Usage:
#   workspace-hygiene.sh              audit (exit 0 always)
#   workspace-hygiene.sh --clean      remove safe clutter
#   workspace-hygiene.sh --gate         exit 1 if issues remain (for ship-knowledge-gate)
#   workspace-hygiene.sh --verbose
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
CLEAN=0
VERBOSE=0
GATE=0
ISSUES=0
KG_CACHE_MAX="${KG_CACHE_MAX:-48}"
for a in "$@"; do
  case "$a" in
    --clean|-c) CLEAN=1 ;;
    --verbose|-v) VERBOSE=1 ;;
    --gate|-g) GATE=1 ;;
  esac
done

warn() { echo "  ⚠ $*"; ISSUES=$((ISSUES + 1)); }
ok()   { [[ "$VERBOSE" == 1 ]] && echo "  OK  $*" || true; }

echo "=== workspace hygiene audit ==="

# Cursor hooks — automation dead without hooks.json
if [[ -f "$ROOT/.cursor/hooks.json" ]]; then
  ok "hooks.json present"
else
  warn "hooks.json missing — Cursor automation inactive"
fi

# Skills manifest vs disk (count SKILL.md under .cursor/skills)
if [[ -f "$ROOT/cursor-bundle/brain/skills-manifest.json" ]]; then
  disk_n=$(find "$ROOT/.cursor/skills" -name 'SKILL.md' 2>/dev/null | wc -l)
  manifest_n=$(python3 -c "
import json, pathlib
m = json.loads(pathlib.Path('$ROOT/cursor-bundle/brain/skills-manifest.json').read_text())
print(len(m.get('skills', [])))
" 2>/dev/null || echo 0)
  if [[ "$disk_n" -gt "$manifest_n" ]]; then
    warn "skills-manifest stale ($manifest_n listed, $disk_n on disk) — update cursor-bundle/brain/skills-manifest.json"
  else
    ok "skills-manifest covers disk skills ($disk_n)"
  fi
fi

# Pending KG without changelog (self-learning gap)
PENDING="$ROOT/.cursor/.pending-kg-rebuild"
CHANGELOG="$ROOT/cursor-bundle/brain/changelog/CHANGELOG.md"
if [[ -f "$PENDING" && -f "$CHANGELOG" ]]; then
  cl_mtime=$(stat -c %Y "$CHANGELOG" 2>/dev/null || echo 0)
  pend_mtime=$(stat -c %Y "$PENDING" 2>/dev/null || echo 0)
  if [[ "$cl_mtime" -lt "$pend_mtime" ]]; then
    warn "commit without brain CHANGELOG — run changelog-add.sh before push"
  fi
fi

# Scratch: stale subdirs (>7d)
if [[ -d scripts/scratch ]]; then
  while IFS= read -r -d '' d; do
    [[ "$(basename "$d")" == "logs" || "$(basename "$d")" == "services" ]] && continue
    warn "stale scratch dir: $d"
    [[ "$CLEAN" == 1 ]] && rm -rf "$d" && echo "    → removed"
  done < <(find scripts/scratch -mindepth 1 -maxdepth 1 -type d -mtime +7 -print0 2>/dev/null)

  # Known session artifacts at scratch root (safe on --clean)
  if [[ "$CLEAN" == 1 ]]; then
    for pat in dpic_four_phase_sanity*.log dpic_phase4_only.log dpic_demo_disburse_*.json; do
      for f in scripts/scratch/$pat; do
        [[ -e "$f" ]] || continue
        rm -f "$f" && echo "    → removed $f"
      done
    done
    for f in scripts/scratch/sdcp-10255-*; do
      [[ -e "$f" ]] || continue
      rm -f "$f" && echo "    → removed $f"
    done
  else
    for pat in dpic_four_phase_sanity*.log dpic_phase4_only.log dpic_demo_disburse_*.json sdcp-10255-*; do
      for f in scripts/scratch/$pat; do
        [[ -e "$f" ]] || continue
        warn "scratch session artifact: $f"
      done
    done
  fi

  while IFS= read -r -d '' f; do
    base=$(basename "$f")
    [[ "$base" == ".gitignore" || "$base" == "dpic_demo_state.env" ]] && continue
    warn "scratch ephemeral (>3d): $f"
    [[ "$CLEAN" == 1 ]] && rm -f "$f" && echo "    → removed"
  done < <(find scripts/scratch -maxdepth 1 -type f -mtime +3 -print0 2>/dev/null)
fi

# Python bytecode in scripts/testing
if find scripts/testing -type d -name __pycache__ 2>/dev/null | grep -q .; then
  n=$(find scripts/testing -type d -name __pycache__ 2>/dev/null | wc -l)
  warn "testing __pycache__ ($n dir(s))"
  [[ "$CLEAN" == 1 ]] && find scripts/testing -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null && echo "    → removed"
fi

# Misplaced temps in .cursor/
for f in .cursor/tmp_* .cursor/*_analysis*.txt .cursor/Untitled*; do
  [[ -e "$f" ]] || continue
  warn "misplaced temp in .cursor: $f"
  [[ "$CLEAN" == 1 ]] && rm -f "$f" && echo "    → removed"
done

# Operational logs — truncate when large
for log in scripts/scratch/logs/*.log .cursor/enrichment-sync.log; do
  [[ -f "$log" ]] || continue
  sz=$(stat -c%s "$log" 2>/dev/null || echo 0)
  if [[ "$sz" -gt 65536 ]]; then
    warn "large log ($(( sz / 1024 ))KB): $log"
    [[ "$CLEAN" == 1 ]] && : >"$log" && echo "    → truncated"
  fi
done

# Root-level noise
for f in Untitled* *_logs*.txt *.log; do
  [[ -e "$f" ]] || continue
  warn "root clutter: $f"
  [[ "$CLEAN" == 1 ]] && rm -f "$f" && echo "    → removed"
done

# KG cache LRU
if [[ -d cursor-bundle/kg/data/cache ]]; then
  n=$(find cursor-bundle/kg/data/cache -name '*.manifest.json' 2>/dev/null | wc -l)
  if [[ "$n" -gt "$KG_CACHE_MAX" ]]; then
    warn "KG cache has $n snapshots (max $KG_CACHE_MAX)"
    [[ "$CLEAN" == 1 ]] && KG_CACHE_MAX="$KG_CACHE_MAX" python3 cursor-bundle/kg/bin/kg.py cache --prune 2>/dev/null && echo "    → pruned"
  else
    ok "KG cache snapshots: $n (max $KG_CACHE_MAX)"
  fi
fi

if [[ "$ISSUES" -eq 0 ]]; then
  echo "✓ No hygiene issues found"
else
  echo "-- $ISSUES issue(s)${CLEAN:+ (cleaned where applicable)}"
  [[ "$CLEAN" == 0 ]] && echo "   Run: scripts/bin/workspace-hygiene.sh --clean"
fi

[[ "$GATE" == 1 && "$ISSUES" -gt 0 ]] && exit 1
exit 0
