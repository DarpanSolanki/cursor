"""Fail-closed check that every indexed error throw site still matches source.

An index that silently decays is worse than no index: the agent stops grepping and
starts trusting stale `file:line` answers. This re-reads each site the KG claims and
verifies the code is still thrown there.

A site is STALE when the file is gone, the line no longer holds a Novopay*Exception, or
it throws a different code. Branch mismatch is reported separately — the KG legitimately
holds sites read from a branch other than the current checkout, and that is not drift.

    python3 scripts/lib/error_index_drift_gate.py            # report
    python3 scripts/lib/error_index_drift_gate.py --strict   # exit 2 on any stale site
    python3 scripts/lib/error_index_drift_gate.py --sample 300
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
KG_DB = ROOT / "cursor-bundle" / "kg" / "data" / "kg.db"
EXC = re.compile(r"new\s+Novopay(?:Fatal|NonFatal)Exception\s*\(\s*([^),]+)")


def _branch(repo: str) -> str:
    try:
        return subprocess.check_output(
            ["git", "-C", str(ROOT / repo), "rev-parse", "--abbrev-ref", "HEAD"],
            text=True, stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return ""


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--sample", type=int, default=0)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    if not KG_DB.exists():
        print("error-index-drift: kg.db missing — run cursor-bundle/kg/bin/build.sh")
        return 1
    db = sqlite3.connect(f"file:{KG_DB}?mode=ro", uri=True)
    rows = db.execute(
        "SELECT dst_id,src,json FROM edges WHERE rel='throws'"
    ).fetchall()
    if args.sample:
        rows = rows[:: max(1, len(rows) // args.sample)]

    by_file: dict[str, list[tuple[str, int, dict]]] = defaultdict(list)
    for dst, src, ej in rows:
        code = dst.split(":", 1)[-1]
        path, _, line = src.rpartition(":")
        try:
            ln = int(line)
        except ValueError:
            continue
        by_file[path].append((code, ln, json.loads(ej) if ej else {}))

    checked = stale = offbranch = 0
    missing_files: list[str] = []
    bad: list[str] = []
    branch_cache: dict[str, str] = {}

    for path, sites in sorted(by_file.items()):
        f = ROOT / path
        if not f.exists():
            missing_files.append(path)
            stale += len(sites)
            checked += len(sites)
            continue
        try:
            lines = f.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            missing_files.append(path)
            stale += len(sites)
            checked += len(sites)
            continue
        for code, ln, meta in sites:
            checked += 1
            repo = meta.get("repo") or path.split("/", 1)[0]
            if repo not in branch_cache:
                branch_cache[repo] = _branch(repo)
            if meta.get("branch") and branch_cache[repo] and meta["branch"] != branch_cache[repo]:
                offbranch += 1
                continue
            # Exact line first: adjacent throws are common (`if (x) throw A; throw B;`)
            # and a widened window would match the neighbour and cry drift on a good index.
            exact = lines[ln - 1] if 0 < ln <= len(lines) else ""
            cands = [exact, "\n".join(lines[max(0, ln - 2): ln + 1])]
            toks = [m.group(1).strip() for w in cands for m in [EXC.search(w)] if m]
            if not toks:
                stale += 1
                bad.append(f"{path}:{ln} — no Novopay*Exception near this line (code {code})")
                continue
            lits = [m.group(1) for t in toks for m in [re.match(r'^"([^"]+)"$', t)] if m]
            if lits and code not in lits:
                stale += 1
                bad.append(f"{path}:{ln} — indexed {code}, source throws {lits[0]}")

    if args.json:
        print(json.dumps({"checked": checked, "stale": stale,
                          "off_branch": offbranch, "bad": bad[:50]}, indent=2))
        return 2 if (args.strict and stale) else 0

    print(f"error-index-drift: checked {checked} throw site(s)")
    print(f"  stale        : {stale}")
    print(f"  off-branch   : {offbranch}  (indexed from another checkout — not drift)")
    if missing_files:
        print(f"  missing files: {len(missing_files)}")
        for p in missing_files[:10]:
            print(f"      {p}")
    for b in bad[:15]:
        print(f"      {b}")
    if len(bad) > 15:
        print(f"      … +{len(bad) - 15} more")
    if stale:
        print("  -> rebuild the index: cursor-bundle/kg/bin/build.sh --force")
        if args.strict:
            print("error-index-drift: FAIL")
            return 2
    else:
        print("error-index-drift: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
