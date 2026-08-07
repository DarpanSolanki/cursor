#!/usr/bin/env python3
"""Turn the read_inquiry coverage gap into a worklist someone can actually pick up.

`read_inquiry` is the largest accounting domain — 94 APIs, 4 covered — and the reason is not
laziness: writing a case means finding the API's request shape and its response contract.
That is twenty minutes of archaeology per API, ninety times over.

The contract is already written down, in the **JTF templates** the service ships:

    deploy/application/templates/request/**/<api>_requestTemplate.json
    deploy/application/templates/response/**/<api>_responseTemplate.json

The request template names every field, not only the validated ones — reading validators
alone reported `getAccountBalances` as requiring nothing, which is plainly false. The
response template names the paths a case can assert, so a generated case can check real
response keys instead of settling for HTTP 200. Validators stay as a second source, for
which fields are mandatory and what values they accept.

Rows are evidence for writing a case — never coverage on their own.

    read_inquiry_worklist.py               write the worklist + summary
    read_inquiry_worklist.py --json
    read_inquiry_worklist.py --ready       only APIs the standard local fixture can drive
    read_inquiry_worklist.py --api NAME    one API's full contract
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[2]
FLOW = ROOT / "cursor-bundle" / "flow-test"
OUT = FLOW / "read_inquiry_worklist.jsonl"
ACCT = ROOT / "trustt-platform-accounting"
TEMPLATES = ACCT / "deploy" / "application" / "templates"

sys.path.insert(0, str(ROOT / "scripts" / "lib"))
sys.path.insert(0, str(ROOT / "cursor-bundle" / "kg" / "bin"))

# Fields the existing local fixture supplies without inventing anything.
FIXTURE_FIELDS = {
    "account_number", "account_number_list", "account_number_details", "loan_account_number",
    "lan", "customer_id", "external_ref_number", "product_id", "office_id", "office_code",
    "group_id", "account_id", "loan_account_id", "function_code", "function_sub_code",
}

_REQUEST = re.compile(r'<Request\s+name="([^"]+)"', re.I)
_PROCESSOR = re.compile(r'<Processor[^>]*\bbean="([^"]+)"', re.I)
_VALIDATOR = re.compile(r'<Validator\s+bean="([^"]+)"(.*?)</Validator>', re.I | re.S)
_IPARAM = re.compile(r'<IParam\b([^>]*)/?>', re.I)
_ATTR = re.compile(r'(\w+)="([^"]*)"')

_META = {"class", "type"}


def orch_files() -> list[pathlib.Path]:
    from _contract_scan import orchestration_xmls
    return [ROOT / p for p in orchestration_xmls("trustt-platform-accounting")]


def request_sites() -> dict[str, tuple[str, int, str]]:
    sites: dict[str, tuple[str, int, str]] = {}
    for path in orch_files():
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        matches = list(_REQUEST.finditer(text))
        for i, m in enumerate(matches):
            end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
            line = text.count("\n", 0, m.start()) + 1
            sites.setdefault(m.group(1), (str(path.relative_to(ROOT)), line, text[m.start():end]))
    return sites


def _template_index(kind: str) -> dict[str, pathlib.Path]:
    root = TEMPLATES / kind
    suffix = f"_{kind}Template.json"
    return {p.name[: -len(suffix)]: p
            for p in root.rglob(f"*{suffix}") if p.name.endswith(suffix)} if root.is_dir() else {}


def walk(node: dict, prefix: str = "") -> list[dict]:
    """Flatten a JTF template into leaf fields, as JSON paths the response really has.

    A container repeats its own name to hold the element shape:

        account_overview_list: {type: ARR, account_overview_list: {amount_details: {...}}}

    Emitting that literally produced `account_overview_list.account_overview_list.…`, which
    matches nothing. The repeated key is the shape, not a path segment, so it is collapsed —
    and an `ARR` becomes `[0]`. Checked against `dpic.overview_api`, a case known to pass:
    `account_overview_list[0].amount_details.total_accrued_dpi_amount`.
    """
    out: list[dict] = []
    for name, child in node.items():
        if name in _META or not isinstance(child, dict):
            continue
        segment = f"{name}[0]" if str(child.get("type")).upper() == "ARR" else name
        path = f"{prefix}.{segment}" if prefix else segment
        inner = child.get(name) if isinstance(child.get(name), dict) else child
        grand = {k: v for k, v in inner.items() if k not in _META and isinstance(v, dict)}
        if grand:
            out.extend(walk(inner, path))
        else:
            out.append({"path": path, "type": child.get("type"), "class": child.get("class")})
    return out


def contract_from_template(path: pathlib.Path | None, api: str) -> list[dict]:
    if path is None:
        return []
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    body = doc.get(api)
    return walk(body) if isinstance(body, dict) else walk(doc)


def validator_contract(block: str) -> tuple[list[str], dict[str, str]]:
    required: list[str] = []
    allowed: dict[str, str] = {}
    for bean, body in _VALIDATOR.findall(block):
        for raw in _IPARAM.findall(body):
            attrs = dict(_ATTR.findall(raw))
            field = attrs.get("fieldName")
            if not field:
                continue
            if bean == "mandatoryFieldValidator":
                required.append(field)
            elif bean == "patternFieldValidator" and attrs.get("pattern"):
                allowed[field] = attrs["pattern"].split("|")[0]
    return sorted(dict.fromkeys(required)), allowed


def uncovered_read_apis() -> list[str]:
    import accounting_flow_domains as afd
    reg = json.loads((ROOT / "scripts/testing/registry.json").read_text(encoding="utf-8"))
    covered = {c.get("api") for c in reg.values() if isinstance(c, dict) and c.get("api")}
    sys.path.insert(0, str(ROOT / "scripts" / "testing"))
    from orch_index import load_index

    out = []
    for api, repo in (load_index().get("apis") or {}).items():
        if repo != afd.ACCOUNTING_REPO or api in covered:
            continue
        if re.search(r"get|fetch|view|list|search|inquiry|simulation|details|overview|summary",
                     api.lower()):
            out.append(api)
    return sorted(out)


def build(only: str | None = None) -> list[dict]:
    sites = request_sites()
    req_idx, resp_idx = _template_index("request"), _template_index("response")
    rows: list[dict] = []

    for api in ([only] if only else uncovered_read_apis()):
        site = sites.get(api)
        req = contract_from_template(req_idx.get(api), api)
        resp = contract_from_template(resp_idx.get(api), api)
        required, allowed = validator_contract(site[2]) if site else ([], {})

        roots = {f["path"].split(".")[0] for f in req}
        unmet = sorted(r for r in roots if r not in FIXTURE_FIELDS and r not in allowed)

        rows.append({
            "api": api,
            "orchestration": f"{site[0]}:{site[1]}" if site else None,
            "request_template": str(req_idx[api].relative_to(ROOT)) if api in req_idx else None,
            "response_template": str(resp_idx[api].relative_to(ROOT)) if api in resp_idx else None,
            "request_fields": req,
            "assertable_paths": [f["path"] for f in resp],
            "mandatory_fields": required,
            "allowed_values": allowed,
            "unmet_inputs": unmet,
            "processors": _PROCESSOR.findall(site[2])[:12] if site else [],
            "ready": bool(req_idx.get(api)) and bool(resp) and not unmet,
        })
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--ready", action="store_true")
    ap.add_argument("--api")
    args = ap.parse_args()

    rows = build(args.api)
    if args.ready:
        rows = [r for r in rows if r["ready"]]

    if args.json or args.api:
        print(json.dumps(rows, indent=1))
        return 0

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8") as fh:
        fh.write("# uncovered accounting read/inquiry APIs — JTF request+response contract per API.\n")
        fh.write("# Evidence for writing a registry case. Never coverage on its own.\n")
        for r in rows:
            fh.write(json.dumps(r) + "\n")

    templated = [r for r in rows if r["request_template"]]
    assertable = [r for r in rows if r["assertable_paths"]]
    ready = [r for r in rows if r["ready"]]
    print(f"read_inquiry worklist: {len(rows)} uncovered API(s) → {OUT.relative_to(ROOT)}")
    print(f"  {len(templated):3} have a JTF request template (the real field list)")
    print(f"  {len(assertable):3} have a response template — real paths to assert, not just HTTP 200")
    print(f"  {len(ready):3} the standard local fixture can drive today")
    if len(rows) - len(templated):
        print(f"  {len(rows)-len(templated):3} have NO request template — "
              "`internal-api-local-test-harness.md` says add one before claiming a test")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
