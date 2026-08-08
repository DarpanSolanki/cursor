#!/usr/bin/env python3
"""trustt-kg MCP server — in-process SQLite (read-only). No kg.py subprocess spawn."""
from __future__ import annotations

import contextlib
import io
import json
import os
import sqlite3
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[3]  # sliProd
BIN = ROOT / "cursor-bundle" / "kg" / "bin"
sys.path.insert(0, str(BIN))
sys.path.insert(0, str(ROOT / "scripts" / "lib"))

import kg as kg_mod  # noqa: E402

MAX_CHARS = int(os.environ.get("KG_MCP_MAX_CHARS", "24000"))
TRUNC_MARK = "\n\n… [truncated — refine query / use brief=true / KG_MCP_MAX_CHARS; showed {shown}/{total} chars] …\n"
SERVER_INFO = {"name": "trustt-kg", "version": "1.9.3"}
PROTOCOL = "2024-11-05"
_SERVER_FILE = Path(__file__).resolve()
# Hot-reload without IDE restart: re-exec when this server (or kg.py) changes on disk.
_BOOT_SOURCE_MTIMES: dict[str, int] = {}

# Per-tool wall-clock caps. Reads ≤2s; heavy ≤15s; kg_enhance explicit.
# CRITICAL: _run_timed must NOT shutdown(wait=True) after timeout (that was the hang).
TOOL_TIMEOUT_S: dict[str, float] = {
    "mcp_auth": 1.0,
    "kg_watermark": 2.0,
    "kg_search": 2.0,
    "kg_concept": 2.0,
    "kg_schema": 8.0,  # schema_oracle + column_binding (live DB / Java)
    "kg_flow": 2.0,
    "kg_crud": 2.0,
    "kg_writes": 2.0,
    "kg_reads": 2.0,
    "kg_cases": 2.0,
    "kg_node": 2.0,
    "kg_error": 8.0,  # was missing → default 2s; Redis template path can exceed
    "kg_align": 3.0,
    "kg_orient": 5.0,
    "kg_why": 5.0,
    "kg_impact": 5.0,
    "kg_doctor": 8.0,
    "workspace_status": 5.0,
    "ship_plan": 8.0,
    "kg_map_audit": 15.0,
    "kg_fixed_elsewhere": 15.0,
    "kg_enhance": 45.0,  # explicit heavy — was 180; still returns TIMEOUT payload
}
DEFAULT_TOOL_TIMEOUT_S = 2.0

_MONEY_LOOKUP_TOOLS = frozenset(
    {
        "kg_orient",
        "kg_flow",
        "kg_why",
        "kg_error",
        "kg_impact",
        "kg_crud",
        "kg_writes",
        "kg_reads",
        "kg_cases",
    }
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
                "brief": {
                    "type": "boolean",
                    "description": "Cap auto silent-surfaces in why (default true — avoids MCP truncation).",
                },
                "full": {
                    "type": "boolean",
                    "description": "If true, disable brief cap (may truncate at KG_MCP_MAX_CHARS).",
                },
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
                "auto_cap": {
                    "type": "integer",
                    "description": "Max auto silent-surface diags (default 10). Use 0 for curated-only.",
                },
            },
            "required": ["query"],
        },
    },
    "kg_error": {
        "description": "START HERE for any error code (132168, LOS-0016, COL-012): every source-derived throw site with file:line and branch, the ExecutionContext keys the message template needs, the runtime template, and prior shipped fixes. Replaces grepping for the code.",
        "args": ["error"],
        "schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "error code, e.g. 132168"},
                "no_template": {
                    "type": "boolean",
                    "description": "Skip the runtime (Redis) template lookup — source-derived facts only.",
                },
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
        "description": "Fail-closed: KG watermark must match expected repo@branch (or domain@train) before money impact analysis. isError when misaligned.",
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
        "description": (
            "Verified higher-branch fixes + file-touch candidates (read-only). "
            "Watermark-keyed cache; STALE when KG watermark drifts. "
            "Default fetch_if_stale=false (opt-in git fetch)."
        ),
        "args": ["fixed-elsewhere"],
        "schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "repo": {"type": "string"},
                "base": {"type": "string", "description": "reported/base branch"},
                "fetch_if_stale": {
                    "type": "boolean",
                    "description": "Auto git fetch upstream when refs stale (default false).",
                },
            },
            "required": ["query"],
        },
    },
    "kg_watermark": {
        "description": "Per-repo branch@sha the KG was built from vs live HEAD.",
        "args": ["watermark"],
        "schema": {"type": "object", "properties": {}},
    },
    "kg_search": {
        "description": (
            "Full-text node search (FTS5). Smallest query first. "
            "Numeric/ACCT_* queries also deepen error-code precedents (ex-kg_error). "
            "Prefers semantics/framework kinds (entity, txn_type, framework, …) when present."
        ),
        "args": ["search"],
        "schema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
    },
    "kg_concept": {
        "description": (
            "DOMAIN SEMANTICS + FRAMEWORK bone lookup (what is X / how substrate behaves). "
            "Kinds: entity, txn_type, gl_mech, batch_cfg, redis_key, framework, server. "
            "LEAN extension — use when kg_search IDs are not enough; returns purpose/note/UNKNOWN/src."
        ),
        "args": ["concept"],
        "schema": {"type": "object", "properties": {"query": {"type": "string"}}, "required": ["query"]},
    },
    "kg_schema": {
        "description": (
            "Resolve a table or table.column before asserts/SQL/docs (40-knowledge-upkeep). "
            "Structure + code readers/writers + train-local column flags. Live oracle — not KG-index-only."
        ),
        "args": ["schema"],
        "schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "table or table.column — e.g. loan_account or loan_account.loan_status",
                },
            },
            "required": ["query"],
        },
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
    "kg_reads": {
        "description": "Who reads a table (complement to kg_writes).",
        "args": ["reads"],
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
    "kg_node": {
        "description": "Inspect a KG node by id or label — JSON + inbound/outbound edges.",
        "args": ["node"],
        "schema": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    },
    "kg_doctor": {
        "description": (
            "KG health (replaces kg_validate + kg_fresh): validate OK, fresh/PROVISIONAL, "
            "node/edge counts, source staleness, watermark drift, CRUD coverage."
        ),
        "args": ["doctor"],
        "schema": {"type": "object", "properties": {}},
    },
    "kg_enhance": {
        "description": (
            "Scoped train sync + KG rebuild. If train is set: runs sync-branches "
            "(scoped by sync_domain) then kg-switch + validate + fresh. "
            "Without train: kg-switch only for current checkout. "
            "kg_align is detect-only — it does not checkout branches."
        ),
        "args": [],
        "schema": {
            "type": "object",
            "properties": {
                "force": {
                    "type": "boolean",
                    "description": "Pass --force to kg-switch (full rebuild even if cache hit).",
                },
                "train": {
                    "type": "string",
                    "description": "Integration branch to checkout (e.g. mfi_integration_v3.4.2.4 or 3.4.2.4).",
                },
                "sync_domain": {
                    "type": "string",
                    "description": "Scoped sync domain (default accounting). See train_banner.DOMAIN_REPOS.",
                },
                "dry_run": {
                    "type": "boolean",
                    "description": "If true with train: SYNC_DRY_RUN=1 on sync-branches (smoke/tests).",
                },
                "align_repo": {"type": "string"},
                "align_branch": {"type": "string"},
            },
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
        "description": "Workspace health snapshot (KG fresh/watermark, ship gate, cached stack-doctor). Fast path — no 45s block.",
        "args": [],
        "schema": {"type": "object", "properties": {}},
    },
    "ship_plan": {
        "description": (
            "Advisory pending test selection (ordered cases, WHY, tier, wall). "
            "Does NOT own push-origin close — that is ship_push_gate "
            "(workspace-safe / knowledge HEAD skips sticky money close)."
        ),
        "args": [],
        "schema": {"type": "object", "properties": {"repo": {"type": "string"}}},
    },
}

_DB = None
_DB_WATERMARK: str | None = None
_DB_FILE_MTIME_NS: int | None = None
os.environ.setdefault("KG_NO_AUTO_REBUILD", "1")

_STACK_DOCTOR_CACHE: tuple[float, dict] | None = None
_STACK_DOCTOR_TTL_S = 90.0
_STACK_DOCTOR_TIMEOUT_S = 12

_KG_DB_PATH = Path(getattr(kg_mod, "DB", str(ROOT / "cursor-bundle" / "kg" / "data" / "kg.db")))


def _file_mtime_ns(path: Path) -> int:
    try:
        return path.stat().st_mtime_ns
    except OSError:
        return 0


def _tracked_source_paths() -> list[Path]:
    return [
        _SERVER_FILE,
        BIN / "kg.py",
        BIN / "kg_state_banner.py",
        ROOT / "scripts" / "lib" / "train_sync.py",
    ]


def _capture_boot_mtimes() -> None:
    global _BOOT_SOURCE_MTIMES
    _BOOT_SOURCE_MTIMES = {str(p): _file_mtime_ns(p) for p in _tracked_source_paths()}


def _stdin_has_pending() -> bool:
    """True when more JSON-RPC lines are already buffered (bulk smoke / piped batch)."""
    try:
        peek = getattr(sys.stdin, "peek", None)
        if callable(peek):
            return bool(peek(1))
    except Exception:  # noqa: BLE001
        return False
    return False


def _maybe_hot_reexec() -> None:
    """If MCP server / kg CLI sources changed, replace this process in-place.

    Cursor keeps the same stdio pipes — no IDE restart. Next tools/list + calls
    see the new SERVER_INFO version and tool schemas.

    Never reexec while more stdin lines are buffered: Python may have read the
    whole pipe into the TextIO buffer, and os.execv inherits an fd already at
    EOF — the child would drop every remaining tools/call (kg-mcp-smoke saw
    only kg_doctor succeed).
    """
    if os.environ.get("KG_MCP_NO_HOT_REEXEC") == "1":
        return
    if not _BOOT_SOURCE_MTIMES:
        _capture_boot_mtimes()
        return
    for path in _tracked_source_paths():
        key = str(path)
        now = _file_mtime_ns(path)
        prev = _BOOT_SOURCE_MTIMES.get(key, 0)
        if now != prev:
            if _stdin_has_pending():
                return
            # Re-open sqlite handles would be stale; exec clears process state.
            os.execv(sys.executable, [sys.executable, str(_SERVER_FILE), *sys.argv[1:]])


def _db():
    global _DB, _DB_WATERMARK, _DB_FILE_MTIME_NS, _HEADER_CACHE
    wm = kg_mod._load_watermark() or {}
    built = str(wm.get("built_at") or "")
    db_mtime = _file_mtime_ns(_KG_DB_PATH)
    stale_wm = bool(_DB is not None and built and built != _DB_WATERMARK)
    stale_file = bool(_DB is not None and _DB_FILE_MTIME_NS is not None and db_mtime != _DB_FILE_MTIME_NS)
    if stale_wm or stale_file:
        try:
            if _DB is not None:
                _DB.close()
        except Exception:  # noqa: BLE001
            pass
        _DB = None
        _HEADER_CACHE = None
    if _DB is None:
        # Tool bodies run on daemon threads (_run_timed). Default sqlite
        # check_same_thread=True breaks when a later worker reuses a conn opened
        # on a prior worker (or after TIMEOUT abandon). _TOOL_SERIAL keeps access
        # single-flight; check_same_thread=False allows cross-worker reuse.
        uri = f"file:{kg_mod.DB}?mode=ro"
        c = sqlite3.connect(uri, uri=True, check_same_thread=False)
        c.row_factory = sqlite3.Row
        _DB = c
        _DB_WATERMARK = built
        _DB_FILE_MTIME_NS = db_mtime
    return _DB


def truncate(s: str) -> str:
    total = len(s)
    if total <= MAX_CHARS:
        return s
    mark = TRUNC_MARK.format(shown=MAX_CHARS - 80, total=total)
    return s[: MAX_CHARS - len(mark)] + mark


_HEADER_CACHE = None  # (mono, str)


def _header() -> str:
    global _HEADER_CACHE
    now = time.monotonic()
    if _HEADER_CACHE and (now - _HEADER_CACHE[0]) < 5.0:
        return _HEADER_CACHE[1]
    try:
        from kg_state_banner import provenance_header

        h = provenance_header()
    except Exception as exc:  # noqa: BLE001
        h = f"[KG @? set=? WIP:?] (header failed: {exc})"
    _HEADER_CACHE = (now, h)
    return h


def _infer_is_error(text: str, rc: int = 0) -> bool:
    """Fail-closed: align/misaligned and non-zero kg exits surface as MCP isError."""
    if rc != 0:
        return True
    if "MISALIGNED" in text or "ALIGN REQUIRED" in text:
        return True
    if text.startswith("(exit=") and not text.startswith("(exit=0)"):
        return True
    return False


def run_kg(argv: list[str]) -> tuple[str, int]:
    """Run kg command in-process. Returns (body_text, exit_code)."""
    cmd = argv[0]
    args = argv[1:]
    if cmd not in kg_mod.CMDS:
        return f"ERROR: unknown kg cmd {cmd}", 1
    if cmd == "validate":
        buf = io.StringIO()
        rc = 0
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            try:
                kg_mod.CMDS[cmd](_db(), args)
            except SystemExit as e:
                rc = int(e.code) if isinstance(e.code, int) else 1
        body = buf.getvalue().strip()
        if rc:
            return truncate((_header() + "\n" + body).strip() or f"ERROR: validate exit {rc}"), rc
        return truncate(_header() + "\n" + (body or "OK")), 0
    if cmd == "fixed-elsewhere":
        buf = io.StringIO()
        rc = 0
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            try:
                kg_mod.CMDS[cmd](_db(), args)
            except SystemExit as e:
                rc = int(e.code) if isinstance(e.code, int) else 1
        body = buf.getvalue().strip()
        return truncate(_header() + "\n" + (body or "(empty)")), rc

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
        return truncate(body), rc
    return truncate(_header() + "\n" + body), rc


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
    if name == "kg_orient":
        if arguments.get("full"):
            pass  # brief disabled
        elif arguments.get("brief", True):
            argv.append("--brief")
    if name == "kg_error" and arguments.get("no_template"):
        argv.append("--no-template")
    if name == "kg_why":
        cap = arguments.get("auto_cap")
        if cap is None:
            cap = 10
        argv.extend(["--auto-cap", str(int(cap))])
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
        # Default false — network fetch was the 10s sink; opt-in only.
        if arguments.get("fetch_if_stale", False):
            argv.append("--fetch-if-stale")
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
    except subprocess.TimeoutExpired:
        return 124, f"timeout after {timeout_s}s"
    except Exception as exc:  # noqa: BLE001
        return 1, f"error: {exc}"


_TOOL_SERIAL = threading.Lock()  # one tool at a time — abandoned workers must not race _DB


def _run_timed(label: str, fn: Callable[[], Any], timeout_s: float) -> Any:
    """Wall-clock cap that returns promptly on breach.

    Hang root-cause (2026-07-30):
    1) ``with ThreadPoolExecutor`` → ``shutdown(wait=True)`` waited for the timed-out
       worker (CallMcpTool blocked for remaining work, e.g. kg-switch ≤170s).
    2) Non-daemon pool threads also blocked **process exit** after TIMEOUT return.

    Fix: daemon ``threading.Thread`` + ``join(timeout)`` — return/TIMEOUT without waiting
    for the worker; drop shared SQLite handle (close=False) so a later call opens a
    fresh conn without joining the abandoned worker (close=True deadlocked).
    """
    box: dict[str, Any] = {}

    def _runner() -> None:
        try:
            box["value"] = fn()
        except BaseException as exc:  # noqa: BLE001 — deliver to caller
            box["exc"] = exc

    thr = threading.Thread(target=_runner, name=f"mcp-{label}", daemon=True)
    thr.start()
    thr.join(timeout=timeout_s)
    if thr.is_alive():
        try:
            _invalidate_db_cache(close=False)
        except Exception:
            pass
        raise TimeoutError(f"{label} exceeded {timeout_s}s")
    if "exc" in box:
        raise box["exc"]
    if "value" not in box:
        raise TimeoutError(f"{label} exceeded {timeout_s}s (no result)")
    return box["value"]


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
    """Cached, short-timeout stack-doctor — must not block workspace_status for 45s."""
    global _STACK_DOCTOR_CACHE
    now = time.monotonic()
    if _STACK_DOCTOR_CACHE and (now - _STACK_DOCTOR_CACHE[0]) < _STACK_DOCTOR_TTL_S:
        cached = dict(_STACK_DOCTOR_CACHE[1])
        cached["cached"] = True
        return cached

    rc, out = _run_cmd(
        ["bash", str(ROOT / "scripts/bin/stack-doctor.sh"), "--json"],
        timeout_s=_STACK_DOCTOR_TIMEOUT_S,
    )
    if rc == 124:
        result = {
            "ok": None,
            "skipped": True,
            "reason": f"stack-doctor timeout ({_STACK_DOCTOR_TIMEOUT_S}s) — run scripts/bin/stack-doctor.sh manually",
        }
        _STACK_DOCTOR_CACHE = (now, result)
        return dict(result)
    if not out:
        return {"ok": False, "error": "no output"}
    try:
        j = json.loads(out)
        j["rc"] = rc
        j["cached"] = False
        _STACK_DOCTOR_CACHE = (now, j)
        return j
    except Exception:
        return {"ok": rc == 0, "raw": out[:600], "cached": False}


def _kg_fresh_summary() -> str:
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        try:
            kg_mod.cmd_fresh(_db(), [])
        except SystemExit:
            pass
    for line in buf.getvalue().splitlines():
        s = line.strip()
        if s and "KG " in s:
            return s
    return buf.getvalue().strip().split("\n")[-1][:300] if buf.getvalue().strip() else "?"


def _kg_watermark_summary() -> str:
    wm = kg_mod._load_watermark() or {}
    acc = (wm.get("repos") or {}).get("trustt-platform-accounting") or {}
    built = wm.get("built_at") or "?"
    if acc:
        return f"built={built} accounting={acc.get('branch','?')}@{acc.get('sha','?')}"
    return f"built={built} repos={len(wm.get('repos') or {})}"


def _invalidate_db_cache(*, close: bool = True) -> None:
    """Drop cached SQLite handle. On tool TIMEOUT use close=False — closing a conn
    still in use by an abandoned daemon worker can deadlock the main thread."""
    global _DB, _HEADER_CACHE, _DB_WATERMARK, _DB_FILE_MTIME_NS
    if close:
        try:
            if _DB is not None:
                _DB.close()
        except Exception:  # noqa: BLE001
            pass
    _DB = None
    _HEADER_CACHE = None
    _DB_WATERMARK = None
    _DB_FILE_MTIME_NS = None


def _kg_enhance_payload(arguments: dict) -> dict:
    force = bool(arguments.get("force"))
    dry_run = bool(arguments.get("dry_run"))
    align_repo = str(arguments.get("align_repo") or "").strip()
    align_branch = str(arguments.get("align_branch") or "").strip()
    train_raw = str(arguments.get("train") or "").strip()
    sync_domain = str(arguments.get("sync_domain") or "accounting").strip().lower()

    result: dict[str, Any] = {"provenance": _header()}

    if train_raw:
        try:
            from train_sync import normalize_train, primary_repo, live_branch, run_sync  # noqa: WPS433

            train = normalize_train(train_raw)
            repo = primary_repo(sync_domain)
            live = live_branch(repo)
            result["train"] = train
            result["sync_domain"] = sync_domain
            result["primary_repo"] = repo
            result["live_branch_before"] = live
            if live and live != train:
                sync_rc, sync_out = run_sync(train, sync_domain, dry_run=dry_run)
                result["sync_branches_rc"] = sync_rc
                result["sync_dry_run"] = dry_run
                result["sync_tail"] = sync_out.splitlines()[-8:] if sync_out else []
                if sync_rc != 0:
                    result["error"] = f"sync-branches failed (rc={sync_rc})"
                    return result
            else:
                result["sync_skipped"] = True
                result["sync_reason"] = "already on train" if live == train else "live branch unknown"
        except Exception as exc:  # noqa: BLE001
            result["error"] = f"train sync failed: {exc}"
            return result

    switch = ROOT / "scripts" / "bin" / "kg-switch.sh"
    cmd = ["bash", str(switch)]
    if force:
        cmd.append("--force")
    rc, out = _run_cmd(cmd, timeout_s=int(TOOL_TIMEOUT_S.get("kg_enhance", 45) - 5))
    _invalidate_db_cache()
    result["kg_switch_rc"] = rc
    result["kg_switch_tail"] = (out.splitlines()[-6:] if out else [])
    if rc != 0:
        result["error"] = f"kg-switch failed (rc={rc})"
        return result
    val_text, val_rc = run_kg(["validate"])
    fresh_text, fresh_rc = run_kg(["fresh"])
    result["validate_rc"] = val_rc
    result["validate"] = val_text.split("\n", 1)[-1][:500] if val_text else ""
    result["fresh_rc"] = fresh_rc
    result["fresh"] = fresh_text.split("\n", 1)[-1][:300] if fresh_text else ""
    if align_repo and align_branch:
        align_text, align_rc = run_kg(
            ["align", "--repo", align_repo, "--branch", align_branch]
        )
        result["align_rc"] = align_rc
        result["align"] = align_text.split("\n", 1)[-1][:300] if align_text else ""
    result["ok"] = val_rc == 0 and fresh_rc == 0
    return result


_WS_STATUS_CACHE: dict[str, Any] | None = None
_WS_STATUS_CACHE_AT = 0.0
_WS_STATUS_CACHE_KEY = ""
_MAP_AUDIT_CACHE: dict[str, Any] | None = None
_MAP_AUDIT_CACHE_AT = 0.0
_MAP_AUDIT_CACHE_KEY = ""
_STATUS_TTL_S = 20.0
_MAP_AUDIT_TTL_S = 60.0
_FIXED_ELSEWHERE_MEM: dict[str, str] = {}
_FIXED_CACHE_DIR = ROOT / "cursor-bundle" / "kg" / "cache" / "fixed_elsewhere"


def _wm_cache_key() -> str:
    wm = kg_mod._load_watermark() or {}
    return str(wm.get("branch_set_key") or wm.get("built_at") or "none")


def _fixed_elsewhere_lookup(arguments: dict) -> tuple[str, str | None]:
    """Return (HIT|STALE|MISS, body_or_None). Never caches fetch_if_stale=true."""
    q = str(arguments.get("query") or "").strip()
    if not q:
        return "MISS", None
    if bool(arguments.get("fetch_if_stale", False)):
        return "MISS", None
    repo = str(arguments.get("repo") or "").strip()
    base = str(arguments.get("base") or "").strip()
    key = f"{_wm_cache_key()}|{q}|{repo}|{base}"
    if key in _FIXED_ELSEWHERE_MEM:
        return "HIT", _FIXED_ELSEWHERE_MEM[key]
    _FIXED_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    import hashlib

    h = hashlib.sha1(key.encode()).hexdigest()
    fp = _FIXED_CACHE_DIR / f"{h}.txt"
    meta = _FIXED_CACHE_DIR / f"{h}.meta"
    if fp.is_file() and meta.is_file():
        try:
            stamped = meta.read_text(encoding="utf-8").strip()
            body = fp.read_text(encoding="utf-8")
            if stamped != _wm_cache_key():
                return "STALE", body
            _FIXED_ELSEWHERE_MEM[key] = body
            return "HIT", body
        except OSError:
            return "MISS", None
    return "MISS", None


def _fixed_elsewhere_store(arguments: dict, body: str) -> None:
    q = str(arguments.get("query") or "").strip()
    if not q or arguments.get("fetch_if_stale"):
        return
    repo = str(arguments.get("repo") or "").strip()
    base = str(arguments.get("base") or "").strip()
    key = f"{_wm_cache_key()}|{q}|{repo}|{base}"
    lines = body.splitlines()
    if lines and lines[0].startswith("[KG @"):
        body = "\n".join(lines[1:]).lstrip("\n")
    # drop prior cache= lines
    body = "\n".join(ln for ln in body.splitlines() if not ln.startswith("cache="))
    _FIXED_ELSEWHERE_MEM[key] = body
    try:
        _FIXED_CACHE_DIR.mkdir(parents=True, exist_ok=True)
        import hashlib

        h = hashlib.sha1(key.encode()).hexdigest()
        (_FIXED_CACHE_DIR / f"{h}.txt").write_text(body, encoding="utf-8")
        (_FIXED_CACHE_DIR / f"{h}.meta").write_text(_wm_cache_key(), encoding="utf-8")
    except OSError:
        pass


def _mtime_key(*paths: Path) -> str:
    parts = []
    for p in paths:
        try:
            parts.append(f"{p.name}:{p.stat().st_mtime_ns}")
        except OSError:
            parts.append(f"{p.name}:missing")
    return "|".join(parts)


def _workspace_status_payload() -> dict:
    global _WS_STATUS_CACHE, _WS_STATUS_CACHE_AT, _WS_STATUS_CACHE_KEY
    now = time.monotonic()
    key = _mtime_key(
        ROOT / ".cursor/.pending-ship-work.json",
        ROOT / ".cursor/.ship-loop-passed.json",
        ROOT / ".cursor/.impact-tests-ran.json",
        ROOT / ".cursor/.autopilot-state.json",
        ROOT / "cursor-bundle/kg/data/stats.json",
        ROOT / "scripts/testing/flow_coverage.json",
    )
    if (
        _WS_STATUS_CACHE is not None
        and key == _WS_STATUS_CACHE_KEY
        and (now - _WS_STATUS_CACHE_AT) < _STATUS_TTL_S
    ):
        out = dict(_WS_STATUS_CACHE)
        out["cache"] = {"hit": True, "ttl_s": _STATUS_TTL_S, "key": key[:48]}
        return out
    pending = _read_json(ROOT / ".cursor/.pending-ship-work.json")
    passed = _read_json(ROOT / ".cursor/.ship-loop-passed.json")
    impact_ran = _read_json(ROOT / ".cursor/.impact-tests-ran.json")
    close_state = _read_json(ROOT / ".cursor/.autopilot-state.json")

    out = {
        "provenance": _header(),
        "kg": {"fresh": _kg_fresh_summary(), "watermark": _kg_watermark_summary()},
        "ship": {
            "pending_repos": pending.get("repos") or [],
            "pending_tier": pending.get("tier"),
            "pending_head_shas": pending.get("repo_head_shas") or {},
            "gate_passed_at": passed.get("passed_at"),
            "gate_note": passed.get("note"),
            "gate_repo_head_shas": passed.get("repo_head_shas") or {},
            "impact_ran_at": impact_ran.get("ran_at"),
            "last_close_result": close_state.get("last_end_result") or close_state.get("last_result"),
        },
        "stack_doctor": _stack_doctor_summary(),
        "flow_coverage": _flow_coverage_pct(),
        "backlog_su_open": _backlog_su_open(),
        "speed_p50": _speed_p50_from_self_report(),
        "active_waivers": _active_waivers(),
        "cache": {"hit": False, "ttl_s": _STATUS_TTL_S, "key": key[:48]},
    }
    _WS_STATUS_CACHE = dict(out)
    _WS_STATUS_CACHE_AT = now
    _WS_STATUS_CACHE_KEY = key
    return out


def _map_audit_payload(arguments: dict | None = None) -> dict:
    global _MAP_AUDIT_CACHE, _MAP_AUDIT_CACHE_AT, _MAP_AUDIT_CACHE_KEY
    arguments = arguments or {}
    fail = bool(arguments.get("fail_on_mismatch"))
    key = _mtime_key(
        ROOT / "scripts/lib/change_test_map.json",
        ROOT / "scripts/lib/lms_flow_map_audit.py",
        ROOT / "cursor-bundle/kg/data/kg.db",
        ROOT / "scripts/testing/registry.json",
    ) + f"|fail={fail}"
    now = time.monotonic()
    if (
        _MAP_AUDIT_CACHE is not None
        and key == _MAP_AUDIT_CACHE_KEY
        and (now - _MAP_AUDIT_CACHE_AT) < _MAP_AUDIT_TTL_S
    ):
        result = dict(_MAP_AUDIT_CACHE)
        result["cache"] = {"hit": True, "ttl_s": _MAP_AUDIT_TTL_S}
        result["provenance"] = _header()
        result["fail_on_mismatch"] = fail
        return result
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
    result["fail_on_mismatch"] = fail
    result["cache"] = {"hit": False, "ttl_s": _MAP_AUDIT_TTL_S}
    _MAP_AUDIT_CACHE = dict(result)
    _MAP_AUDIT_CACHE_AT = now
    _MAP_AUDIT_CACHE_KEY = key
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
    red = list(plan.get("red_cases") or [])
    red_ids = {r.get("case") for r in red}
    ordered_out = []
    for c in ordered:
        row = {"case": c, "why": why.get(c, "")}
        if c in red_ids:
            meta = next((r for r in red if r.get("case") == c), {})
            row["status"] = "RED"
            row["must_fix_first"] = True
            row["last_result"] = meta.get("result")
            row["last_at"] = meta.get("at")
        ordered_out.append(row)
    return {
        "provenance": _header(),
        "tier": pending.get("tier") or ("money" if plan.get("invariants_mandatory") else "service"),
        "files": rel_paths or list(plan.get("files") or []),
        "ordered_cases": ordered_out,
        "red_cases": red,
        "telemetry_red_block": bool(red),
        "planned_wall_s": int(plan_wall_s(ordered)),
        "selection_tier_stats": plan.get("selection_tier_stats") or {},
        "not_covered": plan.get("not_covered_blocking") or plan.get("not_covered_flows") or [],
        "path_not_covered": plan.get("path_not_covered") or [],
    }


def tools_list_payload():
    return {
        "tools": [
            {"name": name, "description": meta["description"], "inputSchema": meta["schema"]}
            for name, meta in TOOLS.items()
        ]
    }


def _dispatch_tool(name: str, arguments: dict) -> tuple[str, bool]:
    """Returns (text, isError)."""
    timeout_s = TOOL_TIMEOUT_S.get(name, DEFAULT_TOOL_TIMEOUT_S)

    def _work() -> tuple[str, bool]:
        if name == "workspace_status":
            payload = _workspace_status_payload()
            return truncate(_header() + "\n" + json.dumps(payload, indent=2)), False
        if name == "ship_plan":
            payload = _ship_plan_payload(arguments)
            if payload.get("error"):
                return truncate(_header() + "\n" + json.dumps(payload, indent=2)), True
            return truncate(_header() + "\n" + json.dumps(payload, indent=2)), False
        if name == "kg_map_audit":
            payload = _map_audit_payload(arguments)
            is_err = bool(arguments.get("fail_on_mismatch")) and (
                int(payload.get("critical_mismatch_count") or 0) > 0
                or int(payload.get("soft_gap_count") or 0) > 0
                or str(payload.get("verdict") or "") in {"FAIL", "ERROR"}
            )
            return truncate(_header() + "\n" + json.dumps(payload, indent=2)), is_err
        if name == "kg_enhance":
            payload = _kg_enhance_payload(arguments)
            is_err = not payload.get("ok") and bool(payload.get("error"))
            return truncate(_header() + "\n" + json.dumps(payload, indent=2)), is_err
        if name == "mcp_auth":
            # Instant — no provenance header (was ~0.7s cold WRAPPER cost).
            return (
                json.dumps(
                    {
                        "ok": True,
                        "auth_required": False,
                        "message": "trustt-kg is local stdio over SQLite — no authentication.",
                    }
                ),
                False,
            )
        if name == "kg_fixed_elsewhere":
            kind, cached_body = _fixed_elsewhere_lookup(arguments)
            if kind == "HIT" and cached_body is not None:
                return truncate(_header() + "\n" + f"cache=HIT\n{cached_body}"), False
            text, rc = run_kg(tool_argv(name, arguments))
            _fixed_elsewhere_store(arguments, text)
            prefix = "cache=MISS\n"
            if kind == "STALE":
                prefix = "STALE: watermark drifted — recomputed\n"
            # prepend cache status inside body after header
            lines = text.splitlines()
            if lines and lines[0].startswith("[KG @"):
                text = lines[0] + "\n" + prefix + "\n".join(lines[1:])
            else:
                text = truncate(_header() + "\n" + prefix + text)
            return text, bool(rc and rc not in (0, 3))
        text, rc = run_kg(tool_argv(name, arguments))
        return text, _infer_is_error(text, rc)

    # Optional env override for one tool (tests): KG_MCP_TOOL_TIMEOUT_<NAME>
    env_key = f"KG_MCP_TOOL_TIMEOUT_{name.upper()}"
    if os.environ.get(env_key):
        try:
            timeout_s = float(os.environ[env_key])
        except ValueError:
            pass
    if os.environ.get("KG_MCP_TOOL_TIMEOUT"):
        try:
            timeout_s = min(timeout_s, float(os.environ["KG_MCP_TOOL_TIMEOUT"]))
        except ValueError:
            pass

    acquired = _TOOL_SERIAL.acquire(timeout=timeout_s + 1.0)
    if not acquired:
        payload = {
            "ok": False,
            "status": "TIMEOUT",
            "partial": True,
            "tool": name,
            "budget_s": timeout_s,
            "error": "tool serial lock busy — prior abandoned worker still running",
        }
        return json.dumps(payload, indent=2), True
    try:
        return _run_timed(name, _work, timeout_s)
    except TimeoutError as exc:
        # Avoid _header()/_db() here — abandoned worker may still touch SQLite.
        payload = {
            "ok": False,
            "status": "TIMEOUT",
            "partial": True,
            "stale": name in {"kg_fixed_elsewhere", "kg_map_audit", "kg_enhance", "kg_doctor"},
            "tool": name,
            "budget_s": timeout_s,
            "error": str(exc),
            "hint": "narrow query / use cache / avoid kg_enhance during rebuild; retry",
            "provenance": (_HEADER_CACHE[1] if _HEADER_CACHE else "[KG @? TIMEOUT]"),
        }
        return json.dumps(payload, indent=2), True
    finally:
        _TOOL_SERIAL.release()


def handle(msg: dict) -> dict | None:
    mid = msg.get("id")
    method = msg.get("method")
    params = msg.get("params") or {}

    # Pick up MCP/tool code changes without requiring an IDE restart.
    if method in {"tools/list", "tools/call", "ping"}:
        _maybe_hot_reexec()

    if method == "initialize":
        _capture_boot_mtimes()
        return {
            "jsonrpc": "2.0",
            "id": mid,
            "result": {
                "protocolVersion": PROTOCOL,
                "capabilities": {"tools": {"listChanged": True}},
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
        text, is_err = _dispatch_tool(name, arguments)
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
    _capture_boot_mtimes()
    mcp_fd = os.dup(1)
    os.dup2(2, 1)
    mcp_out = os.fdopen(mcp_fd, "w", buffering=1, encoding="utf-8", errors="replace")

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
