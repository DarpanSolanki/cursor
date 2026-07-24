#!/usr/bin/env python3
"""Accounting flow domain detection — ALL orchestration flows, not money-only."""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOMAIN_FILE = Path(__file__).with_name("accounting_flow_domains.json")

ACCOUNTING_REPO = "trustt-platform-accounting"


@lru_cache(maxsize=1)
def load_domains() -> dict:
    if not DOMAIN_FILE.is_file():
        return {}
    return json.loads(DOMAIN_FILE.read_text(encoding="utf-8")).get("domains") or {}


def path_blob(paths: list[str] | None) -> str:
    return " ".join(p.replace("\\", "/").lower() for p in (paths or []))


def service_path_blob(paths: list[str] | None) -> str:
    """Domain hints apply to microservice source only — not workspace scripts/testing."""
    service = [
        p
        for p in (paths or [])
        if "novopay-" in p.replace("\\", "/").lower()
        or "trustt-" in p.replace("\\", "/").lower()
    ]
    return path_blob(service)


def accounting_path_blob(paths: list[str] | None) -> str:
    """Path hints for accounting_flow_domains — accounting repo only.

    Prevents LOS ``…/disbursement/…`` (and similar) from falsely pulling money DCF/FC suites.
    """
    acct = [
        p
        for p in (paths or [])
        if "accounting" in p.replace("\\", "/").lower()
        or "scripts/dpic/" in p.replace("\\", "/").lower()
        or "scripts/dcf_" in p.replace("\\", "/").lower()
    ]
    return path_blob(acct)


def _api_matches(api: str, hints: list[str]) -> bool:
    """Match apiName to domain hints without substring false positives (penal vs interest)."""
    low = api.lower()
    for h in hints:
        if not h:
            continue
        hl = h.lower()
        if low == hl:
            return True
        # Prefer token boundary: hint must not be a mid-token substring of api
        if hl in low:
            i = low.find(hl)
            before = low[i - 1] if i > 0 else ""
            after_i = i + len(hl)
            after = low[after_i] if after_i < len(low) else ""
            if (not before or not before.isalnum()) and (not after or not after.isalnum()):
                return True
        if low in hl:
            i = hl.find(low)
            before = hl[i - 1] if i > 0 else ""
            after_i = i + len(low)
            after = hl[after_i] if after_i < len(hl) else ""
            if (not before or not before.isalnum()) and (not after or not after.isalnum()):
                return True
    return False


def _path_hint_matches(hint: str, blob: str) -> bool:
    """True if hint appears as a path token prefix — not mid-token (penal+interest).

    ``getloan`` may match ``getloanaccount…`` (alnum after OK).
    ``interestaccrual`` must not match inside ``penalinterestaccrual``.
    """
    if not hint or hint not in blob:
        return False
    if hint.startswith("/"):
        return True
    start = 0
    while True:
        i = blob.find(hint, start)
        if i < 0:
            return False
        before = blob[i - 1] if i > 0 else ""
        if (not before) or (not before.isalnum()):
            return True
        start = i + 1


def detect_domains(blob: str, apis: set[str] | None = None) -> list[str]:
    """Return domain ids touched by path blob and/or resolved apiNames."""
    apis = apis or set()
    domains = load_domains()
    hit: list[str] = []
    for did, meta in domains.items():
        hints = tuple(meta.get("path_hints") or [])
        api_hints = meta.get("api_hints") or []
        if hints and any(_path_hint_matches(h, blob) for h in hints):
            hit.append(did)
            continue
        if api_hints and any(_api_matches(a, api_hints) for a in apis):
            hit.append(did)
    return hit


def touches_accounting(
    blob: str,
    apis: set[str],
    repos: list[str] | None = None,
) -> bool:
    if ACCOUNTING_REPO in (repos or []):
        return True
    if "trustt-platform-accounting" in blob:
        return True
    if any(p in blob for p in ("/accounting/", "mfi_accounting", "scripts/dpic/", "scripts/dcf_")):
        return True
    # API hints only — do NOT path-match LOS/payments "disbursement" etc. as accounting.
    return bool(detect_domains("", apis))


def domain_cases(
    domain_id: str,
    *,
    phase: str = "impact",
    reg: dict | None = None,
) -> list[str]:
    meta = load_domains().get(domain_id) or {}
    key = f"{phase}_cases"
    if phase == "impact" and domain_id == "dpi":
        out = list(meta.get("impact_cases") or [])
        out.extend(meta.get("billing_cases") or [])
        return out
    return list(meta.get(key) or [])


def resolve_accounting_domain_cases(
    blob: str,
    apis: set[str],
    base: list[str],
    *,
    tier: str,
    reg: dict,
    paths: list[str] | None = None,
) -> list[str]:
    """Add domain guard cases for any accounting touch (service + money tier)."""
    if not touches_accounting(blob, apis):
        return base

    domain_blob = accounting_path_blob(paths) if paths else blob
    # Fall back to full service blob only when APIs already resolved (KG flow hit)
    if not domain_blob and apis:
        domain_blob = service_path_blob(paths) if paths else blob
    domains = detect_domains(domain_blob, apis)
    # Death FC path matches generic foreclosure hint ("foreclos") — prefer death-specific guards only.
    if "death_foreclosure" in domains and "foreclosure" in domains:
        domains = [d for d in domains if d != "foreclosure"]
    if not domains and tier in ("money", "service"):
        domains = ["read_inquiry"] if tier == "service" else domains

    def add(cid: str, out: list[str]) -> None:
        if not cid or cid in out:
            return
        if cid not in reg:
            return
        out.append(cid)

    merged = list(base)
    for did in domains:
        for cid in domain_cases(did, phase="impact", reg=reg):
            add(cid, merged)
        if tier == "money":
            for cid in domain_cases(did, phase="deep", reg=reg):
                add(cid, merged)

    # Per-api registry row when we have a concrete apiName
    for api in apis:
        from resolve_ship_cases import registry_case_for_api_ship  # noqa: WPS433

        cid = registry_case_for_api_ship(api, reg, path_blob_s=blob)
        add(cid, merged)

    # Service-tier fallback when no case resolved
    if tier == "service" and len(merged) == len(base):
        for did in domains:
            fb = (load_domains().get(did) or {}).get("fallback_case")
            if fb:
                add(fb, merged)
        if len(merged) == len(base):
            add("health.accounting", merged)

    return merged


def coverage_report(*, reg: dict | None = None) -> list[dict]:
    """Per-domain orchestration api count vs registry coverage."""
    import sys

    sys.path.insert(0, str(ROOT / "scripts/testing"))
    from orch_index import load_index  # noqa: WPS433

    reg = reg or {}
    idx = load_index()
    apis_map: dict[str, str] = idx.get("apis") or {}
    acct_apis = [a for a, r in apis_map.items() if r == ACCOUNTING_REPO]

    def bucket(name: str) -> str:
        blob = name.lower()
        for did, meta in load_domains().items():
            if any(h in blob for h in (meta.get("path_hints") or [])):
                return did
            if _api_matches(name, meta.get("api_hints") or []):
                return did
        if re.search(r"get|fetch|view|list|search|inquiry|simulation|details|overview|summary", blob):
            return "read_inquiry"
        if re.search(r"create|update|delete|approve|submit|cancel|assign", blob):
            return "write_ops"
        if blob.endswith("job") or "batch" in blob:
            return "batch_other"
        return "other"

    reg_apis = {
        (c.get("api") or "")
        for c in reg.values()
        if isinstance(c, dict) and c.get("api")
    }
    by_domain: dict[str, list[str]] = {}
    for api in acct_apis:
        by_domain.setdefault(bucket(api), []).append(api)

    rows: list[dict] = []
    for did in sorted(set(list(load_domains()) + list(by_domain))):
        api_list = by_domain.get(did, [])
        covered = [a for a in api_list if a in reg_apis]
        guard = domain_cases(did, phase="impact")
        rows.append(
            {
                "domain": did,
                "label": (load_domains().get(did) or {}).get("label", did),
                "apis": len(api_list),
                "registry_apis": len(covered),
                "guard_cases": guard,
                "gap": max(0, len(api_list) - len(covered)),
            }
        )
    return rows


def all_guard_cases() -> frozenset[str]:
    out: set[str] = set()
    for meta in load_domains().values():
        for key in ("impact_cases", "deep_cases", "release_cases", "billing_cases"):
            out.update(meta.get(key) or [])
        fb = meta.get("fallback_case")
        if fb:
            out.add(fb)
    return frozenset(out)


def main() -> int:
    import argparse
    import sys

    sys.path.insert(0, str(ROOT / "scripts/lib"))
    from infer_ship_apis import load_registry

    ap = argparse.ArgumentParser(description="Accounting flow domain coverage")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--domain", default="")
    args = ap.parse_args()
    reg = load_registry()
    rows = coverage_report(reg=reg)
    if args.domain:
        rows = [r for r in rows if r["domain"] == args.domain]
    if args.json:
        import json as _json

        print(_json.dumps(rows, indent=2))
    else:
        print(f"# Accounting flow coverage ({len(rows)} domains)")
        print(f"{'domain':<20} {'apis':>5} {'reg':>5} {'gap':>5}  guard_cases")
        for r in rows:
            guards = ",".join(r.get("guard_cases") or []) or "-"
            print(f"{r['domain']:<20} {r['apis']:>5} {r['registry_apis']:>5} {r['gap']:>5}  {guards}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
