#!/usr/bin/env python3
"""Scaffold ntest registry case + optional e2e shell for a new apiName."""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "scripts/testing/registry.json"
SCRIPTS_TESTING = ROOT / "scripts/testing"
SCRIPTS_DPIC = ROOT / "scripts/dpic"


def _load_registry() -> dict:
    return json.loads(REGISTRY.read_text(encoding="utf-8"))


def _save_registry(raw: dict) -> None:
    REGISTRY.write_text(json.dumps(raw, indent=2) + "\n", encoding="utf-8")


def _slug(api: str) -> str:
    s = re.sub(r"([a-z])([A-Z])", r"\1_\2", api).lower()
    return re.sub(r"[^a-z0-9]+", "_", s).strip("_")


def _pick_sibling(raw: dict, sibling: str | None, api: str) -> tuple[str, dict]:
    cases = {k: v for k, v in raw.items() if not k.startswith("_")}
    if sibling and sibling in cases:
        return sibling, cases[sibling]
    # Prefer same-domain api case
    for cid, case in cases.items():
        if case.get("type") == "api" and case.get("api"):
            if case["api"].lower()[:4] == api.lower()[:4]:
                return cid, case
    for cid, case in cases.items():
        if case.get("type") == "api":
            return cid, case
    raise SystemExit("No sibling api case in registry — pass --sibling explicitly")


def _infer_domain(api: str) -> str:
    low = api.lower()
    if "dpi" in low or "bpi" in low or "bpd" in low:
        return "dpic"
    if "foreclos" in low or "prepay" in low:
        return "foreclosure"
    if "disburse" in low:
        return "disbursement"
    if "repay" in low or "collection" in low:
        return "dpic"
    return "testing"


def scaffold(
    api: str,
    *,
    case_id: str | None,
    sibling: str | None,
    case_type: str,
    smoke_tier: str,
    write: bool,
) -> dict:
    raw = _load_registry()
    for cid, case in raw.items():
        if cid.startswith("_"):
            continue
        if case.get("api") == api:
            raise SystemExit(f"Registry already has api={api} as case {cid}")

    sib_id, sib = _pick_sibling(raw, sibling, api)
    domain = _infer_domain(api)
    cid = case_id or f"{domain}.{_slug(api)}_api"
    if cid in raw:
        raise SystemExit(f"Case id {cid} already exists — pass --case-id")

    new_case: dict = {
        "type": case_type,
        "tags": list(dict.fromkeys((sib.get("tags") or []) + [domain.replace("dpic", "dpi")])),
        "title": f"{api} — local scaffold (from {sib_id})",
        "service": sib.get("service", "accounting"),
        "api": api,
        "smoke_tier": smoke_tier,
    }
    if case_type == "api":
        new_case["request"] = dict(sib.get("request") or {"account_number": "${ACCOUNT_NUMBER}"})
        new_case["expect"] = {"status": "SUCCESS", "paths": []}
        if sib.get("print"):
            new_case["print"] = list(sib["print"])[:3]
    elif case_type == "flow":
        script_dir = SCRIPTS_DPIC if domain == "dpic" else SCRIPTS_TESTING / domain
        script_dir.mkdir(parents=True, exist_ok=True)
        script_path = script_dir / f"run_{_slug(api)}_e2e.sh"
        if not script_path.is_file() and write:
            script_path.write_text(
                f"""#!/usr/bin/env bash
# {api} — local E2E (scaffold — fill request + SQL asserts).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
source "$ROOT/scripts/dpic/lib/dpi_demo_fixture.sh" 2>/dev/null || true
NTEST="$ROOT/scripts/bin/ntest.sh"
echo "=== {api} E2E ==="
"$NTEST" run {cid} || exit 1
echo "=== {api} PASS ==="
""",
                encoding="utf-8",
            )
            script_path.chmod(0o755)
        new_case["cmd"] = f"bash scripts/{'dpic' if domain == 'dpic' else f'testing/{domain}'}/run_{_slug(api)}_e2e.sh"
        new_case["api"] = api

    result = {
        "case_id": cid,
        "sibling": sib_id,
        "case": new_case,
        "script": str(script_path) if case_type == "flow" else None,
        "next": [
            f"Edit registry case `{cid}` — fill request/expect paths",
            f"super-agent.sh trace {api}",
            f"ntest run {cid}",
            "bash scripts/bin/sync-test-intelligence.sh --fast",
        ],
    }

    if write:
        raw[cid] = new_case
        _save_registry(raw)
        print(f"Wrote registry case: {cid}")
    else:
        print(json.dumps({"case_id": cid, "case": new_case}, indent=2))

    for step in result["next"]:
        print(f"  → {step}")
    return result


def main() -> int:
    p = argparse.ArgumentParser(description="Scaffold registry case for new apiName")
    p.add_argument("api", help="Orchestration Request name / apiName")
    p.add_argument("--case-id", help="Registry case id (default domain.api_slug_api)")
    p.add_argument("--sibling", help="Existing registry case to clone shape from")
    p.add_argument("--type", choices=["api", "flow"], default="api")
    p.add_argument("--smoke-tier", default="money", choices=["money", "smoke", "quick"])
    p.add_argument("--write", action="store_true", help="Write registry.json (default dry-run JSON)")
    args = p.parse_args()
    scaffold(
        args.api,
        case_id=args.case_id,
        sibling=args.sibling,
        case_type=args.type,
        smoke_tier=args.smoke_tier,
        write=args.write,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
