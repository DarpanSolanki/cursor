#!/usr/bin/env bash
# Smoke-test trustt-kg MCP: all 17 tools, JSON-RPC hygiene, semantic needles, align isError.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SRV="$ROOT/cursor-bundle/kg/mcp/kg_mcp_server.py"
PY="${PYTHON:-python3}"
ACC_BRANCH="$("$PY" - <<PY 2>/dev/null || echo ""
import subprocess
from pathlib import Path
repo = Path(${ROOT@Q}) / "trustt-platform-accounting"
r = subprocess.run(
    ["git", "-C", str(repo), "rev-parse", "--abbrev-ref", "HEAD"],
    capture_output=True, text=True, check=False,
)
print((r.stdout or "").strip())
PY
)"
if [[ -z "$ACC_BRANCH" ]]; then
  ACC_BRANCH="$("$PY" "$ROOT/cursor-bundle/kg/bin/kg.py" watermark 2>/dev/null | awk '/trustt-platform-accounting/ {print $2; exit}' | cut -d@ -f1)"
fi
[[ -n "$ACC_BRANCH" ]] || ACC_BRANCH="mfi_integration_v3.4.2.4"
MISALIGN_BRANCH="mfi_integration_v9.9.9.9"

"$PY" - <<PY
import json, subprocess, sys, time
from pathlib import Path

srv = Path(${SRV@Q})
acc_branch = ${ACC_BRANCH@Q}
misalign_branch = ${MISALIGN_BRANCH@Q}
tools = [
    ("kg_doctor", {}),
    ("kg_watermark", {}),
    ("kg_align", {"repo": "trustt-platform-accounting", "branch": acc_branch}),
    ("kg_search", {"query": "getLoanForeclosureDetails"}),
    ("kg_orient", {"query": "getLoanForeclosureDetails"}),
    ("kg_flow", {"query": "getLoanForeclosureDetails"}),
    ("kg_why", {"query": "getLoanForeclosureDetails"}),
    ("kg_impact", {"query": "request:trustt-platform-accounting/getLoanForeclosureDetails", "depth": 1}),
    ("kg_cases", {"query": "getLoanForeclosureDetails"}),
    ("kg_crud", {"query": "getLoanForeclosureDetails"}),
    ("kg_writes", {"query": "loan_account_part_prepayment_details"}),
    ("kg_reads", {"query": "loan_account"}),
    ("kg_search", {"query": "134497"}),
    ("kg_node", {"query": "request:trustt-platform-accounting/disburseLoan"}),
    ("kg_fixed_elsewhere", {
        "query": "getLoanForeclosureDetails",
        "repo": "trustt-platform-accounting",
        "base": acc_branch,
        "fetch_if_stale": False,
    }),
    ("kg_map_audit", {"fail_on_mismatch": False}),
    ("mcp_auth", {}),
    ("workspace_status", {}),
    ("ship_plan", {}),
]
# Misalign probe — must set isError
align_fail = ("kg_align", {"repo": "trustt-platform-accounting", "branch": misalign_branch})
msgs = [
    {"jsonrpc": "2.0", "id": 1, "method": "initialize",
     "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                "clientInfo": {"name": "kg-mcp-smoke", "version": "2"}}},
    {"jsonrpc": "2.0", "method": "notifications/initialized"},
    {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
]
for i, (name, args) in enumerate(tools, start=10):
    msgs.append({"jsonrpc": "2.0", "id": i, "method": "tools/call",
                 "params": {"name": name, "arguments": args}})
align_fail_id = 10 + len(tools)
msgs.append({"jsonrpc": "2.0", "id": align_fail_id, "method": "tools/call",
             "params": {"name": align_fail[0], "arguments": align_fail[1]}})

stdin = "\n".join(json.dumps(m) for m in msgs) + "\n"
t0 = time.time()
p = subprocess.run([sys.executable, str(srv)], input=stdin, text=True,
                   capture_output=True, timeout=120, cwd=${ROOT@Q},
                   env={**dict(**{k: v for k, v in __import__("os").environ.items()}),
                        "KG_NO_AUTO_REBUILD": "1", "PYTHONUNBUFFERED": "1"})
elapsed = time.time() - t0
print(f"elapsed={elapsed:.1f}s exit={p.returncode}")

bad = []
parsed = []
for i, line in enumerate((p.stdout or "").splitlines(), 1):
    if not line.strip():
        continue
    try:
        o = json.loads(line)
    except json.JSONDecodeError as e:
        bad.append((i, line[:120], str(e)))
        continue
    if "jsonrpc" not in o:
        bad.append((i, line[:120], "missing jsonrpc"))
        continue
    parsed.append(o)

if bad:
    print("FAIL: non-JSON on MCP stdout (protocol corruption):")
    for i, preview, err in bad[:10]:
        print(f"  line {i}: {err}: {preview!r}")
    sys.exit(2)

by_id = {o.get("id"): o for o in parsed if o.get("id") is not None}
init = by_id.get(1) or {}
si = (init.get("result") or {}).get("serverInfo") or {}
print(f"server={si.get('name')} version={si.get('version')}")
if si.get("version") != "1.9.1":
    print(f"WARN: expected server version 1.9.1 got {si.get('version')}")

listed = [t["name"] for t in ((by_id.get(2) or {}).get("result") or {}).get("tools") or []]
print(f"tools/list={len(listed)}")
expected_names = sorted(TOOLS_NAMES := [n for n, _ in tools] + [align_fail[0]])
# Server advertises smoke-probed tools plus kg_concept/kg_enhance (lookup extras).
if len(listed) < 19 or len(listed) > 22:
    print(f"FAIL: expected 19..22 tools, got {len(listed)}: {listed}")
    sys.exit(3)
for required in ("kg_doctor", "kg_align", "ship_plan", "workspace_status"):
    if required not in listed:
        print(f"FAIL: {required} missing from tools/list")
        sys.exit(3)
for gone in ("kg_validate", "kg_fresh", "kg_error"):
    if gone in listed:
        print(f"FAIL: {gone} should be removed (folded into kg_doctor/kg_search)")
        sys.exit(3)
if "kg_align" not in listed:
    print("FAIL: kg_align missing from tools/list")
    sys.exit(3)

fails = []
per_tool_ms = {}
for i, (name, _) in enumerate(tools, start=10):
    o = by_id.get(i)
    if not o:
        fails.append(f"{name}: no response")
        continue
    res = o.get("result") or {}
    text = ""
    if res.get("content"):
        text = (res["content"][0].get("text") or "")[:80].replace("\n", " ")
    if res.get("isError") and name not in ("kg_map_audit",):
        fails.append(f"{name}: unexpected isError text={text!r}")
        continue
    if "error" in o and o["error"]:
        fails.append(f"{name}: rpc error {o['error']}")
        continue
    print(f"  PASS {name}: {text!r}")

# align misalign must isError
o_fail = by_id.get(align_fail_id) or {}
if not (o_fail.get("result") or {}).get("isError"):
    fails.append("kg_align misalign: expected isError=True")
else:
    print("  PASS kg_align_misalign: isError=True")

needles = {
    "kg_watermark": ("KG built",),
    "kg_align": ("ALIGNED",),
    "kg_search": ("request", "getLoanForeclosureDetails", "diag:", "error", "134497", "match"),
    "kg_orient": ("ORIENT", "getLoanForeclosureDetails"),
    "kg_flow": ("FLOW", "getLoanForeclosureDetails"),
    "kg_why": ("WHY",),
    "kg_impact": ("getLoanForeclosure",),
    "kg_cases": ("PRECEDENT", "shipped"),
    "kg_crud": ("FOOTPRINT", "prepayment"),
    "kg_writes": ("WRITERS",),
    "kg_reads": ("READERS",),
    "kg_doctor": ("nodes/edges", "OK:", "KG FRESH", "PROVISIONAL", "STALE"),
    "kg_node": ("OUT", "IN"),
    "kg_fixed_elsewhere": ("FIXED-ELSEWHERE", "REUSE_", "FILE_TOUCH", "cache="),
    "kg_map_audit": ("soft_gap_count", "verdict"),
    "mcp_auth": ("auth_required", "ok"),
    "workspace_status": ("provenance", "kg"),
    "ship_plan": ("ordered_cases", "tier"),
}
sem_fails = []
for i, (name, _) in enumerate(tools, start=10):
    o = by_id.get(i) or {}
    text = ""
    if (o.get("result") or {}).get("content"):
        text = o["result"]["content"][0].get("text") or ""
    want = needles.get(name) or ()
    if want and not any(n in text for n in want):
        sem_fails.append(f"{name}: expected one of {want}; got={text[:100]!r}")
if sem_fails:
    print("FAIL semantic content:")
    for f in sem_fails:
        print(" ", f)
    sys.exit(5)

if fails:
    print("FAIL tool calls:")
    for f in fails:
        print(" ", f)
    sys.exit(4)

if elapsed > 60:
    print(f"WARN: full smoke took {elapsed:.1f}s (>60s)")

print(f"PASS: smoke calls + align misalign gate (kg_enhance in e2e only); tools={len(listed)}; elapsed={elapsed:.1f}s")

# Train routing gate — detect-only vs sync (honest contract)
sys.path.insert(0, ${ROOT@Q} + "/scripts/lib")
import train_sync as ts
live_acc = ts.live_branch("trustt-platform-accounting")
if not live_acc:
    print("WARN: train_routing: accounting repo branch unknown — skip")
else:
    mis = ts.sync_plan("work on branch mfi_integration_v9.9.9.9 INT")
    if not mis.get("needs_sync"):
        print("FAIL train_routing: fake v9.9.9.9 must need_sync vs live", live_acc)
        sys.exit(6)
    aligned = ts.sync_plan(f"on branch {live_acc} interest accrual")
    if aligned.get("needs_sync"):
        print("FAIL train_routing: message matching live branch must not need_sync", live_acc)
        sys.exit(6)
    print(f"  PASS train_routing: needs_sync detection (live={live_acc})")

# kg_enhance schema must expose train + sync_domain
enh = next((t for t in listed if t == "kg_enhance"), None)
if not enh:
    print("FAIL: kg_enhance missing from tools/list")
    sys.exit(7)
enh_tool = next(t for t in ((by_id.get(2) or {}).get("result") or {}).get("tools") or [] if t.get("name") == "kg_enhance")
props = ((enh_tool or {}).get("inputSchema") or {}).get("properties") or {}
for key in ("train", "sync_domain", "dry_run"):
    if key not in props:
        print(f"FAIL kg_enhance schema missing {key}")
        sys.exit(7)
print("  PASS kg_enhance schema: train + sync_domain + dry_run")

sys.exit(0)
PY
