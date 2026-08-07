#!/usr/bin/env python3
"""The production EOD/BOD job list, read from the bank's Autosys sheet.

Everything else in this workspace infers what runs from code. This is the other direction:
the schedule production actually executes, with the sequence numbers operations relies on.
`data/Trustt- HDFC EOD BOD.xlsx`, sheet `All Autosys Jobs`.

All 110 jobs resolve against the platform API map, which is the useful cross-check — the map
is not missing anything production runs, and the sheet names nothing the platform cannot serve.

Parsed with the stdlib. openpyxl is not a workspace dependency and a 2.6MB workbook with 381
sheets is not worth adding one for.

    autosys_jobs.py                 the full list, grouped
    autosys_jobs.py --repo accounting
    autosys_jobs.py --json
"""
from __future__ import annotations

import argparse
import collections
import json
import pathlib
import zipfile
from xml.etree import ElementTree as ET

ROOT = pathlib.Path(__file__).resolve().parents[2]
BOOK = ROOT / "data" / "Trustt- HDFC EOD BOD.xlsx"
OUT = ROOT / "cursor-bundle" / "flow-test" / "autosys_jobs.jsonl"
SHEET = "All Autosys Jobs"

NS = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
REL = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}"

GROUP_ORDER = {"EOD": 0, "Post EOD-BOD": 1, "BOD": 2, "Report/Extract": 3}


def read_sheet(book: pathlib.Path, name: str) -> list[list[str]]:
    with zipfile.ZipFile(book) as z:
        workbook = ET.fromstring(z.read("xl/workbook.xml"))
        rels = {r.get("Id"): r.get("Target")
                for r in ET.fromstring(z.read("xl/_rels/workbook.xml.rels"))}
        target = next(rels[s.get(REL + "id")] for s in workbook.find(NS + "sheets")
                      if s.get("name") == name)
        shared = ["".join(t.text or "" for t in si.iter(NS + "t"))
                  for si in ET.fromstring(z.read("xl/sharedStrings.xml"))]
        grid = ET.fromstring(z.read("xl/" + target.lstrip("/").replace("xl/", "")))
        rows = []
        for row in grid.iter(NS + "row"):
            values = []
            for cell in row.iter(NS + "c"):
                v = cell.find(NS + "v")
                text = ""
                if v is not None:
                    text = (shared[int(v.text)]
                            if cell.get("t") == "s" and (v.text or "").isdigit()
                            else (v.text or ""))
                values.append(text.strip())
            rows.append(values)
        return rows


def build() -> list[dict]:
    if not BOOK.is_file():
        return []
    rows = read_sheet(BOOK, SHEET)
    header = rows[0]

    def col(*names: str) -> int | None:
        for n in names:
            for i, h in enumerate(header):
                if h.strip().lower() == n.lower():
                    return i
        return None

    idx = {k: col(*v) for k, v in {
        "job": ("jobName",), "seq": ("jobSequence",), "group": ("Group Name",),
        "type": ("Type of Job",), "when": ("Schedule Time (Tentative)",
                                           "Schedule Time (Tentative) "),
        "purpose": ("Job Purpose in detail",), "frequency": ("Frequency",),
        "access": ("Bank API/SFTP/JDBC-ODBC",),
    }.items()}

    def cell(row: list[str], key: str) -> str:
        i = idx.get(key)
        return row[i] if i is not None and i < len(row) else ""

    served = {}
    path = ROOT / "cursor-bundle" / "flow-test" / "platform_api_map.jsonl"
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip() and not line.startswith("#"):
                r = json.loads(line)
                served.setdefault(r["api"], r)

    out = []
    for row in rows[1:]:
        job = cell(row, "job")
        if not job:
            continue
        api = served.get(job)
        try:
            seq = float(cell(row, "seq") or 0)
        except ValueError:
            seq = 0.0
        out.append({
            "job": job, "sequence": seq,
            "group": cell(row, "group"), "type": cell(row, "type"),
            "schedule": cell(row, "when"), "frequency": cell(row, "frequency"),
            "purpose": cell(row, "purpose"), "access": cell(row, "access"),
            "repo": api["repo"] if api else None,
            "in_platform_map": api is not None,
            "orchestration": api["orchestration"] if api else None,
            "processors": len(api["processors"]) if api else 0,
            "tables_written": api["tables_written"] if api else [],
        })
    out.sort(key=lambda r: (GROUP_ORDER.get(r["group"], 9), r["sequence"], r["job"]))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--repo")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    rows = build()
    if not rows:
        print(f"no Autosys sheet at {BOOK.relative_to(ROOT)}")
        return 2
    view = [r for r in rows if args.repo and r["repo"]
            and args.repo in r["repo"]] if args.repo else rows

    if args.json:
        print(json.dumps(view, indent=1))
        return 0

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8") as fh:
        fh.write("# Production Autosys EOD/BOD jobs — read from data/Trustt- HDFC EOD BOD.xlsx\n")
        for r in rows:
            fh.write(json.dumps(r) + "\n")

    unmapped = [r for r in rows if not r["in_platform_map"]]
    print(f"autosys jobs: {len(rows)} in the production schedule")
    for group, n in collections.Counter(r["group"] for r in rows).most_common():
        print(f"  {n:4} {group}")
    print(f"  {len(rows)-len(unmapped)} of {len(rows)} resolve in the platform API map")
    if unmapped:
        print(f"  NOT in the map: {', '.join(r['job'] for r in unmapped[:8])}")
    by_repo = collections.Counter(r["repo"] or "?" for r in rows)
    print("  served by: " + ", ".join(
        f"{k.replace('trustt-platform-','')} {v}" for k, v in by_repo.most_common()))
    if args.repo:
        print(f"\n{args.repo}:")
        for r in view:
            print(f"  [{r['group']:14}] seq={r['sequence']:>6.1f} {r['job'][:44]:46} "
                  f"procs={r['processors']:3} writes={len(r['tables_written']):2}")
    print(f"  → {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
