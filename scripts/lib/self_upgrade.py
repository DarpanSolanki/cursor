#!/usr/bin/env python3
"""Self-upgrade: findings → backlog → weekly draft/apply (auto_safe)."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/lib"))

from impact_tests import (  # noqa: E402
    mark_finding_done,
    record_finding,
    self_report_unincorporated,
)

FINDINGS = ROOT / "cursor-bundle/memory/self-upgrade-findings.json"
SELF_REPORT = ROOT / "cursor-bundle/memory/SELF-REPORT.md"
BACKLOG = ROOT / "scripts/workspace-backlog.json"


def _utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def weekly_drain() -> dict:
    """Draft/apply auto_safe open findings; leave structural for approval."""
    applied = []
    awaiting = []
    if not FINDINGS.is_file():
        return {"applied": [], "awaiting": [], "line": self_report_unincorporated()}
    data = json.loads(FINDINGS.read_text(encoding="utf-8"))
    for f in data.get("findings") or []:
        if f.get("status") != "open":
            continue
        if f.get("auto_safe"):
            # Structural work already applied by agents when shipping the finding's fix.
            # Mark done when draft_plan says applied= or status flipped externally.
            if (f.get("draft_plan") or "").startswith("APPLIED:"):
                mark_finding_done(f["id"], note="weekly_drain")
                applied.append(f["id"])
            else:
                awaiting.append({"id": f["id"], "title": f.get("title"), "plan": f.get("draft_plan")})
        else:
            awaiting.append({"id": f["id"], "title": f.get("title"), "plan": f.get("draft_plan"), "needs": "approval"})
    line = self_report_unincorporated()
    # Append SELF-REPORT line
    if SELF_REPORT.is_file():
        text = SELF_REPORT.read_text(encoding="utf-8")
        stamp = f"\n## Self-upgrade ({_utc()[:10]})\n- {line}\n"
        if "unincorporated findings:" not in text[-800:]:
            SELF_REPORT.write_text(text.rstrip() + stamp, encoding="utf-8")
        else:
            # refresh last line
            lines = text.rstrip().splitlines()
            out = []
            for ln in lines:
                if ln.strip().startswith("unincorporated findings:"):
                    continue
                out.append(ln)
            out.append(f"- {line}")
            SELF_REPORT.write_text("\n".join(out) + "\n", encoding="utf-8")
    return {"applied": applied, "awaiting": awaiting, "line": line}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["record", "done", "weekly", "report"])
    ap.add_argument("--id", default="")
    ap.add_argument("--title", default="")
    ap.add_argument("--sot", default="")
    ap.add_argument("--plan", default="")
    ap.add_argument("--auto-safe", action="store_true", default=True)
    ap.add_argument("--structural", action="store_true")
    args = ap.parse_args()
    if args.cmd == "record":
        item = record_finding(
            args.id,
            args.title,
            sot_entry=args.sot,
            auto_safe=not args.structural,
            draft_plan=args.plan,
        )
        print(json.dumps(item, indent=2))
    elif args.cmd == "done":
        mark_finding_done(args.id, note=args.plan or "done")
        print(self_report_unincorporated())
    elif args.cmd == "weekly":
        print(json.dumps(weekly_drain(), indent=2))
    else:
        print(self_report_unincorporated())
    return 0


if __name__ == "__main__":
    sys.exit(main())
