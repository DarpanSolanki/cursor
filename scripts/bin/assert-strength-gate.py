#!/usr/bin/env python3
"""Fail when a money-path audit gains a NEW presence-only assert.

Gate D-acceptance already forbids presence-only DB asserts, but nothing enforced
it in the audit code itself. `iad_column_audit` declared "ALL physical columns
audited fail-closed" while checking `start_date` as merely non-null, and checked
the installment FK for existence without ownership — so SHG child rows shipped
with a stale FK and merged windows and the suite stayed green.

Existing sites are grandfathered in `.assert-strength-grandfather` so this can be
adopted without a big-bang rewrite; the count may only shrink. Anything new fails.

  assert-strength-gate.py              # check, exit 1 on new weak asserts
  assert-strength-gate.py --baseline   # rewrite the grandfather file
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GRANDFATHER = ROOT / "scripts" / "testing" / ".assert-strength-grandfather"
SCAN_ROOTS = ["scripts/testing", "scripts/dpic", "scripts/dcf_sanity", "scripts/disbursement"]

PATTERNS = [
    (re.compile(r'_ck\(\s*"[^"]*",\s*bool\([a-z_]+\)'), "presence-only-bool"),
    (re.compile(r'"non-null[^"]*"'), "presence-only-nonnull"),
    (re.compile(r'expect=\s*"?exists'), "existence-only-fk"),
    (re.compile(r'level\s*=\s*"WARN"'), "warn-not-fail"),
]


def scan() -> dict[str, int]:
    """file::pattern -> occurrence count. Counting matters: keying on the pair alone
    lets a second weak assert hide inside an already-grandfathered file."""
    found: dict[str, int] = {}
    for root in SCAN_ROOTS:
        base = ROOT / root
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*.py")):
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            rel = path.relative_to(ROOT)
            for line in text.splitlines():
                for rx, label in PATTERNS:
                    if rx.search(line):
                        found[f"{rel}::{label}"] = found.get(f"{rel}::{label}", 0) + 1
    return found


def load_baseline() -> dict[str, int]:
    if not GRANDFATHER.is_file():
        return {}
    out: dict[str, int] = {}
    for ln in GRANDFATHER.read_text(encoding="utf-8").splitlines():
        ln = ln.strip()
        if not ln or ln.startswith("#"):
            continue
        key, _, count = ln.rpartition(" ")
        out[key or ln] = int(count) if count.isdigit() else 1
    return out


def write_baseline(found: dict[str, int]) -> None:
    GRANDFATHER.parent.mkdir(parents=True, exist_ok=True)
    GRANDFATHER.write_text(
        "# file::pattern pairs grandfathered from the SHG accrual false-positive audit.\n"
        "# This list may only SHRINK. New entries mean a new weak assert — fix the\n"
        "# assert instead of extending this file.\n"
        + "\n".join(f"{k} {v}" for k, v in sorted(found.items())) + "\n",
        encoding="utf-8",
    )


def main() -> int:
    found = scan()
    if "--baseline" in sys.argv:
        write_baseline(found)
        print(f"assert-strength: baseline written "
              f"({sum(found.values())} weak assert(s) across {len(found)} site(s))")
        return 0

    baseline = load_baseline()
    worse = sorted(k for k, n in found.items() if n > baseline.get(k, 0))
    if worse:
        print("assert-strength FAIL — new presence-only / existence-only asserts:")
        for k in worse:
            print(f"  - {k}: {baseline.get(k, 0)} -> {found[k]}")
        print("Fix: assert the VALUE (or FK ownership), not merely presence.")
        return 1
    healed = sum(baseline.values()) - sum(found.values())
    if healed > 0:
        write_baseline(found)
        print(f"assert-strength: {healed} weak assert(s) strengthened — baseline tightened")
    print(f"assert-strength OK ({sum(found.values())} known weak assert(s), none new)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
