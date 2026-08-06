"""APIs excluded from the coverage denominator because the flow is not live in production.

`accounting_flow_domains.json` already carried `scope: out` for penal interest, but only
`impact_tests.py` honoured it — the money-proof metric and the footprint audit counted those
APIs anyway, so flows nobody runs dragged the numbers down and invited fake proof.

Adding a domain here is a product decision, not a coverage shortcut: it says the flow is not
live, so its absence of proof is correct rather than a debt. If such a ticket arrives, scope
it back in for that work.
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOMAINS = ROOT / "scripts/lib/accounting_flow_domains.json"


def scope_out_apis() -> set[str]:
    try:
        data = json.loads(DOMAINS.read_text())
    except (OSError, json.JSONDecodeError):
        return set()
    domains = data.get("domains") if isinstance(data.get("domains"), dict) else data
    out: set[str] = set()
    for meta in domains.values():
        if not isinstance(meta, dict) or (meta.get("scope") or "").lower() != "out":
            continue
        for api in meta.get("api_hints") or []:
            out.add(api)
    return out


def is_scope_out(api: str) -> bool:
    if not api:
        return False
    apis = scope_out_apis()
    if api in apis:
        return True
    lowered = api.lower()
    return any(a.lower() == lowered for a in apis)


if __name__ == "__main__":
    for api in sorted(scope_out_apis()):
        print(api)
