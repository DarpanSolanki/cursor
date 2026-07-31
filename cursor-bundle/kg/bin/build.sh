#!/usr/bin/env bash
# build.sh — rebuild the system KG from sliProd repos + cursor-bundle/brain.
#   cursor-bundle/kg/bin/build.sh [--force]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BUNDLE="$(cd "$SCRIPT_DIR/../.." && pwd)"
ROOT="$(cd "$BUNDLE/.." && pwd)"
BIN="$BUNDLE/kg/bin"
DATA="$BUNDLE/kg/data"

cd "$ROOT"
mkdir -p "$DATA"

exec 9>"$DATA/.build.lock"
if command -v flock >/dev/null 2>&1; then
  flock -w 1800 9 || { echo "build: could not acquire lock (another build running too long)"; exit 1; }
fi

REPOS=$(for d in novopay-* trustt-*; do [ -d "$d/.git" ] && printf '%s ' "$d"; done)

CACHE="$DATA/cache"
mkdir -p "$CACHE"
FORCE=0
[[ "${1:-}" == "--force" ]] && FORCE=1

_composite() {
  # Shared key with kg-switch / kg_composite.py (docs mtime_ns fingerprint).
  python3 "$BIN/kg_composite.py" key
}

KEY="$(_composite)"
if [[ "$FORCE" == 0 ]] && [[ -f "$CACHE/$KEY.db" ]]; then
  cp "$CACHE/$KEY.db" "$DATA/kg.db"
  cp "$CACHE/$KEY.jsonl" "$DATA/kg.jsonl" 2>/dev/null || true
  cp "$CACHE/$KEY.json" "$DATA/stats.json" 2>/dev/null || true
  touch "$DATA/kg.db"
  echo "✓ KG restored from cache for current branch-set (key $KEY)."
  echo "  built_at: $(grep -o '\"built_at\"[^,]*' "$DATA/stats.json" | head -1)"
  echo "  (force rebuild: cursor-bundle/kg/bin/build.sh --force)"
  exit 0
fi

tmp="$DATA/.raw.jsonl"
: > "$tmp"
python3 "$BIN/build_orchestration.py" $REPOS      >> "$tmp"
python3 "$BIN/build_internal_calls.py" "$tmp" $REPOS >> "$tmp"
python3 "$BIN/build_event_dispatch.py" "$tmp" $REPOS >> "$tmp"
python3 "$BIN/build_contracts.py" $REPOS          >> "$tmp"
python3 "$BIN/build_services.py"                  >> "$tmp"
python3 "$BIN/build_tables.py" $REPOS             >> "$tmp"
python3 "$BIN/build_dataaccess.py" "$tmp" $REPOS  >> "$tmp"
# Method-level symbols for kg impact (money-path packages; branch = live checkout)
python3 "$BIN/build_java_symbols.py" $REPOS         >> "$tmp"
python3 "$BIN/build_money_concepts.py" "$tmp" $REPOS >> "$tmp"
python3 "$BIN/build_kafka.py" "$tmp" $REPOS       >> "$tmp"
python3 "$BIN/build_schedulers.py" "$tmp"         >> "$tmp"
# DOMAIN SEMANTICS + FRAMEWORK LAYER (entity/txn_type/gl_mech/batch_cfg/redis_key/framework/server)
python3 "$BIN/build_semantics_bone.py" "$tmp" $REPOS >> "$tmp"
python3 "$BIN/build_semantics_closeup.py" "$tmp" $REPOS >> "$tmp"
# Activation/wiring (api_master + platform-lib anchors) — was built but unwired
python3 "$BIN/build_activation.py" "$tmp"         >> "$tmp"
python3 "$BIN/build_cases.py" "$tmp"              >> "$tmp"
python3 "$BIN/build_curated.py"                   >> "$tmp"
python3 "$BIN/build_docs.py" "$tmp"               >> "$tmp"
python3 "$BIN/build_failuremodes.py" "$tmp" $REPOS >> "$tmp"

python3 - "$tmp" "$DATA/kg.jsonl" "$DATA/stats.json" $REPOS <<'PY'
import json, sys, collections, subprocess, datetime, hashlib, re

raw, out, statsf = sys.argv[1], sys.argv[2], sys.argv[3]
repos = sys.argv[4:]
seen = set()
nodes = []
edges = []
# Track processor bean -> set of repos (from orch emits) for shared-attr fix
proc_repos = collections.defaultdict(set)
entity_by_id = {}
for line in open(raw, encoding="utf-8"):
    o = json.loads(line)
    if o["t"] == "node":
        if o.get("kind") == "processor" and o.get("repo"):
            proc_repos[o["id"]].add(o["repo"])
        # entity purpose upgrade: later non-UNKNOWN / purpose_backfill wins
        if o.get("kind") == "entity":
            prev = entity_by_id.get(o["id"])
            if prev is None:
                entity_by_id[o["id"]] = o
            else:
                prev_p = (prev.get("purpose") or "")
                new_p = (o.get("purpose") or "")
                if prev_p.startswith("UNKNOWN") and new_p and not new_p.startswith("UNKNOWN"):
                    entity_by_id[o["id"]] = o
                elif o.get("purpose_backfill") and not prev.get("purpose_backfill"):
                    if new_p and not new_p.startswith("UNKNOWN"):
                        entity_by_id[o["id"]] = o
            continue
        if o["id"] in seen:
            continue
        seen.add(o["id"])
        nodes.append(o)
    else:
        edges.append(o)
for eid, eo in entity_by_id.items():
    if eid not in seen:
        seen.add(eid)
        nodes.append(eo)
# Shared processors used from multiple repos → repo=shared (fixes ATTR_DRIFT)
for n in nodes:
    if n.get("kind") != "processor":
        continue
    rs = proc_repos.get(n["id"]) or set()
    if len(rs) > 1:
        n["repo"] = "shared"
        n["repos"] = sorted(rs)
with open(out, "w", encoding="utf-8") as fh:
    for o in nodes + edges:
        fh.write(json.dumps(o, ensure_ascii=False) + "\n")
nk = collections.Counter(n["kind"] for n in nodes)
ne = collections.Counter(e["rel"] for e in edges)
_RELRE = re.compile(r'(?:^|/)(mfi_(?:integration|release)_v[0-9][0-9.]*)$')

def git(d, *a):
    try:
        return subprocess.check_output(["git", "-C", d, *a], text=True, stderr=subprocess.DEVNULL).strip()
    except Exception:
        return ""

def release_refs(d):
    out = git(d, "for-each-ref", "--format=%(refname)", "refs/remotes/upstream", "refs/heads")
    seen = {}
    for ref in out.splitlines():
        m = _RELRE.search(ref)
        if m and m.group(1) not in seen:
            seen[m.group(1)] = ref
    return seen

def fork_base(d):
    best = None
    for name, ref in release_refs(d).items():
        mb = git(d, "merge-base", "HEAD", ref)
        if not mb:
            continue
        cnt = git(d, "rev-list", "--count", f"{mb}..HEAD")
        try:
            cnt = int(cnt)
        except ValueError:
            continue
        if best is None or cnt < best[1]:
            best = (name, cnt, mb[:10])
    return best

wm = {"built_at": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"), "repos": {}}
for r in sorted(repos):
    br = git(r, "rev-parse", "--abbrev-ref", "HEAD")
    rec = {"branch": br, "sha": git(r, "rev-parse", "--short=10", "HEAD"), "dirty": bool(git(r, "status", "--porcelain"))}
    if rec["dirty"]:
        _blob = git(r, "status", "--porcelain") + git(r, "diff", "HEAD")
        rec["dirty_hash"] = hashlib.sha1(_blob.encode("utf-8", "replace")).hexdigest()[:12]
    if br and not re.match(r'^mfi_(integration|release)_v[0-9]', br):
        fb = fork_base(r)
        if fb:
            rec["base"], rec["feature_delta"], rec["fork_sha"] = fb[0], fb[1], fb[2]
    wm["repos"][r] = rec
stats = {"nodes": len(nodes), "edges": len(edges), "node_kinds": dict(nk), "edge_rels": dict(ne), "watermark": wm}
json.dump(stats, open(statsf, "w"), indent=2)
_REL = re.compile(r'^mfi_(integration|release)_v[0-9]')
_wip = [r for r, i in wm["repos"].items() if i.get("branch") and not _REL.match(i["branch"])]
if _wip:
    print(f"⚠ WATERMARK: KG built off {len(_wip)} non-release branch(es) — knowledge is PROVISIONAL:")
    for r in _wip:
        i = wm["repos"][r]
        base = i.get("base")
        if base:
            print(f"    {r}: {i['branch']}  <- base {base} (+{i.get('feature_delta', '?')} WIP commits)")
        else:
            print(f"    {r}: {i['branch']}  <- base UNRESOLVED")
print(f"KG built: {len(nodes)} nodes, {len(edges)} edges")
print("  node kinds:", dict(nk))
print("  edge rels :", dict(ne))
PY

python3 "$BIN/build_db.py" "$DATA/kg.jsonl" "$DATA/kg.db"
rm -f "$tmp" "$DATA/orchestration.jsonl" "$DATA/orch.err" 2>/dev/null || true

cp "$DATA/kg.db" "$CACHE/$KEY.db"
cp "$DATA/kg.jsonl" "$CACHE/$KEY.jsonl" 2>/dev/null || true
cp "$DATA/stats.json" "$CACHE/$KEY.json" 2>/dev/null || true
echo "✓ snapshotted to cache (key $KEY)."
# Keep newest 8 branch-set snapshots; drop sidecars + orphan manifests (no .db).
ls -1t "$CACHE"/*.db 2>/dev/null | tail -n +9 | while read -r old; do
  base="${old%.db}"
  rm -f "$old" "${base}.jsonl" "${base}.json" "${base}.manifest.json"
done
for m in "$CACHE"/*.manifest.json; do
  [[ -f "$m" ]] || continue
  base="${m%.manifest.json}"
  [[ -f "${base}.db" ]] || rm -f "$m"
done
echo "-> $DATA/kg.jsonl + $DATA/kg.db"
