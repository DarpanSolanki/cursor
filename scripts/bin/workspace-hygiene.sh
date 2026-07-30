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
# Align with cursor-bundle/kg/bin/build.sh (keeps newest 8 *.db snapshots).
KG_CACHE_MAX="${KG_CACHE_MAX:-8}"
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
  if [[ "$CLEAN" == 1 ]]; then
    find scripts/testing -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
    echo "    → removed testing __pycache__ ($n)"
  else
    warn "testing __pycache__ ($n dir(s))"
  fi
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

# Local Yugabyte orphan pg_temp_* schemas (CREATE TEMP leftovers from local scripts)
if [[ "$CLEAN" == 1 ]]; then
  if bash "$ROOT/scripts/bin/db-local-hygiene.sh" --clean 2>/dev/null; then
    ok "local Yugabyte temp-schema hygiene"
  else
    warn "local Yugabyte temp-schema hygiene failed (is YB up on :5433?)"
  fi
else
  if command -v psql >/dev/null 2>&1; then
    temp_ns=$(PGPASSWORD="${PGPASSWORD:-yugabyte}" psql -h 127.0.0.1 -p 5433 -U yugabyte -d yugabyte -At -c \
      "SELECT count(*) FROM pg_namespace WHERE nspname LIKE 'pg_temp%' OR nspname LIKE 'pg_toast_temp%'" 2>/dev/null || echo "")
    if [[ -n "$temp_ns" && "$temp_ns" =~ ^[0-9]+$ && "$temp_ns" -gt 20 ]]; then
      warn "local Yugabyte orphan temp schemas: $temp_ns — run: bash scripts/bin/db-local-hygiene.sh --clean"
    elif [[ -n "$temp_ns" && "$temp_ns" =~ ^[0-9]+$ ]]; then
      ok "local Yugabyte temp schemas: $temp_ns"
    fi
  fi
fi

# KG cache LRU — top-level branch-set manifests only (newest KG_CACHE_MAX)
# Also drop orphan manifests / sidecars with no matching *.db (build.sh leaves these otherwise).
if [[ -d cursor-bundle/kg/data/cache ]]; then
  n=$(find cursor-bundle/kg/data/cache -maxdepth 1 -name '*.manifest.json' 2>/dev/null | wc -l)
  orphan_n=$(python3 - <<'PY'
from pathlib import Path
cache = Path("cursor-bundle/kg/data/cache")
mans = list(cache.glob("*.manifest.json"))
orph = 0
for m in mans:
    key = m.name[: -len(".manifest.json")]
    if not (cache / f"{key}.db").is_file():
        orph += 1
print(orph)
PY
)
  if [[ "$n" -gt "$KG_CACHE_MAX" || "$orphan_n" -gt 0 ]]; then
    if [[ "$CLEAN" == 1 ]]; then
      python3 - <<PY
from pathlib import Path
import os
cache = Path("cursor-bundle/kg/data/cache")
max_n = int(os.environ.get("KG_CACHE_MAX", "$KG_CACHE_MAX"))
mans = sorted(
    (p for p in cache.glob("*.manifest.json") if p.is_file()),
    key=lambda p: p.stat().st_mtime,
    reverse=True,
)
# Prefer keys that still have a .db when ranking keep-set.
with_db = [p for p in mans if (cache / (p.name[: -len(".manifest.json")] + ".db")).is_file()]
without_db = [p for p in mans if p not in with_db]
ordered = with_db + without_db
keep = {p.name[: -len(".manifest.json")] for p in ordered[:max_n]
        if (cache / (p.name[: -len(".manifest.json")] + ".db")).is_file()}
# Always keep every remaining .db under max_n newest dbs (even if manifest missing).
dbs = sorted(cache.glob("*.db"), key=lambda p: p.stat().st_mtime, reverse=True)
keep |= {p.stem for p in dbs[:max_n]}
removed = 0
for p in list(cache.iterdir()):
    if not p.is_file():
        continue
    if p.name.endswith(".manifest.json"):
        key = p.name[: -len(".manifest.json")]
    else:
        key = p.name.split(".", 1)[0]
    if key not in keep:
        p.unlink(missing_ok=True)
        removed += 1
print(f"pruned_files={removed} keep={len(keep)}")
PY
      n2=$(find cursor-bundle/kg/data/cache -maxdepth 1 -name '*.manifest.json' 2>/dev/null | wc -l)
      if [[ "$n2" -gt "$KG_CACHE_MAX" ]]; then
        warn "KG cache still oversized after prune ($n2 > $KG_CACHE_MAX)"
      else
        echo "    → pruned KG cache manifests $n → $n2 (orphans were $orphan_n)"
      fi
    else
      warn "KG cache has $n snapshots (max $KG_CACHE_MAX), orphan_manifests=$orphan_n"
    fi
  else
    ok "KG cache snapshots: $n (max $KG_CACHE_MAX)"
  fi
fi

# registry-proposals.json — impact.stub flood (impact_tests used to draft on every mark-ran)
PROPOSALS="$ROOT/scripts/testing/registry-proposals.json"
if [[ -f "$PROPOSALS" ]]; then
  stub_n=$(python3 - <<'PY'
import json
from pathlib import Path
p = Path("scripts/testing/registry-proposals.json")
try:
    data = json.loads(p.read_text(encoding="utf-8"))
except Exception:
    print(0); raise SystemExit
n = sum(
    1
    for x in (data.get("proposals") or [])
    if (x.get("source") == "impact_tests")
    or str(x.get("id") or "").startswith("impact.stub.")
)
print(n)
PY
)
  if [[ "$stub_n" -gt 0 ]]; then
    warn "registry-proposals has $stub_n impact.stub drafts (noise — promote intentionally via --draft-stubs)"
    if [[ "$CLEAN" == 1 ]]; then
      python3 - <<'PY'
import json
from datetime import datetime, timezone
from pathlib import Path
p = Path("scripts/testing/registry-proposals.json")
data = json.loads(p.read_text(encoding="utf-8"))
kept = [
    x for x in (data.get("proposals") or [])
    if not (
        (x.get("source") == "impact_tests")
        or str(x.get("id") or "").startswith("impact.stub.")
    )
]
removed = len(data.get("proposals") or []) - len(kept)
data["proposals"] = kept
data["updated"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
p.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
print(f"    → pruned {removed} impact stubs; kept {len(kept)}")
PY
    fi
  else
    ok "registry-proposals has no impact.stub flood"
  fi
fi

# Untracked ops SQL under scripts/sql/{adhoc,deploy} — hygiene never auto-deletes these
# (ops packs are deliberate). Warn so agents commit or move to scratch, not leave dirty forever.
untracked_sql=$(git -C "$ROOT" status --porcelain -- scripts/sql/adhoc scripts/sql/deploy 2>/dev/null | grep -E '^\?\?' | wc -l || true)
untracked_sql=${untracked_sql// /}
if [[ "${untracked_sql:-0}" -gt 0 ]]; then
  warn "untracked scripts/sql packs: $untracked_sql file(s) — commit reusable ops SQL or delete one-shots (hygiene will NOT auto-rm)"
  if [[ "$VERBOSE" == 1 ]]; then
    git -C "$ROOT" status --porcelain -- scripts/sql/adhoc scripts/sql/deploy 2>/dev/null | grep -E '^\?\?' || true
  fi
else
  ok "no untracked scripts/sql/{adhoc,deploy} packs"
fi

if [[ "$ISSUES" -eq 0 ]]; then
  echo "✓ No hygiene issues found"
else
  echo "-- $ISSUES issue(s)${CLEAN:+ (cleaned where applicable)}"
  [[ "$CLEAN" == 0 ]] && echo "   Run: scripts/bin/workspace-hygiene.sh --clean"
fi

[[ "$GATE" == 1 && "$ISSUES" -gt 0 ]] && exit 1
exit 0
