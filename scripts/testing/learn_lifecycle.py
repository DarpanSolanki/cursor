#!/usr/bin/env python3
"""Learning lifecycle on the bus: captured → proposed → adopted → verified-effective (U8)."""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys_path_testing = ROOT / "scripts" / "testing"

import sys

sys.path.insert(0, str(sys_path_testing))
from learning_bus import append_event, load_events, _read_all_rows, BUS  # noqa: E402

STALE_WEEKS = 4
REVIEW = ROOT / "cursor-bundle" / "memory" / "learning-review.md"


def _id(meta: dict | None, detail: str | None) -> str:
    if meta and meta.get("learning_id"):
        return str(meta["learning_id"])
    return (detail or "anon")[:80]


def capture(*, detail: str, api: str | None = None, learning_id: str | None = None, meta: dict | None = None) -> dict:
    m = dict(meta or {})
    m["learning_id"] = learning_id or _id(m, detail)
    m["lifecycle"] = "captured"
    return append_event(
        "learning_captured",
        source="learn_lifecycle",
        api=api,
        detail=detail,
        meta=m,
        force=True,
    )


def propose(*, learning_id: str, detail: str, api: str | None = None, kind: str = "registry_proposal") -> dict:
    return append_event(
        "learning_proposed",
        source="learn_lifecycle",
        api=api,
        detail=detail,
        meta={"learning_id": learning_id, "lifecycle": "proposed", "kind": kind},
        force=True,
    )


def adopt(*, learning_id: str, detail: str = "human promoted") -> dict:
    return append_event(
        "learning_adopted",
        source="learn_lifecycle",
        detail=detail,
        meta={"learning_id": learning_id, "lifecycle": "adopted"},
        force=True,
    )


def verify(*, learning_id: str, detail: str, api: str | None = None) -> dict:
    return append_event(
        "learning_verified",
        source="learn_lifecycle",
        api=api,
        detail=detail,
        meta={"learning_id": learning_id, "lifecycle": "verified"},
        force=True,
    )


def latest_stage(learning_id: str) -> str | None:
    order = ["captured", "proposed", "adopted", "verified"]
    best = None
    for row in _read_all_rows():
        if (row.get("meta") or {}).get("learning_id") != learning_id:
            continue
        stage = (row.get("meta") or {}).get("lifecycle") or {
            "learning_captured": "captured",
            "learning_proposed": "proposed",
            "learning_adopted": "adopted",
            "learning_verified": "verified",
        }.get(row.get("type"))
        if stage in order:
            if best is None or order.index(stage) > order.index(best):
                best = stage
    return best


def age_review(*, weeks: int = STALE_WEEKS) -> list[dict]:
    """Mark learnings untouched N weeks → review list (not trusted)."""
    cutoff = time.time() - weeks * 7 * 86400
    by_id: dict[str, dict] = {}
    for row in _read_all_rows():
        lid = (row.get("meta") or {}).get("learning_id")
        if not lid:
            continue
        ts = row.get("ts") or ""
        try:
            t = time.mktime(time.strptime(ts, "%Y-%m-%dT%H:%M:%SZ"))
        except Exception:
            continue
        prev = by_id.get(lid)
        if not prev or t > prev["_t"]:
            by_id[lid] = {**row, "_t": t, "stage": latest_stage(lid)}
    stale = []
    for lid, row in by_id.items():
        if row["_t"] < cutoff and row.get("stage") in ("captured", "proposed"):
            stale.append({"learning_id": lid, "stage": row.get("stage"), "last_ts": row.get("ts"), "detail": row.get("detail")})
            append_event(
                "learning_stale",
                source="learn_lifecycle.age",
                detail=f"untouched >{weeks}w — {row.get('detail')}",
                meta={"learning_id": lid, "lifecycle": "stale"},
                force=True,
            )
    if stale:
        REVIEW.parent.mkdir(parents=True, exist_ok=True)
        lines = ["# Learning review (stale — do not trust until re-verified)", "", f"Generated for >{weeks}w untouched", ""]
        for s in stale[:50]:
            lines.append(f"- `{s['learning_id']}` [{s['stage']}] {s.get('last_ts')} — {s.get('detail')}")
        REVIEW.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return stale


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["capture", "propose", "adopt", "verify", "stage", "age"])
    ap.add_argument("--id", default="")
    ap.add_argument("--detail", default="")
    ap.add_argument("--api", default="")
    ap.add_argument("--weeks", type=int, default=STALE_WEEKS)
    args = ap.parse_args()
    if args.cmd == "capture":
        print(json.dumps(capture(detail=args.detail or "learning", api=args.api or None, learning_id=args.id or None), indent=2))
    elif args.cmd == "propose":
        print(json.dumps(propose(learning_id=args.id, detail=args.detail or "proposal"), indent=2))
    elif args.cmd == "adopt":
        print(json.dumps(adopt(learning_id=args.id, detail=args.detail or "adopted"), indent=2))
    elif args.cmd == "verify":
        print(json.dumps(verify(learning_id=args.id, detail=args.detail or "verified on next run", api=args.api or None), indent=2))
    elif args.cmd == "stage":
        print(latest_stage(args.id) or "unknown")
    elif args.cmd == "age":
        stale = age_review(weeks=args.weeks)
        print(f"stale learnings: {len(stale)} → {REVIEW}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
