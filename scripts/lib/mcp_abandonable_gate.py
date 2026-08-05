#!/usr/bin/env python3
"""Fail when code reachable from the MCP server can't be abandoned by its timeout.

`kg_mcp_server._run_timed` caps every tool with a daemon thread and `join(timeout)`, so it can
return TIMEOUT and walk away from slow work. That only holds if the work is actually abandonable.
A `with ThreadPoolExecutor(...)` inside it is not: `__exit__` calls `shutdown(wait=True)`, which
blocks on the worker the server just gave up on, and non-daemon pool threads then hold process
exit. That was the 2026-07-30 hang; it was reintroduced on 2026-08-06 by a speed change to
`_drift_check` and `prefetch_repo_states`, and no gate caught it.

Banned in the reachable set:
  - ThreadPoolExecutor / ProcessPoolExecutor
  - threading.Thread(...) without daemon=True
  - .join() with no timeout
  - shutdown(wait=True)

Comments are not evidence — this parses the AST, so the warning notes left in kg.py and
kg_composite.py naming the hang do not trip it.

    python3 scripts/lib/mcp_abandonable_gate.py check [--json]
"""
from __future__ import annotations

import argparse
import ast
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ENTRY = ROOT / "cursor-bundle" / "kg" / "mcp" / "kg_mcp_server.py"
SEARCH_DIRS = (
    ROOT / "cursor-bundle" / "kg" / "mcp",
    ROOT / "cursor-bundle" / "kg" / "bin",
    ROOT / "scripts" / "lib",
)
BANNED_POOLS = {"ThreadPoolExecutor", "ProcessPoolExecutor"}


def _module_file(name: str) -> Path | None:
    leaf = name.split(".")[-1]
    for d in SEARCH_DIRS:
        p = d / f"{leaf}.py"
        if p.is_file():
            return p
    return None


def reachable() -> list[Path]:
    """Modules the server can reach, following workspace-local imports from the entry point."""
    seen: set[Path] = set()
    out: list[Path] = []
    stack = [ENTRY] if ENTRY.is_file() else []
    while stack:
        f = stack.pop()
        if f in seen or not f.is_file():
            continue
        seen.add(f)
        out.append(f)
        try:
            tree = ast.parse(f.read_text(encoding="utf-8"))
        except (OSError, SyntaxError):
            continue
        for node in ast.walk(tree):
            names: list[str] = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                names = [node.module]
            for n in names:
                dep = _module_file(n)
                if dep and dep not in seen:
                    stack.append(dep)
    return out


def _name_of(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return ""


def scan_file(path: Path) -> list[dict]:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return []
    rel = str(path.relative_to(ROOT))
    found: list[dict] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        fname = _name_of(node.func)
        if fname in BANNED_POOLS:
            found.append({
                "file": rel, "line": node.lineno, "kind": fname,
                "why": "pool cannot be abandoned — __exit__ runs shutdown(wait=True)",
            })
        elif fname == "Thread":
            daemon = any(
                k.arg == "daemon" and getattr(k.value, "value", None) is True
                for k in node.keywords
            )
            if not daemon:
                found.append({
                    "file": rel, "line": node.lineno, "kind": "Thread(daemon=False)",
                    "why": "non-daemon thread blocks process exit after TIMEOUT",
                })
        elif fname == "join" and not node.args and not node.keywords:
            found.append({
                "file": rel, "line": node.lineno, "kind": "join() without timeout",
                "why": "unbounded join defeats the wall-clock cap",
            })
        elif fname == "shutdown":
            if any(k.arg == "wait" and getattr(k.value, "value", None) is True for k in node.keywords):
                found.append({
                    "file": rel, "line": node.lineno, "kind": "shutdown(wait=True)",
                    "why": "blocks on work the server already abandoned",
                })
    return found


def scan() -> list[dict]:
    out: list[dict] = []
    for f in reachable():
        out.extend(scan_file(f))
    return sorted(out, key=lambda d: (d["file"], d["line"]))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", nargs="?", default="check", choices=["check", "files"])
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    if args.cmd == "files":
        for f in reachable():
            print(f.relative_to(ROOT))
        return 0

    findings = scan()
    if args.json:
        print(json.dumps({"findings": findings, "count": len(findings)}, indent=2))
        return 1 if findings else 0
    n = len(reachable())
    if not findings:
        print(f"mcp-abandonable gate: OK — {n} MCP-reachable module(s), all abandonable")
        return 0
    print(f"mcp-abandonable gate: FAIL — {len(findings)} blocking construct(s) in the MCP path")
    for f in findings:
        print(f"  {f['file']}:{f['line']}  {f['kind']}")
        print(f"      {f['why']}")
    print("\nkg_mcp_server._run_timed abandons slow work with a daemon thread + join(timeout).")
    print("Anything it calls must be abandonable too — see the 2026-07-30 hang note in that file.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
