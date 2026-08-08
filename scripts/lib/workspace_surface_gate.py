#!/usr/bin/env python3
"""Workspace agent-surface maturity gate (fail-closed).

Promotes the exhaustive-audit checklist into a standing gate so Cursor↔Claude
routing, live knowledge-answer wiring, and KG_FIRST cannot regress silently.

  python3 scripts/lib/workspace_surface_gate.py
  python3 scripts/lib/workspace_surface_gate.py --json

Exit 0 = clean, 1 = gap/fail.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _errors() -> list[str]:
    errs: list[str] = []

    hooks_p = ROOT / ".cursor/hooks.json"
    if not hooks_p.is_file():
        return ["hooks.json missing"]
    hooks = json.loads(hooks_p.read_text(encoding="utf-8")).get("hooks") or {}

    pre = hooks.get("preToolUse") or []
    ka_wired = any("knowledge-answer.py" in (e.get("command") or "") for e in pre)
    if not ka_wired:
        errs.append("hooks.json preToolUse must wire knowledge-answer.py (Grep|Glob|Read)")

    settings_p = ROOT / ".cursor/settings.json"
    if settings_p.is_file():
        s = settings_p.read_text(encoding="utf-8")
        for bad in ("claude-hook-dispatch.py", "rule-router.py"):
            if bad in s:
                errs.append(f"settings.json must not reference missing Claude hook {bad}")

    ka = (ROOT / ".cursor/hooks/knowledge-answer.py").read_text(encoding="utf-8")
    for needle, label in (
        ("TARGETED_BUDGET_S", "shared TARGETED_BUDGET_S"),
        ("def _run_kg", "inline _run_kg"),
        ('"permission": "deny"', "hard-deny Grep when KG answered"),
        ("_emit_deny", "deny emitter"),
    ):
        if needle not in ka:
            errs.append(f"knowledge-answer.py missing {label}")

    ar = (ROOT / "scripts/testing/agent_router.py").read_text(encoding="utf-8")
    block = ar.split("KG_FIRST", 1)[1][:800] if "KG_FIRST" in ar else ""
    if "kg_error" not in block:
        errs.append("agent_router KG_FIRST missing kg_error")
    if "kg_schema" not in block:
        errs.append("agent_router KG_FIRST missing kg_schema")

    # CLI help parser must see more than the old double-space subset
    parity = (ROOT / "scripts/lib/test_kg_mcp_cli_parity.py").read_text(encoding="utf-8")
    if r"^\s{2}([a-z][a-z-]+)\s{2,}" in parity and "re.split" not in parity:
        errs.append("test_kg_mcp_cli_parity still uses weak double-space-only CLI parser")

    return errs


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    errs = _errors()
    if args.json:
        print(json.dumps({"ok": not errs, "errors": errs}, indent=2))
    elif errs:
        print("workspace_surface_gate: FAIL")
        for e in errs:
            print(f"  - {e}")
    else:
        print("workspace_surface_gate: PASS")
    return 1 if errs else 0


if __name__ == "__main__":
    raise SystemExit(main())
