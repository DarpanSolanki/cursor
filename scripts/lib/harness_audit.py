#!/usr/bin/env python3
"""Audit the workspace harness itself: is every gate correct, needed, working, wired.

Checks
  tests     every scripts/lib/test_*.py passes
  hooks     hooks.json <-> settings.json in sync; every hook script exists
  registry  every registry case cmd points at a file that exists
  syntax    every shell/python artifact parses
  wiring    every *_gate / assert-* is invoked by ship-loop, smoke, or a hook
  orphans   scripts referenced nowhere (reported, never fatal)

Exit 0 = clean, 1 = hard failure, 2 = bad usage.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

WIRING_HOSTS = (
    "scripts/bin/ship-loop-gate.sh",
    "scripts/bin/workspace-smoke.sh",
    "scripts/bin/workspace-doctor.sh",
    "scripts/bin/smoke-workspace.sh",
    "scripts/bin/push-origin.sh",
    "scripts/bin/workspace-close.sh",
    ".cursor/hooks.json",
    "scripts/testing/registry.json",
    "scripts/lib/impact_tests.py",
    "scripts/testing/workspace_autopilot.py",
)

ORPHAN_EXEMPT_PREFIX = ("test_",)


def _run(cmd: list[str], cwd: Path = ROOT, timeout: int = 300) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True, timeout=timeout)


TIMING_SENSITIVE = ("test_kg_mcp_e2e.py",)


SLOW_TESTS = {"test_kg_mcp_e2e.py"}
_SKIP_SLOW = False


def check_tests() -> dict:
    tests = sorted(ROOT.glob("scripts/lib/test_*.py"))
    if _SKIP_SLOW:
        tests = [t for t in tests if t.name not in SLOW_TESTS]
    parallel = [t for t in tests if t.name not in TIMING_SENSITIVE]
    serial = [t for t in tests if t.name in TIMING_SENSITIVE]
    failures: list[dict] = []

    def one(t: Path) -> tuple[Path, subprocess.CompletedProcess | Exception]:
        try:
            return t, subprocess.run(
                [sys.executable, str(t)],
                cwd=str(ROOT),
                capture_output=True,
                text=True,
                timeout=300,
                env={
                    **__import__("os").environ,
                    "PYTHONPATH": str(ROOT / "scripts/lib"),
                    # This sweep audits CORRECTNESS. Latency budgets flake under any
                    # concurrent load; strict timing belongs to a dedicated perf run.
                    "KG_MCP_TEST_TIME_FACTOR": "10",
                },
            )
        except Exception as exc:  # noqa: BLE001
            return t, exc

    def record(t: Path, res) -> None:
        if isinstance(res, Exception):
            failures.append({"test": t.name, "error": str(res)})
        elif res.returncode != 0:
            tail = (res.stderr or res.stdout or "").strip().splitlines()[-3:]
            failures.append({"test": t.name, "tail": tail})

    with ThreadPoolExecutor(max_workers=8) as pool:
        for t, res in pool.map(one, parallel):
            record(t, res)

    for t in serial:
        record(*one(t))

    return {"name": "tests", "total": len(tests), "failures": failures, "ok": not failures}


def check_hooks() -> dict:
    errors: list[str] = []
    hooks_p = ROOT / ".cursor/hooks.json"
    settings_p = ROOT / ".cursor/settings.json"
    if not hooks_p.is_file():
        return {"name": "hooks", "ok": False, "errors": ["hooks.json missing"]}

    # Claude Code regenerates settings.json from hooks.json via sync-claude-hooks.py.
    # Cursor reads hooks.json directly — only run the sync check when that script exists.
    sync_py = ROOT / "scripts/bin/sync-claude-hooks.py"
    if sync_py.is_file():
        sync = _run([sys.executable, str(sync_py), "--check"])
        if sync.returncode != 0:
            errors.append(
                "settings.json stale vs hooks.json — tail hooks can be killed by a short "
                "dispatcher timeout. fix: python3 scripts/bin/sync-claude-hooks.py --write"
            )

    data = json.loads(hooks_p.read_text(encoding="utf-8"))
    for event, entries in (data.get("hooks") or {}).items():
        for e in entries:
            for tok in re.findall(r"(\.cursor/hooks/[\w./-]+)", e.get("command", "")):
                if not (ROOT / tok).is_file():
                    errors.append(f"{event}: hook script missing: {tok}")

    if settings_p.is_file():
        s = json.loads(settings_p.read_text(encoding="utf-8"))
        for tok in re.findall(r"(\.cursor/hooks/[\w./-]+)", json.dumps(s)):
            if not (ROOT / tok).is_file():
                errors.append(f"settings.json references missing hook: {tok}")

    return {"name": "hooks", "ok": not errors, "errors": errors}


def check_registry() -> dict:
    errors: list[str] = []
    reg_p = ROOT / "scripts/testing/registry.json"
    reg = json.loads(reg_p.read_text(encoding="utf-8"))
    for cid, case in reg.items():
        if cid.startswith("_") or not isinstance(case, dict):
            continue
        cmd = case.get("cmd") or ""
        for tok in re.findall(r"(scripts/[\w./-]+\.(?:sh|py|sql))", cmd):
            if not (ROOT / tok).is_file():
                errors.append(f"{cid}: cmd references missing file: {tok}")
    return {"name": "registry", "ok": not errors, "errors": errors, "cases": len(reg)}


def check_syntax() -> dict:
    errors: list[str] = []
    shells = list(ROOT.glob("scripts/**/*.sh")) + list(ROOT.glob(".cursor/hooks/*.sh"))
    pys = list(ROOT.glob("scripts/**/*.py")) + list(ROOT.glob(".cursor/hooks/*.py"))

    def bash_ok(f: Path) -> tuple[Path, bool]:
        return f, _run(["bash", "-n", str(f)], timeout=30).returncode == 0

    with ThreadPoolExecutor(max_workers=16) as pool:
        for f, ok in pool.map(bash_ok, shells):
            if not ok:
                errors.append(f"bash syntax: {f.relative_to(ROOT)}")

    import py_compile

    for f in pys:
        try:
            py_compile.compile(str(f), cfile=None, doraise=True)
        except py_compile.PyCompileError as exc:
            errors.append(f"python syntax: {f.relative_to(ROOT)} — {str(exc).splitlines()[0]}")
        except Exception:  # noqa: BLE001
            errors.append(f"python syntax: {f.relative_to(ROOT)}")

    return {"name": "syntax", "ok": not errors, "errors": errors, "scanned": len(shells) + len(pys)}


def _executables() -> dict[str, Path]:
    out: dict[str, Path] = {}
    for pat in ("scripts/**/*.sh", "scripts/**/*.py", ".cursor/hooks/*.sh", ".cursor/hooks/*.py"):
        for p in ROOT.glob(pat):
            if p.is_file():
                out[p.name] = p
    return out


def _tokens_for(name: str) -> tuple[str, ...]:
    """A .py artifact can be referenced by filename or by python module stem."""
    if name.endswith(".py"):
        return (name, name[:-3])
    return (name,)


def _mentions(text: str, name: str) -> bool:
    return any(
        re.search(rf"(?<![\w-]){re.escape(tok)}(?![\w-])", text) for tok in _tokens_for(name)
    )


def _reachable_from_hosts() -> set[str]:
    """Names reachable from a root host by following script->script references."""
    execs = _executables()
    if not execs:
        return set()

    token_owner: dict[str, str] = {}
    for name in execs:
        for tok in _tokens_for(name):
            token_owner[tok] = name
    alternation = "|".join(re.escape(t) for t in sorted(token_owner, key=len, reverse=True))
    scanner = re.compile(rf"(?<![\w-])({alternation})(?![\w-])")

    def refs(text: str) -> set[str]:
        return {token_owner[m.group(1)] for m in scanner.finditer(text)}

    seen: set[str] = set()
    frontier: list[str] = []
    for h in WIRING_HOSTS:
        p = ROOT / h
        if p.is_file():
            frontier.extend(refs(p.read_text(encoding="utf-8", errors="ignore")))

    while frontier:
        name = frontier.pop()
        if name in seen:
            continue
        seen.add(name)
        src = execs.get(name)
        if src:
            frontier.extend(refs(src.read_text(encoding="utf-8", errors="ignore")) - seen)
    return seen


def check_wiring() -> dict:
    reachable = _reachable_from_hosts()
    unwired: list[str] = []
    gates = sorted(
        set(ROOT.glob("scripts/lib/*_gate.py"))
        | set(ROOT.glob("scripts/bin/*-gate.py"))
        | set(ROOT.glob("scripts/bin/*-gate.sh"))
        | set(ROOT.glob("scripts/bin/assert-*.sh"))
        | set(ROOT.glob("scripts/bin/audit-*.sh"))
    )
    host_names = {Path(h).name for h in WIRING_HOSTS}
    for g in gates:
        if g.name.startswith("test_") or g.name in host_names:
            continue
        if g.name not in reachable:
            unwired.append(str(g.relative_to(ROOT)))
    return {"name": "wiring", "ok": not unwired, "unwired": unwired, "gates": len(gates)}


def check_orphans() -> dict:
    files = [
        p
        for pat in ("scripts/**/*", ".cursor/**/*", "cursor-bundle/**/*", "AGENTS.md")
        for p in ROOT.glob(pat)
        if p.is_file() and p.suffix in (".sh", ".py", ".json", ".md", ".mdc")
    ]
    candidates = sorted(set(ROOT.glob("scripts/bin/*.sh")) | set(ROOT.glob("scripts/bin/*.py")))
    candidates = [c for c in candidates if not c.name.startswith(ORPHAN_EXEMPT_PREFIX)]
    if not candidates:
        return {"name": "orphans", "ok": True, "orphans": []}

    token_owner: dict[str, str] = {}
    for c in candidates:
        for tok in _tokens_for(c.name):
            token_owner[tok] = c.name
    alternation = "|".join(re.escape(t) for t in sorted(token_owner, key=len, reverse=True))
    scanner = re.compile(rf"(?<![\w-])({alternation})(?![\w-])")

    referenced: set[str] = set()
    by_name = {c.name: c for c in candidates}
    for f in files:
        body = f.read_text(encoding="utf-8", errors="ignore")
        for m in scanner.finditer(body):
            owner = token_owner[m.group(1)]
            if by_name.get(owner) != f:
                referenced.add(owner)

    orphans = [str(c.relative_to(ROOT)) for c in candidates if c.name not in referenced]
    return {"name": "orphans", "ok": True, "orphans": orphans}


def check_path_leak() -> dict:
    lib = str(ROOT / "scripts" / "lib")
    if lib not in sys.path:
        sys.path.insert(0, lib)
    from path_leak_gate import check as _path_check

    bad = _path_check()
    return {
        "name": "path_leak",
        "ok": not bad,
        "hits": bad[:40],
        "total": len(bad),
        "errors": bad[:20],
    }


CHECKS = {
    "tests": check_tests,
    "hooks": check_hooks,
    "registry": check_registry,
    "syntax": check_syntax,
    "wiring": check_wiring,
    "orphans": check_orphans,
    "path_leak": check_path_leak,
}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--only", help="comma list: " + ",".join(CHECKS))
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--quick", action="store_true", help="skip syntax + tests")
    ap.add_argument(
        "--tests-fast",
        action="store_true",
        help="quick checks plus the self-tests, minus the slow MCP e2e — the ship-gate mode",
    )
    args = ap.parse_args()

    global _SKIP_SLOW
    _SKIP_SLOW = args.tests_fast

    names = list(CHECKS)
    if args.only:
        names = [n.strip() for n in args.only.split(",") if n.strip() in CHECKS]
        if not names:
            print("no valid check selected", file=sys.stderr)
            return 2
    elif args.tests_fast:
        names = ["hooks", "registry", "wiring", "orphans", "path_leak", "tests"]
    elif args.quick:
        names = ["hooks", "registry", "wiring", "orphans", "path_leak"]

    results = [CHECKS[n]() for n in names]
    hard_fail = any(not r["ok"] for r in results)

    if args.json:
        print(json.dumps({"ok": not hard_fail, "checks": results}, indent=2))
        return 1 if hard_fail else 0

    for r in results:
        mark = "✓" if r["ok"] else "✗"
        detail = ""
        if r["name"] == "tests":
            detail = f"{r['total'] - len(r['failures'])}/{r['total']} passing"
        elif r["name"] == "wiring":
            detail = f"{r['gates'] - len(r['unwired'])}/{r['gates']} wired"
        elif r["name"] == "registry":
            detail = f"{r['cases']} cases"
        elif r["name"] == "orphans":
            detail = f"{len(r['orphans'])} unreferenced"
        elif r["name"] == "syntax":
            detail = f"{r.get('scanned', 0)} files"
        elif r["name"] == "path_leak":
            detail = f"{r.get('total', 0)} hit(s)" if not r["ok"] else "clean"
        print(f"  {mark} harness/{r['name']} {detail}")
        for item in r.get("errors", []):
            print(f"      - {item}")
        for item in r.get("failures", []):
            print(f"      - {item.get('test')}: {item.get('tail') or item.get('error')}")
        for item in r.get("unwired", []):
            print(f"      - UNWIRED: {item}")
        for item in r.get("orphans", [])[:15]:
            print(f"      · orphan: {item}")

    return 1 if hard_fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
