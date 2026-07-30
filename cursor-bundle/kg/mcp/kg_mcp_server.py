#!/usr/bin/env python3
"""trustt-kg MCP server — in-process SQLite (read-only). No kg.py subprocess spawn."""
from __future__ import annotations

import contextlib
import io
import json
import os
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]  # sliProd
BIN = ROOT / "cursor-bundle" / "kg" / "bin"
sys.path.insert(0, str(BIN))
sys.path.insert(0, str(ROOT / "scripts" / "lib"))

import kg as kg_mod  # noqa: E402

MAX_CHARS = 10_000
TRUNC_MARK = "\n\n… [truncated — refine query / narrower args; max 10000 chars] …\n"
SERVER_INFO = {"name": "trustt-kg", "version": "1.5.0"}
PROTOCOL = "2024-11-05"

_MONEY_LOOKUP_TOOLS = frozenset(
    {"kg_orient", "kg_flow", "kg_why", "kg_impact", "kg_crud", "kg_writes", "kg_cases"}
)

TOOLS = {
    "kg_orient": {
        "description": "Orient on an apiName/request: flow spine + silent branches + precedents. Prefer for LOOKUP before grepping. Pass require_repo+require_branch for fail-closed train match.",
        "args": ["orient"],
        "schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "apiName / request / partial id"},
                "require_repo": {"type": "string"},
                "require_branch": {"type": "string"},
            },
            "required": ["query"],
        },
    },
    "kg_flow": {
        "description": "Ordered processor chain (flow spine) + DB footprint for a Request. Optional require_repo/require_branch.",
        "args": ["flow"],
        "schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "require_repo": {"type": "string"},
                "require_branch": {"type": "string"},
            },
            "required": ["query"],
        },
    },
    "kg_why": {
        "description": "Failure-mode / silent decision-point catalog. Optional require_repo/require_branch.",
        "args": ["why"],
        "schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "require_repo": {"type": "string"},
                "require_branch": {"type": "string"},
            },
            "required": ["query"],
        },
    },
    "kg_impact": {
        "description": "Reverse blast radius — who reaches this node. Supports Class#method. Pass require_repo+require_branch before money claims.",
        "args": ["impact"],
        "schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "depth": {"type": "integer", "description": "optional --depth N"},
                "require_repo": {"type": "string"},
                "require_branch": {"type": "string"},
            },
            "required": ["query"],
        },
    },
    "kg_align": {
        "description": "Fail-closed: KG watermark must match expected repo@branch (or domain@train) before money impact analysis. Exit mismatch = do not trust flow/impact for that train.",
        "args": ["align"],
        "schema": {
            "type": "object",
            "properties": {
                "repo": {"type": "string", "description": "e.g. trustt-platform-accounting"},
                "branch": {"type": "string", "description": "e.g. mfi_integration_v3.4.2.4"},
                "domain": {"type": "string", "description": "dfc|dpi|accounting|foreclosure|…"},
                "train": {"type": "string", "description": "mfi_integration_vX.Y.Z for --domain"},
            },
        },
    },
    "kg_fixed_elsewhere": {
        "description": "Verified higher-branch fixes + file-touch candidates (read-only). Use before proposing ports.",
        "args": ["fixed-elsewhere"],
        "schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "repo": {"type": "string"},
                "base": {"type": "string", "description": "reported/base branch"},
            },
            "required": ["query"],
        },
    },
    "kg_validate": {
        "description": "KG integrity + min nodes/edges check.",
        "args": ["validate"],
        "schema": {"type": "object", "properties": {}},
    },
    "kg_watermark": {
        "description": "Per-repo branch@sha the KG was built from vs live HEAD.",
        "args": ["watermark"],
        "schema": {"type": "object", "properties": {}},
    },
    "kg_fresh": {
        "description": "One-line verdict: is KG branch-correct for current checkout?",
        "args": ["fresh"],
        "schema": {"type": "object", "properties": {}},
    },
    "kg_search": {
        "description": "Full-text node search (FTS5). Smallest query first.",
        "args": ["search"],
        "schema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
    },
    "kg_cases": {
        "description": "Shipped-fix precedents (CHANGELOG cases) for a flow/table.",
        "args": ["cases"],
        "schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "require_repo": {"type": "string"},
                "require_branch": {"type": "string"},
            },
        },
    },
    "kg_crud": {
        "description": "DB footprint of a flow (reads/writes/deletes).",
        "args": ["crud"],
        "schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "require_repo": {"type": "string"},
                "require_branch": {"type": "string"},
            },
            "required": ["query"],
        },
    },
    "kg_writes": {
        "description": "Who writes a table.",
        "args": ["writes"],
        "schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "require_repo": {"type": "string"},
                "require_branch": {"type": "string"},
            },
            "required": ["query"],
        },
    },
    "kg_map_audit": {
        "description": "LMS change_test_map vs KG audit — CRITICAL + soft gaps (mismatch/bare/orphan/missing). Run before money ship / after map edits.",
        "args": [],
        "schema": {
            "type": "object",
            "properties": {
                "fail_on_mismatch": {
                    "type": "boolean",
                    "description": "If true, mark isError when CRITICAL or soft_gap_count > 0",
                }
            },
        },
    },
    "mcp_auth": {
        "description": "No-op for trustt-kg (local stdio SQLite). Always succeeds — no OAuth/credentials required.",
        "args": [],
        "schema": {"type": "object", "properties": {}, "additionalProperties": False},
    },
    "workspace_status": {
        "description": "Workspace health snapshot: KG freshness/watermark, ship gate status, stack-doctor summary, flow coverage, backlog SU, speed, waivers.",
        "args": [],
        "schema": {"type": "object", "properties": {}},
    },
    "ship_plan": {
        "description": "Current pending selection plan: ordered cases, WHY, tier, planned wall, NOT-COVERED.",
        "args": [],
        "schema": {"type": "object", "properties": {"repo": {"type": "string"}}},
    },
}

_DB = None
os.environ.setdefault("KG_NO_AUTO_REBUILD", "1")


def _db():
    global _DB
    if _DB is None:
        _DB = kg_mod.conn(readonly=True)
    return _DB


def truncate(s: str) -> str:
    if len(s) <= MAX_CHARS:
        return s
    return s[: MAX_CHARS - len(TRUNC_MARK)] + TRUNC_MARK


_HEADER_CACHE = None  # (mono, str)

def _header() -> str:
    global _HEADER_CACHE
    import time as _time
    now = _time.monotonic()
    if _HEADER_CACHE and (now - _HEADER_CACHE[0]) < 5.0:
        return _HEADER_CACHE[1]
    try:
        from kg_state_banner import provenance_header

        h = provenance_header()
    except Exception as exc:  # noqa: BLE001
        h = f"[KG @? set=? WIP:?] (header failed: {exc})"
    _HEADER_CACHE = (now, h)
    return h


def run_kg(argv: list[str]) -> str:
    cmd = argv[0]
    args = argv[1:]
    if cmd not in kg_mod.CMDS:
        return f"ERROR: unknown kg cmd {cmd}"
    # validate still shells to kg_validate for integrity PRAGMA (rare)
    if cmd == "validate":
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            try:
                kg_mod.CMDS[cmd](_db(), args)
            except SystemExit as e:
                if e.code not in (0, None):
                    return truncate((_header() + "\n" + buf.getvalue()).strip() or f"ERROR: validate exit {e.code}")
        body = buf.getvalue().strip()
        return truncate(_header() + "\n" + (body or "OK"))
    if cmd == "fixed-elsewhere":
        # keeps branch_train subprocess (rare path)
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            try:
                kg_mod.CMDS[cmd](_db(), args)
            except SystemExit:
                pass
        body = buf.getvalue().strip()
        return truncate(_header() + "\n" + (body or "(empty)"))

    buf = io.StringIO()
    t0 = time.perf_counter()
    rc = 0
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        try:
            kg_mod.CMDS[cmd](_db(), args)
        except SystemExit as e:
            rc = int(e.code) if isinstance(e.code, int) else 1
    ms = (time.perf_counter() - t0) * 1000
    body = buf.getvalue().strip() or "(empty)"
    if rc:
        body = f"(exit={rc})\n" + body
    if os.environ.get("KG_MCP_TIMING"):
        body = f"(mcp_inproc_ms={ms:.1f})\n" + body
    if body.startswith("[KG @"):
        return truncate(body)
    return truncate(_header() + "\n" + body)


def tool_argv(name: str, arguments: dict) -> list[str]:
    """Build kg.py argv for a tool. Only forward args declared on the tool schema."""
    meta = TOOLS[name]
    argv = list(meta["args"])
    props = (meta.get("schema") or {}).get("properties") or {}
    if "query" in props:
        q = arguments.get("query")
        if q is not None and str(q).strip():
            argv.append(str(q).strip())
    if name == "kg_impact" and arguments.get("depth") is not None:
        argv.extend(["--depth", str(arguments["depth"])])
    if name in _MONEY_LOOKUP_TOOLS:
        rr = arguments.get("require_repo") or os.environ.get("KG_ALIGN_REPO")
        rb = arguments.get("require_branch") or os.environ.get("KG_ALIGN_BRANCH")
        if rr and rb:
            argv.extend(["--require-repo", str(rr), "--require-branch", str(rb)])
    if name == "kg_align":
        if arguments.get("repo"):
            argv.extend(["--repo", str(arguments["repo"])])
        if arguments.get("branch"):
            argv.extend(["--branch", str(arguments["branch"])])
        if arguments.get("domain"):
            argv.extend(["--domain", str(arguments["domain"])])
        if arguments.get("train"):
            argv.extend(["--train", str(arguments["train"])])
    if name == "kg_fixed_elsewhere":
        if arguments.get("repo"):
            argv.extend(["--repo", str(arguments["repo"])])
        if arguments.get("base"):
            argv.extend(["--base", str(arguments["base"])])
    return argv


def _read_json(path: Path) -> dict:
    if not path.is_file():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}


def _run_cmd(cmd: list[str], *, timeout_s: int = 8) -> tuple[int, str]:
    try:
        cp = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s, check=False)
        return cp.returncode, (cp.stdout or cp.stderr or "").strip()
    except Exception as exc:  # noqa: BLE001
        return 1, f"error: {exc}"


def _flow_coverage_pct() -> str:
    fp = ROOT / "scripts/testing/flow_coverage.json"
    data = _read_json(fp)
    flows = data.get("flows") or []
    yes = 0
    den = 0
    for row in flows:
        scope = str(row.get("scope") or "").lower()
        if scope == "out":
            continue
        den += 1
        if str(row.get("status") or "").upper() == "YES":
            yes += 1
    if den <= 0:
        return "0/0 (0%)"
    pct = round((yes * 100.0) / den, 1)
    return f"{yes}/{den} ({pct}%)"


def _backlog_su_open() -> int:
    bp = ROOT / "scripts/workspace-backlog.json"
    data = _read_json(bp)
    n = 0
    for item in data.get("items") or []:
        iid = str(item.get("id") or "")
        st = str(item.get("status") or "").lower()
        if iid.startswith("SU-") and st in {"open", "todo", "pending", "in_progress"}:
            n += 1
    return n


def _speed_p50_from_self_report() -> dict:
    fp = ROOT / "cursor-bundle/memory/SELF-REPORT.md"
    if not fp.is_file():
        return {}
    out: dict[str, str] = {}
    for line in fp.read_text(encoding="utf-8", errors="ignore").splitlines():
        s = line.strip()
        if not s.startswith("- `") or "p50=" not in s:
            continue
        try:
            k = s.split("`", 2)[1]
            p50 = s.split("p50=", 1)[1].split()[0]
            out[k] = p50
        except Exception:
            continue
    return out


def _active_waivers() -> list[dict]:
    wp = ROOT / ".cursor/.impact-tests-human-waiver.json"
    if not wp.is_file():
        return []
    data = _read_json(wp)
    return [data] if data else []


def _stack_doctor_summary() -> dict:
    # 12s was too tight (workspace_status regularly timed out → false "ok:false").
    rc, out = _run_cmd(["bash", str(ROOT / "scripts/bin/stack-doctor.sh"), "--json"], timeout_s=45)
    if not out:
        return {"ok": False, "error": "no output"}
    try:
        j = json.loads(out)
        j["rc"] = rc
        return j
    except Exception:
        return {"ok": rc == 0, "raw": out[:600]}


def _workspace_status_payload() -> dict:
    pending = _read_json(ROOT / ".cursor/.pending-ship-work.json")
    passed = _read_json(ROOT / ".cursor/.ship-loop-passed.json")
    impact_ran = _read_json(ROOT / ".cursor/.impact-tests-ran.json")
    close_state = _read_json(ROOT / ".cursor/.autopilot-state.json")

    kg_fresh = run_kg(["fresh"])
    kg_watermark = run_kg(["watermark"])
    return {
        "provenance": _header(),
        "kg": {"fresh": kg_fresh, "watermark": kg_watermark},
        "ship": {
            "pending_repos": pending.get("repos") or [],
            "pending_tier": pending.get("tier"),
            "pending_head_shas": pending.get("repo_head_shas") or {},
            "gate_passed_at": passed.get("passed_at"),
            "gate_repo_head_shas": passed.get("repo_head_shas") or {},
            "impact_ran_at": impact_ran.get("ran_at"),
            "last_close_result": close_state.get("last_end_result") or close_state.get("last_result"),
        },
        "stack_doctor": _stack_doctor_summary(),
        "flow_coverage": _flow_coverage_pct(),
        "backlog_su_open": _backlog_su_open(),
        "speed_p50": _speed_p50_from_self_report(),
        "active_waivers": _active_waivers(),
    }


def _map_audit_payload(arguments: dict | None = None) -> dict:
    """LMS change_test_map vs KG — wraps scripts/lib/lms_flow_map_audit.py.

    Always reload map modules so Cursor's long-lived MCP process picks up
    change_test_map / audit edits without a full server restart.
    """
    arguments = arguments or {}
    try:
        import importlib

        import change_test_map as ctm_mod  # noqa: WPS433
        import lms_flow_map_audit as audit_mod  # noqa: WPS433

        importlib.reload(ctm_mod)
        ctm_mod.load_map.cache_clear()
        if hasattr(ctm_mod, "known_batch_apis"):
            ctm_mod.known_batch_apis.cache_clear()
        audit_mod = importlib.reload(audit_mod)
        result = audit_mod.audit()
    except Exception as exc:  # noqa: BLE001
        return {"error": f"map audit failed: {exc}", "verdict": "ERROR"}
    result["provenance"] = _header()
    result["fail_on_mismatch"] = bool(arguments.get("fail_on_mismatch"))
    return result


def _ship_plan_payload(arguments: dict) -> dict:
    try:
        from impact_tests import build_plan  # noqa: WPS433
        from chain_budgets import plan_wall_s  # noqa: WPS433
    except Exception as exc:  # noqa: BLE001
        return {"error": f"import failed: {exc}"}

    repo = str(arguments.get("repo") or "").strip()
    pending = _read_json(ROOT / ".cursor/.pending-ship-work.json")
    rel_paths = list(pending.get("files") or [])
    if repo:
        rel_paths = [p for p in rel_paths if p.startswith(f"{repo}/") or p == repo]
    plan = build_plan(from_pending=not rel_paths, paths=(rel_paths or None), shipped_only=True)
    ordered = list(plan.get("ordered_cases") or [])
    why_lines = list(plan.get("why_lines") or [])
    why = {}
    for line in why_lines:
        if ": " in line:
            c, w = line.split(": ", 1)
            why[c] = w
    return {
        "provenance": _header(),
        "tier": pending.get("tier") or ("money" if plan.get("invariants_mandatory") else "service"),
        "files": rel_paths or list(plan.get("files") or []),
        "ordered_cases": [{"case": c, "why": why.get(c, "")} for c in ordered],
        "planned_wall_s": int(plan_wall_s(ordered)),
        "selection_tier_stats": plan.get("selection_tier_stats") or {},
        "not_covered": plan.get("not_covered_blocking") or plan.get("not_covered_flows") or [],
    }


def tools_list_payload():
    return {
        "tools": [
            {"name": name, "description": meta["description"], "inputSchema": meta["schema"]}
            for name, meta in TOOLS.items()
        ]
    }


def handle(msg: dict) -> dict | None:
    mid = msg.get("id")
    method = msg.get("method")
    params = msg.get("params") or {}

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": mid,
            "result": {
                "protocolVersion": PROTOCOL,
                "capabilities": {"tools": {}},
                "serverInfo": SERVER_INFO,
            },
        }
    if method == "notifications/initialized":
        return None
    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": mid, "result": tools_list_payload()}
    if method == "tools/call":
        name = params.get("name")
        arguments = params.get("arguments") or {}
        if name not in TOOLS:
            return {
                "jsonrpc": "2.0",
                "id": mid,
                "result": {"content": [{"type": "text", "text": f"Unknown tool: {name}"}], "isError": True},
            }
        if name == "workspace_status":
            text = truncate(_header() + "\n" + json.dumps(_workspace_status_payload(), indent=2))
            is_err = False
        elif name == "ship_plan":
            text = truncate(_header() + "\n" + json.dumps(_ship_plan_payload(arguments), indent=2))
            is_err = False
        elif name == "kg_map_audit":
            payload = _map_audit_payload(arguments)
            text = truncate(_header() + "\n" + json.dumps(payload, indent=2))
            is_err = bool(arguments.get("fail_on_mismatch")) and (
                int(payload.get("critical_mismatch_count") or 0) > 0
                or int(payload.get("soft_gap_count") or 0) > 0
                or str(payload.get("verdict") or "") in {"FAIL", "ERROR"}
            )
        elif name == "mcp_auth":
            text = truncate(
                _header()
                + "\n"
                + json.dumps(
                    {
                        "ok": True,
                        "auth_required": False,
                        "message": "trustt-kg is local stdio over SQLite — no authentication.",
                    },
                    indent=2,
                )
            )
            is_err = False
        else:
            text = run_kg(tool_argv(name, arguments))
            is_err = False
        out: dict = {"jsonrpc": "2.0", "id": mid, "result": {"content": [{"type": "text", "text": text}]}}
        if is_err:
            out["result"]["isError"] = True
        return out
    if method == "ping":
        return {"jsonrpc": "2.0", "id": mid, "result": {}}
    if mid is None:
        return None
    return {"jsonrpc": "2.0", "id": mid, "error": {"code": -32601, "message": f"Method not found: {method}"}}


def main() -> None:
    # MCP stdio: ONLY JSON-RPC on fd1. Subprocess/print leaks (kg_validate "OK: N nodes",
    # branch_train "REUSE_FORBIDDEN") previously corrupted the stream → Cursor
    # "Unexpected token … is not valid JSON" → serverStatus=error.
    mcp_fd = os.dup(1)
    os.dup2(2, 1)  # Python stdout / child inherit → stderr
    mcp_out = os.fdopen(mcp_fd, "w", buffering=1, encoding="utf-8", errors="replace")

    # Lazy DB: do not block initialize / tools/list on SQLite open.
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            continue
        resp = handle(msg)
        if resp is not None:
            mcp_out.write(json.dumps(resp, ensure_ascii=False) + "\n")
            mcp_out.flush()


if __name__ == "__main__":
    main()
