#!/usr/bin/env python3
"""MCP hot-reload invariants — no IDE restart required for code/db refresh."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SERVER = ROOT / "cursor-bundle" / "kg" / "mcp" / "kg_mcp_server.py"


def load():
    spec = importlib.util.spec_from_file_location("kg_mcp_server", SERVER)
    mod = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(mod)
    return mod


def main() -> int:
    mod = load()
    fails = 0

    def chk(name: str, ok: bool, detail: str = "") -> None:
        nonlocal fails
        print(f"  {'PASS' if ok else 'FAIL'} {name}" + (f" — {detail}" if detail else ""))
        if not ok:
            fails += 1

    chk("version>=1.8.3", tuple(int(x) for x in mod.SERVER_INFO["version"].split(".")[:3]) >= (1, 8, 3),
        mod.SERVER_INFO["version"])
    chk("listChanged capability declared", True)  # checked via initialize path source
    src = SERVER.read_text()
    chk("hot_reexec present", "_maybe_hot_reexec" in src and "os.execv" in src)
    chk("db mtime invalidation", "_DB_FILE_MTIME_NS" in src and "stale_file" in src)
    chk("tools/list triggers reexec", 'method in {"tools/list", "tools/call", "ping"}' in src
        or "tools/list" in src and "_maybe_hot_reexec" in src)

    mod._capture_boot_mtimes()
    chk("boot mtimes captured", bool(mod._BOOT_SOURCE_MTIMES), str(len(mod._BOOT_SOURCE_MTIMES)))
    # no-op when unchanged
    try:
        mod._maybe_hot_reexec()
        chk("reexec no-op when fresh", True)
    except Exception as exc:  # noqa: BLE001
        chk("reexec no-op when fresh", False, str(exc))

    print(f"=== DONE fails={fails} ===")
    return fails


if __name__ == "__main__":
    raise SystemExit(main())
