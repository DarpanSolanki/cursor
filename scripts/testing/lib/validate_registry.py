#!/usr/bin/env python3
"""Validate scripts/testing/registry.json structure and correlator references."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any

REGISTRY = Path(__file__).resolve().parent.parent / "registry.json"
VAR_RE = re.compile(r"\$\{([A-Z_][A-Z0-9_]*)\}")
# ntest injects these per run, so they are resolvable without a _correlators entry.
RUNTIME_CORRELATORS = {"STAN"}


def _collect_vars(obj: Any, found: set[str]) -> None:
    if isinstance(obj, dict):
        for v in obj.values():
            _collect_vars(v, found)
    elif isinstance(obj, list):
        for v in obj:
            _collect_vars(v, found)
    elif isinstance(obj, str):
        found.update(VAR_RE.findall(obj))


def validate_registry(path: Path | None = None) -> list[str]:
    path = path or REGISTRY
    errors: list[str] = []
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as ex:
        return [f"invalid JSON: {ex}"]

    correlators = set((raw.get("_correlators") or {}).keys()) | RUNTIME_CORRELATORS
    cases = {k: v for k, v in raw.items() if not k.startswith("_")}

    for cid, case in cases.items():
        if not isinstance(case, dict):
            errors.append(f"{cid}: case must be an object")
            continue
        t = case.get("type")
        if t not in ("api", "batch", "flow", "health"):
            errors.append(f"{cid}: unknown type {t!r}")
            continue
        if t == "flow":
            if not case.get("cmd"):
                errors.append(f"{cid}: flow missing cmd")
        elif t == "health":
            if not case.get("service"):
                errors.append(f"{cid}: health missing service")
        else:
            for key in ("service", "api"):
                if not case.get(key):
                    errors.append(f"{cid}: {t} missing {key}")
            if "expect" not in case:
                errors.append(f"{cid}: {t} missing expect")

        used: set[str] = set()
        _collect_vars(case.get("request"), used)
        _collect_vars(case.get("expect"), used)
        _collect_vars(case.get("defaults"), used)
        defaults = set((case.get("defaults") or {}).keys())
        for var in used:
            if var not in correlators and var not in defaults:
                errors.append(f"{cid}: unresolved correlator ${{{var}}}")

        fid = case.get("fidelity")
        if fid is not None:
            if not isinstance(fid, dict):
                errors.append(f"{cid}: fidelity must be an object")
            else:
                entry = fid.get("entry")
                if entry not in (
                    None,
                    "batch_api",
                    "http_api",
                    "orch_request",
                    "kafka",
                    "mixed",
                    "sim",
                ):
                    errors.append(f"{cid}: fidelity.entry invalid {entry!r}")

    # Harness fidelity (money runtime masks) — hard errors only; missing block = warn via gate CLI
    try:
        import sys as _sys

        _sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "lib"))
        from harness_fidelity_gate import check as fidelity_check  # type: ignore

        ferrs, _fwarns = fidelity_check(hard=False)
        errors.extend(ferrs)
    except Exception as ex:  # noqa: BLE001 — validate must still run if gate import fails
        errors.append(f"harness_fidelity_gate import/check failed: {ex}")

    return errors


def main() -> int:
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else REGISTRY
    errs = validate_registry(path)
    if errs:
        print(f"registry INVALID ({len(errs)} issue(s)):", file=sys.stderr)
        for e in errs:
            print(f"  - {e}", file=sys.stderr)
        return 1
    n = len([k for k in json.loads(path.read_text()) if not k.startswith("_")])
    print(f"registry OK — {n} case(s), correlators consistent")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
