#!/usr/bin/env python3
"""Registry proposals + acceptance ratchet + gap miner (Upgrade 7).

Drafts land in scripts/testing/registry-proposals.json (human promotes to registry.json).
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "lib"))
from accounting_flow_domains import _path_hint_matches  # noqa: E402
PROPOSALS = ROOT / "scripts" / "testing" / "registry-proposals.json"
REGISTRY = ROOT / "scripts" / "testing" / "registry.json"
MANIFEST = ROOT / "scripts" / "lib" / "acceptance_coverage_manifest.json"
DOMAINS = ROOT / "scripts" / "lib" / "accounting_flow_domains.json"
PENDING = ROOT / ".cursor" / ".pending-ship-work.json"
CHANGELOG = ROOT / ".cursor" / "changelog.md"
GRANDFATHER = ROOT / "scripts" / "testing" / ".verify-mode-grandfather"


def _utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _load(path: Path, default):
    if not path.is_file():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return default


def _save_proposals(data: dict) -> None:
    PROPOSALS.parent.mkdir(parents=True, exist_ok=True)
    PROPOSALS.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def load_proposals() -> dict:
    return _load(PROPOSALS, {"version": 1, "updated": None, "proposals": []})


def draft_from_ship(*, force: bool = False) -> dict | None:
    """AUTO-DRAFT a regression pin from pending ship / recent changelog (mutation-gated adoption)."""
    pending = _load(PENDING, {})
    tier = (pending.get("tier") or "").lower()
    apis = list(pending.get("apis") or [])
    files = list(pending.get("files") or [])
    if not force and tier not in ("money", "service") and not apis:
        # Try changelog head for a recent bugfix
        if CHANGELOG.is_file():
            head = CHANGELOG.read_text(encoding="utf-8", errors="ignore").splitlines()[:8]
            blob = " ".join(head).lower()
            if "fix" not in blob and "bug" not in blob:
                return None
        else:
            return None

    api = (apis[0] if apis else "unknownApi")
    domain = "unknown"
    domains = (_load(DOMAINS, {}) or {}).get("domains") or {}
    blob = " ".join(files + apis).lower()
    for name, d in domains.items():
        hints = [h.lower() for h in (d.get("path_hints") or []) + (d.get("api_hints") or [])]
        if any(h and _path_hint_matches(h, blob) for h in hints):
            domain = name
            break

    cid = f"proposal.{domain}.{api}.{_utc()[:10].replace('-', '')}"
    money_tables = ((_load(MANIFEST, {}) or {}).get("domain_money_tables") or {}).get(domain) or [
        "transaction_master"
    ]
    db_asserts = [
        {
            "table": t,
            "assert": f"TODO: value-level expect for {t} from RCA evidence",
            "expect": {"TODO": "fill from ship DB readback"},
            "checked_by": "AUTO-DRAFT — promote after human fills expects",
        }
        for t in money_tables[:4]
    ]
    proposal = {
        "id": cid,
        "status": "draft",
        "source": "ship_auto_draft",
        "created_at": _utc(),
        "domain": domain,
        "suggested_tier": "money" if tier == "money" or domain != "unknown" else "smoke",
        "case": {
            "type": "flow",
            "api": api,
            "smoke_tier": "money" if domain != "unknown" else "smoke",
            "verify_mode": "runtime",
            "note": "AUTO-DRAFT from ship/RCA — human must promote to registry.json after filling expects",
            "acceptance": {
                "verify_mode": "runtime",
                "dimensions": ["happy_path", "dirty_state"],
                "db_asserts": db_asserts,
            },
            "defaults": {},
            "expect": {"status": "SUCCESS"},
        },
        "evidence": {"pending_apis": apis, "pending_files": files[:12], "tier": tier},
    }
    data = load_proposals()
    # de-dupe same api+domain draft same day
    existing = [
        p
        for p in data["proposals"]
        if p.get("domain") == domain and p.get("case", {}).get("api") == api and p.get("status") == "draft"
    ]
    if existing and not force:
        return existing[0]
    data["proposals"].append(proposal)
    data["updated"] = _utc()
    _save_proposals(data)
    return proposal


def mine_gaps() -> list[dict]:
    """Wire accounting-flow-coverage gaps → case STUBS in proposals."""
    sys.path.insert(0, str(ROOT / "scripts" / "lib"))
    import accounting_flow_domains as afd  # type: ignore

    from infer_ship_apis import load_registry  # type: ignore

    reg = load_registry()
    rows = afd.coverage_report(reg=reg)
    stubs = []
    data = load_proposals()
    known = {p.get("id") for p in data["proposals"]}
    enforced = set((_load(MANIFEST, {}) or {}).get("enforced_domains") or [])
    high = {"dpi", "prepayment", "reversal", "restructuring", "reopening"}
    for r in rows:
        name = r["domain"]
        gap = int(r.get("gap") or 0)
        impact = r.get("guard_cases") or []
        if gap <= 0 and impact:
            continue
        apis = ((_load(DOMAINS, {}) or {}).get("domains") or {}).get(name, {}).get("api_hints") or []
        api = apis[0] if apis else name
        pid = f"gap.{name}.{api}"
        if pid in known:
            continue
        stub = {
            "id": pid,
            "status": "stub",
            "source": "gap_miner",
            "created_at": _utc(),
            "domain": name,
            "suggested_tier": "money" if name in enforced or name in high else "smoke",
            "case": {
                "type": "flow",
                "api": api,
                "smoke_tier": "smoke",
                "verify_mode": "runtime",
                "note": f"GAP STUB — domain {name} gap={gap} apis; human designs fixture",
                "acceptance": {"verify_mode": "runtime", "dimensions": ["happy_path"]},
            },
            "evidence": {"gap": gap, "apis": r.get("apis"), "registry_apis": r.get("registry_apis"), "guard_cases": impact},
        }
        data["proposals"].append(stub)
        stubs.append(stub)
        known.add(pid)
    data["updated"] = _utc()
    _save_proposals(data)
    return stubs


def check_ratchet() -> list[str]:
    """Fail if enforced_domains shrank vs enforced_domains_min or money case deleted without replacement."""
    errors: list[str] = []
    man = _load(MANIFEST, {})
    enforced = list(man.get("enforced_domains") or [])
    minimum = list(man.get("enforced_domains_min") or [])
    if not set(minimum).issubset(set(enforced)):
        missing = sorted(set(minimum) - set(enforced))
        errors.append(
            f"acceptance ratchet FAIL: enforced_domains shrunk — missing {missing} "
            f"(min={minimum}). List may only GROW."
        )
    # Money case deletion: compare to proposals tombstones? Use git if available.
    try:
        import subprocess

        prev = subprocess.check_output(
            ["git", "show", "HEAD:scripts/testing/registry.json"],
            cwd=str(ROOT),
            stderr=subprocess.DEVNULL,
            text=True,
        )
        old = json.loads(prev)
        new = _load(REGISTRY, {})
        old_money = {k for k, v in old.items() if isinstance(v, dict) and v.get("smoke_tier") == "money"}
        new_money = {k for k, v in new.items() if isinstance(v, dict) and v.get("smoke_tier") == "money"}
        deleted = sorted(old_money - new_money)
        if deleted:
            # Allow if proposal references replacement
            props = load_proposals()
            refs = " ".join(json.dumps(p) for p in props.get("proposals") or [])
            for d in deleted:
                if d not in refs and f"replaces:{d}" not in refs:
                    errors.append(
                        f"acceptance ratchet FAIL: money case deleted without replacement ref: {d} "
                        f"(add proposal with replaces:{d} or restore case)"
                    )
    except Exception:
        pass
    return errors


def check_money_verify_modes() -> list[str]:
    """All smoke_tier:money cases must declare verify_mode."""
    man = _load(MANIFEST, {})
    if not man.get("require_money_verify_mode", True):
        return []
    reg = _load(REGISTRY, {})
    gf = set()
    if GRANDFATHER.is_file():
        gf = {ln.strip() for ln in GRANDFATHER.read_text().splitlines() if ln.strip() and not ln.startswith("#")}
    errors = []
    for cid, c in reg.items():
        if not isinstance(c, dict) or c.get("smoke_tier") != "money":
            continue
        vm = c.get("verify_mode") or (c.get("acceptance") or {}).get("verify_mode")
        if not vm:
            if cid in gf:
                continue
            errors.append(f"{cid}: money case missing verify_mode")
    return errors


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["draft", "mine", "ratchet", "verify-modes", "check", "list"])
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()
    if args.cmd == "draft":
        p = draft_from_ship(force=args.force)
        print(json.dumps(p, indent=2) if p else "no draft (nothing pending / no bug changelog)")
        return 0
    if args.cmd == "mine":
        stubs = mine_gaps()
        print(f"gap stubs added: {len(stubs)}")
        for s in stubs[:20]:
            print(f"  - {s['id']} domain={s['domain']} tier={s['suggested_tier']}")
        return 0
    if args.cmd == "ratchet":
        errs = check_ratchet()
        if errs:
            print("RATCHET FAIL:")
            for e in errs:
                print(f"  - {e}")
            return 1
        print("RATCHET OK: enforced_domains grew-or-held; no orphan money deletes")
        return 0
    if args.cmd == "verify-modes":
        errs = check_money_verify_modes()
        if errs:
            print("verify_mode FAIL:")
            for e in errs:
                print(f"  - {e}")
            return 1
        print("verify_mode OK: all money cases declare verify_mode")
        return 0
    if args.cmd == "check":
        from process_router import check_money_ratchet

        errs = check_ratchet() + check_money_verify_modes() + check_money_ratchet()
        if errs:
            print("registry-proposals check FAIL:")
            for e in errs:
                print(f"  - {e}")
            return 1
        print("registry-proposals check OK (acceptance + verify_mode + money-cell)")
        return 0
    if args.cmd == "list":
        data = load_proposals()
        print(f"proposals: {len(data.get('proposals') or [])} updated={data.get('updated')}")
        for p in data.get("proposals") or []:
            print(f"  [{p.get('status')}] {p.get('id')} {p.get('domain')}")
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
