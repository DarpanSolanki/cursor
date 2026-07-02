#!/usr/bin/env bash
# afterFileEdit — flag any ship-path edit; accumulate tiered pending work.
set -euo pipefail
ROOT="${CURSOR_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
INPUT=$(cat)
FILE=$(echo "$INPUT" | python3 -c "import json,sys; print(json.load(sys.stdin).get('file_path',''))" 2>/dev/null || true)
[[ -n "$FILE" ]] || exit 0

python3 "$ROOT/scripts/lib/infer_ship_apis.py" --is-ship-path "$FILE" 2>/dev/null || exit 0

python3 - <<'PY' "$FILE" "$ROOT"
import json, sys, datetime
from pathlib import Path

sys.path.insert(0, str(Path(sys.argv[2]) / "scripts/lib"))
from infer_ship_apis import (
    build_impact,
    classify_path,
    infer_from_path,
    infer_repo_from_path,
    is_ship_path,
    merge_tier,
    registry_case_for_api,
    smoke_cases_for_tier,
    health_cases_for_repos,
)

f, root = Path(sys.argv[1]), Path(sys.argv[2])
p = f if f.is_absolute() else root / f
s = str(p)
if not is_ship_path(s):
    sys.exit(0)

try:
    rel = str(p.relative_to(root))
except ValueError:
    rel = s

flag = root / ".cursor/.pending-ship-nudge"
flag.parent.mkdir(parents=True, exist_ok=True)
flag.write_text(rel + "\n", encoding="utf-8")

pending_path = root / ".cursor/.pending-ship-work.json"
now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
data = {
    "tier": "workspace",
    "files": [],
    "apis": [],
    "repos": [],
    "registry_cases": [],
    "smoke_money_cases": [],
    "smoke_service_cases": [],
    "health_cases": [],
    "updated_at": now,
}
if pending_path.is_file():
    try:
        data = json.loads(pending_path.read_text(encoding="utf-8"))
    except Exception:
        pass

if rel not in data["files"]:
    data["files"].append(rel)

data["tier"] = merge_tier(data.get("tier"), classify_path(s))

api = infer_from_path(s)
if api and api not in data.get("apis", []):
    data.setdefault("apis", []).append(api)
    case = registry_case_for_api(api)
    if case and case not in data.setdefault("registry_cases", []):
        data["registry_cases"].append(case)

repo = infer_repo_from_path(s)
if repo and repo not in data.get("repos", []):
    data.setdefault("repos", []).append(repo)

# Recompute smoke/health from full file set
all_paths = [str(root / x) if not x.startswith("/") else x for x in data["files"]]
impact = build_impact(all_paths)
data["tier"] = impact["tier"]
data["smoke_money_cases"] = impact["smoke_money_cases"]
data["smoke_service_cases"] = impact["smoke_service_cases"]
data["health_cases"] = impact["health_cases"]
for c in impact["registry_cases"]:
    if c not in data["registry_cases"]:
        data["registry_cases"].append(c)

data["close_command"] = "bash scripts/bin/workspace-close.sh --from-pending"
data["updated_at"] = now
data.pop("ship_loop_passed_at", None)
pending_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
PY
exit 0
