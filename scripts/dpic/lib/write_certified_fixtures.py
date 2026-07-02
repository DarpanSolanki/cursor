#!/usr/bin/env python3
"""Merge DPI certification scenario results into scripts/dpic/certified_fixtures.json."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path


def main() -> None:
    if len(sys.argv) < 3:
        raise SystemExit("usage: write_certified_fixtures.py <fixtures.json> <scenario.json> [primary_id]")
    fixtures_path = Path(sys.argv[1])
    scenario = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
    primary = sys.argv[3] if len(sys.argv) > 3 else None

    if fixtures_path.exists():
        doc = json.loads(fixtures_path.read_text(encoding="utf-8"))
    else:
        doc = {"_meta": "Local DPI certification — fresh LAN per scenario; re-run certify_dpi_scenarios.sh", "scenarios": []}

    doc["certified_at"] = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    doc["product_id"] = doc.get("product_id", "6367")
    scenarios = [s for s in doc.get("scenarios", []) if s.get("id") != scenario.get("id")]
    scenarios.append(scenario)
    doc["scenarios"] = scenarios
    if primary:
        doc["primary_scenario"] = primary
        for s in scenarios:
            if s.get("id") == primary and s.get("status") == "PASS":
                doc["primary"] = {
                    "scenario_id": primary,
                    "lan": s.get("lan"),
                    "loan_account_id": s.get("loan_account_id"),
                    "foreclosure_date": s.get("foreclosure_job_ms"),
                    "job_time": s.get("single_overdue_job_ms") or s.get("multi_overdue_job_ms"),
                }
                break

    fixtures_path.parent.mkdir(parents=True, exist_ok=True)
    fixtures_path.write_text(json.dumps(doc, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {fixtures_path} ({len(scenarios)} scenario(s))")


if __name__ == "__main__":
    main()
