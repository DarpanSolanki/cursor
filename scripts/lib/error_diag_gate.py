"""L3 — close the `kg why` loop by DERIVING a diagnostic from a shipped fix.

`kg why` was empty on 4% of platform APIs because diagnostics were hand-authored, so they
only got written when someone remembered. The obvious fix — "fail the ship unless a
diagnostic exists" — is worse than the gap: an agent that can satisfy a gate by writing
prose will write prose, and the KG fills with plausible fiction that later reads as truth.

So this gate never accepts authored text. Every field is derived from evidence that already
exists, and it REFUSES to emit when the evidence is missing:

    id/src/mechanism/depends  <- KG throw sites + ExecutionContext keys (build_error_codes)
    symptom                   <- the runtime message template for the code
    diagnostic                <- the registry case that covers the code (red -> green)
    fix                       <- the changelog entry sha + branch

    python3 scripts/lib/error_diag_gate.py --codes 132168,134131      # show derived
    python3 scripts/lib/error_diag_gate.py --from-changelog           # codes from latest entry
    python3 scripts/lib/error_diag_gate.py --from-changelog --emit    # append to diagnostics.jsonl
    python3 scripts/lib/error_diag_gate.py --from-changelog --strict  # exit 2 if a loop is open
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
KG_DB = ROOT / "cursor-bundle" / "kg" / "data" / "kg.db"
DIAGS = ROOT / "cursor-bundle" / "kg" / "curated" / "diagnostics.jsonl"
CHANGELOG = ROOT / "cursor-bundle" / "brain" / "changelog" / "CHANGELOG.md"
REGISTRY = ROOT / "scripts" / "testing" / "registry.json"

CODE_RE = re.compile(r"\b(\d{6}|[A-Z][A-Z0-9]{1,7}(?:-[A-Z0-9]+)+)\b")


def _template(code: str) -> tuple[str | None, str | None]:
    for key in (f"localmfi_{code}_en-in", f"localmfi_{code}"):
        try:
            out = subprocess.run(
                ["redis-cli", "-n", "2", "get", key],
                capture_output=True, text=True, timeout=3,
            ).stdout.strip()
        except Exception:
            return None, None
        if out and out != "(nil)":
            return out.strip('"'), f"redis db2:{key}"
    return None, None


def _throw_sites(db: sqlite3.Connection, code: str) -> list[dict]:
    rows = db.execute(
        "SELECT src,json FROM edges WHERE dst_id=? AND rel='throws' ORDER BY src",
        (f"error:{code}",),
    ).fetchall()
    out = []
    for src, ej in rows:
        o = json.loads(ej) if ej else {}
        o["src"] = src
        out.append(o)
    return out


def _changelog_codes() -> tuple[list[str], str, str]:
    if not CHANGELOG.exists():
        return [], "", ""
    head: list[str] = []
    for line in CHANGELOG.read_text(encoding="utf-8", errors="replace").splitlines():
        if head and line.startswith("## "):
            break
        head.append(line)
        if len(head) > 60:
            break
    blob = "\n".join(head)
    codes: list[str] = []
    m = re.search(r"errors?\s*[=:]\s*([0-9A-Z,\- ]+)", blob)
    if m:
        codes = [x.strip() for x in m.group(1).split(",") if x.strip()]
    sha = ""
    ms = re.search(r"\b([0-9a-f]{7,40})\b", blob)
    if ms:
        sha = ms.group(1)
    branch = ""
    mb = re.search(r"\b(mfi_(?:integration|release)_v[0-9.]+)\b", blob)
    if mb:
        branch = mb.group(1)
    return codes, sha, branch


def _registry_cases(code: str) -> list[str]:
    if not REGISTRY.exists():
        return []
    try:
        reg = json.loads(REGISTRY.read_text(encoding="utf-8"))
    except Exception:
        return []
    # registry.json is a dict keyed by case id (plus `_meta` / `_correlators` sidecars),
    # not a list under "cases".
    hits = []
    if isinstance(reg, dict):
        items = reg.items()
    else:
        items = ((c.get("id", ""), c) for c in reg if isinstance(c, dict))
    for cid, cse in items:
        if cid.startswith("_") or not isinstance(cse, dict):
            continue
        if code in json.dumps(cse):
            hits.append(cid)
    return hits


def derive(db: sqlite3.Connection, code: str, sha: str, branch: str) -> dict:
    sites = _throw_sites(db, code)
    tpl, tpl_src = _template(code)
    cases = _registry_cases(code)
    keys: list[str] = []
    for s in sites:
        for k in (s.get("ctx_keys") or "").split(","):
            if k and k not in keys:
                keys.append(k)
    missing = []
    if not sites:
        missing.append("no throw site in KG (dynamic throw, or rebuild the KG)")
    if not tpl:
        missing.append("no message template resolved (is redis db2 loaded?)")
    if not cases:
        missing.append("no registry case references this code (encode the defect first)")
    rec = {
        "code": code,
        "sites": sites,
        "template": tpl,
        "template_src": tpl_src,
        "ctx_keys": keys,
        "cases": cases,
        "missing": missing,
    }
    if not sites or not tpl:
        return rec
    owner = (sites[0].get("from") or "").split(":", 1)[-1]
    rec["diag"] = {
        "t": "node",
        "id": f"diag:error.{code}",
        "kind": "diag",
        "class": "message_resolution" if "${" in tpl else "validation_gate",
        "label": f"{code} — {tpl}",
        "symptom": tpl,
        "role": f"{code} " + " ".join(keys) + " error message validation",
        "src": sites[0]["src"],
        "mechanism": f"{owner} throws {code} ({sites[0].get('severity','?')}); "
                     f"message template `{tpl}` is substituted from the ExecutionContext",
        "depends": ("ExecutionContext keys: " + ", ".join(keys)) if keys
                   else "no ExecutionContext placeholder keys",
        "fails_to": (
            f"blank or literal `{tpl}` reaches the caller when "
            f"{', '.join(keys)} {'is' if len(keys) == 1 else 'are'} "
            f"absent from the resolving context"
            if keys else f"caller receives {code} with no further detail"
        ),
        "diagnostic": "registry case(s): " + ", ".join(cases),
        "reference": f"branch {branch or sites[0].get('branch','?')}"
                     + (f" sha {sha}" if sha else ""),
    }
    return rec


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--codes", default="")
    ap.add_argument("--from-changelog", action="store_true")
    ap.add_argument("--emit", action="store_true")
    ap.add_argument("--strict", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    sha = branch = ""
    codes = [x.strip() for x in args.codes.split(",") if x.strip()]
    if args.from_changelog:
        cl, sha, branch = _changelog_codes()
        codes = codes or cl
    if not codes:
        print("error-diag: no error codes named (--codes, or `errors=` in the changelog entry)")
        return 0
    if not KG_DB.exists():
        print("error-diag: kg.db missing — run cursor-bundle/kg/bin/build.sh")
        return 1

    db = sqlite3.connect(f"file:{KG_DB}?mode=ro", uri=True)
    existing = DIAGS.read_text(encoding="utf-8", errors="replace") if DIAGS.exists() else ""
    results = [derive(db, c, sha, branch) for c in codes]

    if args.json:
        print(json.dumps(results, indent=2))
        return 0

    open_loops = 0
    emitted = 0
    for r in results:
        code = r["code"]
        print(f"\n=== {code} ===")
        print(f"  throw sites : {len(r['sites'])}")
        for s in r["sites"]:
            print(f"      {s['src']}  [{s.get('branch','?')}]")
        print(f"  template    : {r['template'] or '— none —'}")
        print(f"  EC keys     : {', '.join(r['ctx_keys']) or '— none —'}")
        print(f"  registry    : {', '.join(r['cases']) or '— none —'}")
        if r["missing"]:
            open_loops += 1
            print("  LOOP OPEN — cannot derive a diagnostic:")
            for m in r["missing"]:
                print(f"      * {m}")
            print("    Fix the evidence, not this gate. A diagnostic written by hand to")
            print("    satisfy a gate is exactly what poisons `kg why`.")
            continue
        if f'"diag:error.{code}"' in existing:
            print("  already in diagnostics.jsonl — nothing to write")
            continue
        if args.emit:
            with DIAGS.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(r["diag"], ensure_ascii=False) + "\n")
            emitted += 1
            print("  EMITTED to diagnostics.jsonl (derived — review, then rebuild the KG)")
        else:
            print("  derivable — rerun with --emit to write it")

    if emitted:
        print(f"\nerror-diag: wrote {emitted} derived diagnostic(s) — "
              f"rebuild: cursor-bundle/kg/bin/build.sh --force")
    if args.strict and open_loops:
        print(f"\nerror-diag: FAIL — {open_loops} code(s) with an open knowledge loop")
        return 2
    print(f"\nerror-diag: {len(results)} code(s), {open_loops} open loop(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
