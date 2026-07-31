#!/usr/bin/env python3
"""Credit recent ntest PASSes into ship-loop — skip re-fire when code fingerprint matches.

Standing problem: agents run money e2e before workspace-close; ship-loop re-runs the same
suite and burns TAT. Credit is fail-closed on fingerprint mismatch or stale age.

Env:
  SHIP_CREDIT_PASS=0          disable crediting (always re-fire)
  SHIP_FORCE_REFIRE=1         force re-fire even when credit eligible
  SHIP_CREDIT_PASS_MAX_AGE_S  default 7200 (2h)
"""
from __future__ import annotations

import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CREDITS = ROOT / ".cursor" / ".ntest-pass-credits.json"
PENDING = ROOT / ".cursor" / ".pending-ship-work.json"


def _utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _parse_utc(s: str | None) -> datetime | None:
    if not s:
        return None
    try:
        return datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def max_age_s() -> int:
    try:
        return max(60, int(os.environ.get("SHIP_CREDIT_PASS_MAX_AGE_S", "7200")))
    except ValueError:
        return 7200


def credit_enabled() -> bool:
    if os.environ.get("SHIP_FORCE_REFIRE", "").strip() in ("1", "true", "yes"):
        return False
    return os.environ.get("SHIP_CREDIT_PASS", "1").strip().lower() not in (
        "0",
        "false",
        "no",
        "off",
    )


def pending_paths(root: Path | None = None) -> list[str]:
    root = root or ROOT
    p = root / ".cursor" / ".pending-ship-work.json"
    if not p.is_file():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return []
    out: list[str] = []
    for rel in data.get("files") or []:
        rel = str(rel).replace("\\", "/")
        if rel.startswith("scripts/scratch/"):
            continue
        out.append(rel)
    return sorted(set(out))


def fingerprint_paths(paths: list[str], root: Path | None = None) -> str:
    """Stable sha256 of path→content for pending ship files (missing=empty)."""
    root = root or ROOT
    h = hashlib.sha256()
    for rel in sorted({str(p).replace("\\", "/") for p in paths}):
        h.update(rel.encode("utf-8"))
        h.update(b"\0")
        fp = root / rel
        if fp.is_file():
            h.update(fp.read_bytes())
        h.update(b"\0")
    return h.hexdigest()[:32]


def current_fingerprint(root: Path | None = None) -> str:
    return fingerprint_paths(pending_paths(root), root)


def _load_credits(root: Path | None = None) -> dict:
    root = root or ROOT
    path = root / ".cursor" / ".ntest-pass-credits.json"
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def _save_credits(data: dict, root: Path | None = None) -> None:
    root = root or ROOT
    path = root / ".cursor" / ".ntest-pass-credits.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")


def record_pass(case_id: str, duration_s: float = 0.0, root: Path | None = None) -> dict:
    """Record PASS credit with current pending fingerprint (call from ntest on success)."""
    root = root or ROOT
    paths = pending_paths(root)
    fp = fingerprint_paths(paths, root) if paths else "no-pending"
    data = _load_credits(root)
    row = {
        "at": _utc(),
        "fp": fp,
        "paths": paths,
        "duration_s": round(float(duration_s), 2),
        "source": "ntest",
    }
    data[case_id] = row
    data["_updated"] = _utc()
    _save_credits(data, root)
    return row


def clear_pass(case_id: str, root: Path | None = None) -> None:
    root = root or ROOT
    data = _load_credits(root)
    if case_id in data:
        data.pop(case_id, None)
        data["_updated"] = _utc()
        _save_credits(data, root)


def credit_eligible(case_id: str, root: Path | None = None) -> tuple[bool, str]:
    """Return (ok, reason). ok=True means ship-loop may skip re-fire."""
    root = root or ROOT
    if not credit_enabled():
        return False, "credit disabled (SHIP_CREDIT_PASS=0 or SHIP_FORCE_REFIRE=1)"
    data = _load_credits(root)
    row = data.get(case_id)
    if not isinstance(row, dict):
        return False, "no credit row"
    at = _parse_utc(row.get("at"))
    if not at:
        return False, "credit missing at"
    age = (datetime.now(timezone.utc) - at).total_seconds()
    if age > max_age_s():
        return False, f"credit stale age={int(age)}s max={max_age_s()}s"
    paths = pending_paths(root)
    fp_now = fingerprint_paths(paths, root) if paths else "no-pending"
    fp_was = str(row.get("fp") or "")
    if not fp_was:
        return False, "credit missing fp"
    if fp_was == "no-pending" and fp_now != "no-pending":
        # Pass recorded before pending existed — allow if telemetry last pass is fresh
        # and we re-bind credit to current fp only when paths empty at pass... refuse.
        return False, "credit was no-pending; pending now set — re-fire once"
    if fp_was != fp_now:
        return False, "pending fingerprint changed since PASS"
    return True, f"credit PASS at={row.get('at')} age={int(age)}s fp={fp_was[:8]}"


def filter_cases_for_ship(
    case_ids: list[str], root: Path | None = None
) -> tuple[list[str], list[tuple[str, str]]]:
    """Split into (must_run, credited) where credited is list of (case_id, reason)."""
    must: list[str] = []
    credited: list[tuple[str, str]] = []
    for cid in case_ids:
        if not cid:
            continue
        ok, reason = credit_eligible(cid, root)
        if ok:
            credited.append((cid, reason))
        else:
            must.append(cid)
    return must, credited


def main() -> int:
    import argparse

    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("cmd", choices=["status", "eligible", "record", "fp", "filter"])
    ap.add_argument("--case", action="append", default=[])
    ap.add_argument("--duration", type=float, default=0.0)
    args = ap.parse_args()
    if args.cmd == "fp":
        print(current_fingerprint())
        return 0
    if args.cmd == "status":
        print(json.dumps(_load_credits(), indent=2))
        return 0
    if args.cmd == "record":
        for c in args.case:
            print(json.dumps(record_pass(c, args.duration)))
        return 0
    if args.cmd == "eligible":
        for c in args.case:
            ok, reason = credit_eligible(c)
            print(f"{c}: {'YES' if ok else 'NO'} — {reason}")
        return 0
    if args.cmd == "filter":
        must, credited = filter_cases_for_ship(args.case)
        print("MUST_RUN", " ".join(must))
        for c, r in credited:
            print(f"CREDIT {c} — {r}")
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
