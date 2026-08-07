#!/usr/bin/env python3
"""Generate read-API registry cases from the JTF templates, and keep only the ones that pass.

Writing a case by hand meant finding the request shape and the response contract for each
API — twenty minutes, ninety times over, which is why `read_inquiry` sat at 4 of 94 covered.
The service already ships both, as `templates/request|response/**/<api>_*Template.json`.

The honest part is the last step. A generated case that fails is not coverage, it is noise
that trains everyone to ignore red, so a case is written to the registry **only after it has
run green against the live service**. Failures are reported with the reason so the fixture
gap is visible rather than papered over.

Read-only APIs only. Nothing here generates a case that mutates state.

    generate_read_cases.py --dry-run        what would be attempted, and with what request
    generate_read_cases.py                  generate, run, keep passes, report failures
    generate_read_cases.py --limit 10
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "scripts" / "testing" / "registry.json"

sys.path.insert(0, str(ROOT / "scripts" / "testing"))
import read_inquiry_worklist as worklist  # noqa: E402

# Only fields a real correlator can fill. Anything else means the API needs a fixture we do
# not have, and the case is not attempted — never invented.
FILL = {
    "account_number": "${ACCOUNT_NUMBER}",
    "account_number_list": "${ACCOUNT_NUMBER}",
    "account_number_details": "${ACCOUNT_NUMBER}",
    "loan_account_number": "${ACCOUNT_NUMBER}",
    "loan_account_id": "${LOAN_ACCOUNT_ID}",
    "customer_id": "${CUSTOMER_ID}",
    "office_id": "${OFFICE_ID}",
    "user_id": "${USER_ID}",
}

# Mutating verbs never get a generated case, whatever the name search matched.
_MUTATES = re.compile(r"^(create|update|delete|approve|submit|cancel|assign|post|process|"
                      r"upload|generate|reverse|waive|disburse|repay|close)", re.I)


def case_id(api: str) -> str:
    snake = re.sub(r"(?<!^)(?=[A-Z])", "_", api).lower()
    return f"accounting.{snake}"


_LITERAL = re.compile(r"^[A-Za-z0-9_]+$")


def literal_value(allowed: dict, field: str) -> str | None:
    """A `patternFieldValidator` pattern is only usable when it names one literal value.

    `DEFAULT|BY_DUE_DATE` yields `DEFAULT`. `[0-9]+` yields nothing — sending the regex as
    the value invents data, which is the thing this generator exists not to do.
    """
    value = (allowed or {}).get(field)
    return value if value and _LITERAL.match(value) else None


def build_request(row: dict) -> dict | None:
    """Fill the template's top-level fields from correlators, or refuse."""
    allowed = row.get("allowed_values") or {}
    req: dict = {}
    for field in row["request_fields"]:
        root = field["path"].split(".")[0]
        if root in FILL:
            req.setdefault(root, FILL[root])
            continue
        literal = literal_value(allowed, root)
        if literal is None:
            return None
        req.setdefault(root, literal)
    return req


# `function_code`, `function_sub_code` and `run_mode` are control fields the gateway reads
# from the headers. Sending them in the body leaves the validator seeing nothing and the API
# answers `11008 Invalid run_mode` on a request that names run_mode correctly.
CONTROL_FIELDS = ("function_code", "function_sub_code", "run_mode")


def build_headers(row: dict) -> dict:
    allowed = row.get("allowed_values") or {}
    return {k: literal_value(allowed, k) for k in CONTROL_FIELDS
            if literal_value(allowed, k)}


def shape_request(api: str, req: dict, row: dict) -> dict:
    """Honour ARR containers the template declares (a list field must be sent as a list)."""
    arr_roots = {f["path"].split(".")[0].removesuffix("[0]")
                 for f in row["request_fields"] if "[0]" in f["path"].split(".")[0]}
    out: dict = {}
    for key, value in req.items():
        if key in arr_roots:
            leaf = next((f["path"].split(".")[-1] for f in row["request_fields"]
                         if f["path"].startswith(key)), None)
            out[key] = [{leaf: value}] if leaf and leaf != key else [value]
        else:
            out[key] = value
    return out


def assertable(row: dict) -> list[str]:
    paths = [p for p in row["assertable_paths"] if not p.startswith("response_status")]
    return paths[:1]


def candidates(limit: int | None) -> list[dict]:
    rows = []
    for row in worklist.build():
        api = row["api"]
        if _MUTATES.match(api) or not row["request_template"] or not row["response_template"]:
            continue
        req = build_request(row)
        if req is None or not assertable(row):
            continue
        rows.append({**row, "_request": shape_request(api, req, row),
                     "_headers": build_headers(row)})
    rows.sort(key=lambda r: len(r["_request"]))
    return rows[:limit] if limit else rows


def run_case(cid: str) -> tuple[bool, str]:
    proc = subprocess.run(["bash", str(ROOT / "scripts/bin/ntest.sh"), "run", cid],
                          cwd=str(ROOT), capture_output=True, text=True, timeout=300)
    text = proc.stdout + proc.stderr
    if "✓ PASS" in text:
        return True, "PASS"
    for marker in ("STALE RUNTIME", "SKIP"):
        if marker in text:
            return False, marker
    fail = [l.strip() for l in text.splitlines() if "[FAIL]" in l or '"code"' in l]
    return False, (fail[0][:160] if fail else "no PASS marker")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=int)
    args = ap.parse_args()

    rows = candidates(args.limit)
    print(f"{len(rows)} read API(s) the correlators can drive\n")

    if args.dry_run:
        for r in rows:
            print(f"  {r['api'][:44]:46} {json.dumps(r['_request'])[:70]}")
        return 0

    kept, rejected = [], []
    for r in rows:
        api, cid = r["api"], case_id(r["api"])
        reg = json.loads(REGISTRY.read_text(encoding="utf-8"))
        if cid in reg:
            continue
        reg[cid] = {
            "type": "api", "smoke_tier": "service", "ship_auto": True,
            "tags": ["read", "inquiry", "generated"],
            "title": f"{api} — read contract",
            "service": "accounting", "api": api, "request": r["_request"],
            "headers": r["_headers"],
            "expect": {"status": "SUCCESS", "paths": assertable(r)},
            "why": "generated from the shipped JTF request/response templates and kept only "
                   "after running green (generate_read_cases.py)",
        }
        REGISTRY.write_text(json.dumps(reg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

        ok, why = run_case(cid)
        if ok:
            kept.append(api)
            print(f"  KEEP   {api}")
        else:
            reg = json.loads(REGISTRY.read_text(encoding="utf-8"))
            reg.pop(cid, None)
            REGISTRY.write_text(json.dumps(reg, indent=2, ensure_ascii=False) + "\n",
                                encoding="utf-8")
            rejected.append((api, why))
            print(f"  drop   {api}  — {why}")

    print(f"\nkept {len(kept)} case(s); {len(rejected)} not generated")
    if rejected:
        print("  not coverage — each needs a fixture or a contract look:")
        for api, why in rejected[:20]:
            print(f"    {api[:44]:46} {why}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
