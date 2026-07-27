#!/usr/bin/env bash
# ORPHAN-DOCUMENTED (SU-STITCH-005): NOT wired in .cursor/hooks.json.
# Superseded by after-ship-path-edit.sh (afterFileEdit). Kept as reference / manual invoke.
# Indirect caller: historically workspace-close docs; live path = after-ship-path-edit.sh.
set -euo pipefail
ROOT="${CURSOR_PROJECT_DIR:-$(cd "$(dirname "$0")/../.." && pwd)}"
INPUT=$(cat)
FILE=$(echo "$INPUT" | python3 -c "import json,sys; print(json.load(sys.stdin).get('file_path',''))" 2>/dev/null || true)
[[ -n "$FILE" ]] || exit 0

python3 - <<'PY' "$FILE" "$ROOT"
import json, sys, datetime
from pathlib import Path

f, root = Path(sys.argv[1]), Path(sys.argv[2])
p = f if f.is_absolute() else root / f
s = str(p)

ship = (
    "novopay-platform-accounting-v2" in s
    or ("novopay-mfi-los" in s and any(x in s for x in ("Disburse", "Foreclos", "Repay", "Processor")))
    or ("novopay-platform-payments" in s and "Processor.java" in s)
    or ("/orchestration/" in s and s.endswith(".xml"))
    or ("Processor.java" in s and any(x in s for x in ("accounting", "mfi-los", "payments")))
    or "_responseTemplate.json" in s
    or "/deploy/application/templates/" in s
)

if not ship:
    sys.exit(0)

flag = root / ".cursor/.pending-ship-nudge"
flag.parent.mkdir(parents=True, exist_ok=True)
flag.write_text(s + "\n", encoding="utf-8")

sys.path.insert(0, str(root / "scripts/lib"))
from infer_ship_apis import (
    infer_from_path,
    infer_repo_from_path,
    registry_case_for_api,
    smoke_cases_for_tier,
)

pending_path = root / ".cursor/.pending-ship-work.json"
now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
data = {"files": [], "apis": [], "repos": [], "registry_cases": [], "updated_at": now}
if pending_path.is_file():
    try:
        data = json.loads(pending_path.read_text(encoding="utf-8"))
    except Exception:
        pass

try:
    rel = str(p.relative_to(root))
except ValueError:
    rel = s
if rel not in data["files"]:
    data["files"].append(rel)
api = infer_from_path(s)
if api and api not in data.get("apis", []):
    data.setdefault("apis", []).append(api)
    case = registry_case_for_api(api)
    if case and case not in data.setdefault("registry_cases", []):
        data["registry_cases"].append(case)
repo = infer_repo_from_path(s)
if repo and repo not in data.get("repos", []):
    data.setdefault("repos", []).append(repo)
data["smoke_money_cases"] = smoke_cases_for_tier("money")
data["close_command"] = "bash scripts/bin/workspace-close.sh --from-pending"
data["updated_at"] = now
data.pop("ship_loop_passed_at", None)
pending_path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
PY
exit 0
