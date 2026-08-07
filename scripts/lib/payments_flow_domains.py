#!/usr/bin/env python3
"""Payments flow domain detection — ALL orchestration flows, not money-only.

Mirrors accounting_flow_domains.py; reuses its token-boundary matchers instead
of duplicating them (same convention as lms_service_domains.py, registry_proposals.py).
"""
from __future__ import annotations

import json
import re
import sys
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOMAIN_FILE = Path(__file__).with_name("payments_flow_domains.json")

sys.path.insert(0, str(Path(__file__).parent))
from accounting_flow_domains import _api_matches, _path_hint_matches  # noqa: E402

PAYMENTS_REPO = "trustt-platform-payments"


@lru_cache(maxsize=1)
def load_domains() -> dict:
    if not DOMAIN_FILE.is_file():
        return {}
    return json.loads(DOMAIN_FILE.read_text(encoding="utf-8")).get("domains") or {}


def path_blob(paths: list[str] | None) -> str:
    return " ".join(p.replace("\\", "/").lower() for p in (paths or []))


def payments_path_blob(paths: list[str] | None) -> str:
    """Path hints for payments_flow_domains — payments repo only."""
    pay = [
        p
        for p in (paths or [])
        if "payments" in p.replace("\\", "/").lower()
    ]
    return path_blob(pay)


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


def touches_payments(
    blob: str,
    apis: set[str],
    repos: list[str] | None = None,
) -> bool:
    if PAYMENTS_REPO in (repos or []):
        return True
    if "trustt-platform-payments" in blob:
        return True
    return bool(detect_domains("", apis))


def domain_cases(
    domain_id: str,
    *,
    phase: str = "impact",
    reg: dict | None = None,
) -> list[str]:
    meta = load_domains().get(domain_id) or {}
    key = f"{phase}_cases"
    return list(meta.get(key) or [])


def _domain_read_only(meta: dict, apis: set[str], paths: list[str] | None) -> bool:
    read_apis = {str(a) for a in (meta.get("read_apis") or []) if a}
    if not read_apis:
        return False
    relevant = {a for a in apis if a and _api_matches(a, list(meta.get("api_hints") or []) + list(read_apis))}
    if not relevant:
        writeish = apis - read_apis
        return not writeish or writeish <= read_apis
    return relevant <= read_apis


def resolve_payments_domain_cases(
    blob: str,
    apis: set[str],
    base: list[str],
    *,
    tier: str,
    reg: dict,
    paths: list[str] | None = None,
) -> list[str]:
    """Add domain guard cases for any payments touch (service + money tier)."""
    if not touches_payments(blob, apis):
        return base

    domain_blob = payments_path_blob(paths) if paths else blob
    if not domain_blob and apis:
        domain_blob = blob
    domains = detect_domains(domain_blob, apis)
    if not domains and tier in ("money", "service"):
        domains = ["group_individual_collection_views"] if tier == "service" else domains

    def add(cid: str, out: list[str]) -> None:
        if not cid or cid in out:
            return
        if cid not in reg:
            return
        out.append(cid)

    merged = list(base)
    all_domains = load_domains()
    for did in domains:
        meta = all_domains.get(did) or {}
        if meta.get("scope") == "out":
            continue
        read_only = _domain_read_only(meta, apis, paths)
        if read_only and meta.get("read_impact_cases"):
            for cid in domain_cases(did, phase="read_impact", reg=reg):
                add(cid, merged)
            continue
        for cid in domain_cases(did, phase="impact", reg=reg):
            add(cid, merged)
        if tier == "money":
            for cid in domain_cases(did, phase="deep", reg=reg):
                add(cid, merged)

    if tier == "service" and len(merged) == len(base):
        for did in domains:
            fb = (load_domains().get(did) or {}).get("fallback_case")
            if fb:
                add(fb, merged)
        if len(merged) == len(base):
            add("health.payments", merged)

    return merged


def coverage_report(*, reg: dict | None = None) -> list[dict]:
    """Per-domain orchestration api count vs registry coverage."""
    sys.path.insert(0, str(ROOT / "scripts/testing"))
    from orch_index import load_index  # noqa: WPS433

    if reg is None:
        try:
            reg = json.loads((ROOT / "scripts/testing/registry.json").read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            reg = {}
    idx = load_index()
    apis_map: dict[str, str] = idx.get("apis") or {}
    pay_apis = [a for a, r in apis_map.items() if r == PAYMENTS_REPO]

    def bucket(name: str) -> str:
        blob = name.lower()
        for did, meta in load_domains().items():
            if any(_path_hint_matches(h, blob) for h in (meta.get("path_hints") or [])):
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
    for api in pay_apis:
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
        for key in ("impact_cases", "deep_cases", "release_cases"):
            out.update(meta.get(key) or [])
        fb = meta.get("fallback_case")
        if fb:
            out.add(fb)
    return frozenset(out)


def main() -> int:
    import argparse

    sys.path.insert(0, str(ROOT / "scripts/lib"))
    from infer_ship_apis import load_registry

    ap = argparse.ArgumentParser(description="Payments flow domain coverage")
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
        print(f"# Payments flow coverage ({len(rows)} domains)")
        print(f"{'domain':<32} {'apis':>5} {'reg':>5} {'gap':>5}  guard_cases")
        for r in rows:
            guards = ",".join(r.get("guard_cases") or []) or "-"
            print(f"{r['domain']:<32} {r['apis']:>5} {r['registry_apis']:>5} {r['gap']:>5}  {guards}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
