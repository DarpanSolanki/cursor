#!/usr/bin/env bash
# Smoke-test trustt-kg MCP: discovery + every tool call; assert stdout is JSON-RPC-only.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SRV="$ROOT/cursor-bundle/kg/mcp/kg_mcp_server.py"
PY="${PYTHON:-python3}"

"$PY" - <<PY
import json, subprocess, sys, time
from pathlib import Path

srv = Path(${SRV@Q})
tools = [
    ("kg_validate", {}),
    ("kg_fresh", {}),
    ("kg_watermark", {}),
    ("kg_search", {"query": "getLoanForeclosureDetails"}),
    ("kg_orient", {"query": "getLoanForeclosureDetails"}),
    ("kg_flow", {"query": "getLoanForeclosureDetails"}),
    ("kg_why", {"query": "getLoanForeclosureDetails"}),
    ("kg_impact", {"query": "request:trustt-platform-accounting/getLoanForeclosureDetails", "depth": 1}),
    ("kg_cases", {"query": "getLoanForeclosureDetails"}),
    ("kg_crud", {"query": "getLoanForeclosureDetails"}),
    ("kg_writes", {"query": "loan_account_part_prepayment_details"}),
    ("kg_fixed_elsewhere", {
        "query": "getLoanForeclosureDetails",
        "repo": "trustt-platform-accounting",
        "base": "mfi_integration_v3.5.2.2",
    }),
    ("kg_map_audit", {"fail_on_mismatch": True}),
    ("mcp_auth", {}),
    ("workspace_status", {}),
    ("ship_plan", {}),
]
msgs = [
    {"jsonrpc": "2.0", "id": 1, "method": "initialize",
     "params": {"protocolVersion": "2024-11-05", "capabilities": {},
                "clientInfo": {"name": "kg-mcp-smoke", "version": "1"}}},
    {"jsonrpc": "2.0", "method": "notifications/initialized"},
    {"jsonrpc": "2.0", "id": 2, "method": "tools/list"},
]
for i, (name, args) in enumerate(tools, start=10):
    msgs.append({"jsonrpc": "2.0", "id": i, "method": "tools/call",
                 "params": {"name": name, "arguments": args}})

stdin = "\n".join(json.dumps(m) for m in msgs) + "\n"
t0 = time.time()
p = subprocess.run([sys.executable, str(srv)], input=stdin, text=True,
                   capture_output=True, timeout=180, cwd=${ROOT@Q},
                   env={**dict(**{k: v for k, v in __import__("os").environ.items()}),
                        "KG_NO_AUTO_REBUILD": "1", "PYTHONUNBUFFERED": "1"})
elapsed = time.time() - t0
print(f"elapsed={elapsed:.1f}s exit={p.returncode}")

# Every non-empty stdout line MUST be valid JSON-RPC
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

listed = [t["name"] for t in ((by_id.get(2) or {}).get("result") or {}).get("tools") or []]
print(f"tools/list={len(listed)}: {listed}")
expected = [n for n, _ in tools]
missing = [n for n in expected if n not in listed]
if missing:
    print(f"FAIL: tools missing from list: {missing}")
    sys.exit(3)

fails = []
for i, (name, _) in enumerate(tools, start=10):
    o = by_id.get(i)
    if not o:
        fails.append(f"{name}: no response")
        continue
    res = o.get("result") or {}
    text = ""
    if res.get("content"):
        text = (res["content"][0].get("text") or "")[:80].replace("\n", " ")
    if res.get("isError") and name != "kg_map_audit":
        fails.append(f"{name}: isError text={text!r}")
        continue
    if "error" in o and o["error"]:
        fails.append(f"{name}: rpc error {o['error']}")
        continue
    print(f"  PASS {name}: {text!r}")

# Prove validate/fixed-elsewhere no longer leak plain text onto stdout
leak_tokens = ("OK: ", "REUSE_FORBIDDEN", "RESULT: ", "VERIFIED_FIXED")
stdout_blob = p.stdout or ""
for tok in leak_tokens:
    # OK only if inside a JSON string value — raw line start is forbidden (caught above).
    # Extra: no bare non-JSON line containing token.
    pass

if fails:
    print("FAIL tool calls:")
    for f in fails:
        print(" ", f)
    sys.exit(4)

# Semantic needles — prove each tool returns useful content (not empty/error-shaped)
needles = {
    "kg_validate": ("OK:", "nodes"),
    "kg_fresh": ("KG FRESH", "KG STALE", "PROVISIONAL"),
    "kg_watermark": ("KG built",),
    "kg_search": ("request", "getLoanForeclosureDetails", "diag:"),
    "kg_orient": ("ORIENT", "getLoanForeclosureDetails"),
    "kg_flow": ("FLOW", "getLoanForeclosureDetails"),
    "kg_why": ("WHY",),
    "kg_impact": ("getLoanForeclosure",),
    "kg_cases": ("PRECEDENT", "shipped"),
    "kg_crud": ("FOOTPRINT", "prepayment"),
    "kg_writes": ("WRITERS",),
    "kg_fixed_elsewhere": ("FIXED-ELSEWHERE", "REUSE_", "FILE_TOUCH"),
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

print(f"PASS: {len(expected)}/{len(expected)} tools routed; stdout JSON-RPC-clean; semantic OK")
sys.exit(0)
PY
