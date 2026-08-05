#!/usr/bin/env python3
"""Append-only learning bus — skills/scripts share facts through JSONL events."""

from __future__ import annotations

import json
import calendar
import time
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
BUS = ROOT / "cursor-bundle/flow-test/learning_bus.jsonl"

VALID_TYPES = frozenset({
    "scan_complete",
    "test_pass",
    "test_fail",
    "gotcha",
    "fix_captured",
    "gap_discovered",
    "fix_shipped",
    "hub_refresh",
    "sanity_pass",
    "sanity_fail",
    "learning_captured",
    "learning_proposed",
    "learning_adopted",
    "learning_verified",
    "learning_stale",
    "plan_computed",
    "plan_escalation",
    "task_closed",
})

# Housekeeping types kept as counters, never as bus rows — they drowned real signal
COUNTER_ONLY_TYPES = frozenset({"hub_refresh"})
COUNTERS = ROOT / "cursor-bundle/flow-test/bus_counters.json"

# High-signal types shown in hub (exclude noisy hub_refresh spam)
SIGNAL_TYPES = frozenset({
    "scan_complete",
    "test_pass",
    "test_fail",
    "gotcha",
    "fix_captured",
    "gap_discovered",
    "fix_shipped",
    "sanity_pass",
    "sanity_fail",
    "learning_captured",
    "learning_proposed",
    "learning_adopted",
    "learning_verified",
    "plan_escalation",
    "task_closed",
})

# Rate-limit noisy event types (seconds between same type+source)
DEDUP_RATE_LIMIT_S: dict[str, int] = {
    "hub_refresh": 300,
    "plan_computed": 60,
}

BUS_MAX_EVENTS = 5000
BUS_MAX_AGE_DAYS = 30


def _parse_ts(ts: str) -> float:
    try:
        return float(calendar.timegm(time.strptime(ts, "%Y-%m-%dT%H:%M:%SZ")))
    except (ValueError, TypeError):
        return 0.0


def _read_all_rows() -> list[dict]:
    if not BUS.is_file():
        return []
    rows: list[dict] = []
    for line in BUS.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    return rows


def _is_rate_limited(event_type: str, source: str, detail: str | None) -> bool:
    window = DEDUP_RATE_LIMIT_S.get(event_type)
    if not window:
        return False
    now = time.time()
    detail_key = (detail or "")[:120]
    for row in reversed(_read_all_rows()[-50:]):
        if row.get("type") != event_type:
            continue
        if row.get("source") != source:
            continue
        if (row.get("detail") or "")[:120] != detail_key:
            continue
        age = now - _parse_ts(row.get("ts", ""))
        if age < window:
            return True
    return False


LEARNINGS = ROOT / "cursor-bundle/brain/testing/learnings.jsonl"
PROMOTED = ROOT / "cursor-bundle/kg/curated/promoted_learnings.jsonl"


def _promote_learnings_to_graph() -> dict:
    """Upgrade 10: verified learnings → curated KG nodes (intake stays on the bus).

    Promotes gotcha/learning rows with a real api + non-probe text into
    diag:/case: nodes in curated/promoted_learnings.jsonl for the next build.
    """
    if not LEARNINGS.is_file():
        return {"promoted": 0, "reason": "no_learnings"}
    existing: set[str] = set()
    if PROMOTED.is_file():
        for line in PROMOTED.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                o = json.loads(line)
                if o.get("id"):
                    existing.add(o["id"])
            except json.JSONDecodeError:
                pass
    new_rows: list[dict] = []
    for line in LEARNINGS.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            o = json.loads(line)
        except json.JSONDecodeError:
            continue
        kind = o.get("kind") or o.get("type") or ""
        api = (o.get("api") or "").strip()
        text = (o.get("text") or o.get("detail") or "").strip()
        if not api or api in ("sanityWorkspace", "unknownApi", "unknown"):
            continue
        if not text or "sanity probe" in text.lower():
            continue
        if kind not in ("gotcha", "learning_verified", "fix_shipped", "learning_adopted", ""):
            # allow plain learnings.jsonl gotchas
            if kind and kind not in ("gotcha",):
                continue
        digest = __import__("hashlib").sha1(f"{api}|{text}".encode()).hexdigest()[:10]
        nid = f"diag:learn.{digest}"
        if nid in existing:
            continue
        existing.add(nid)
        new_rows.append({
            "t": "node",
            "id": nid,
            "kind": "diag",
            "label": f"{api}: {text[:80]}",
            "role": "promoted_learning",
            "src": "brain/testing/learnings.jsonl",
            "api": api,
            "note": text[:240],
        })
    if not new_rows:
        return {"promoted": 0, "existing": len(existing)}
    PROMOTED.parent.mkdir(parents=True, exist_ok=True)
    with PROMOTED.open("a", encoding="utf-8") as f:
        if PROMOTED.stat().st_size == 0:
            f.write("# Promoted learnings — written by learning_bus.compact_bus; consumed by build_curated.py\n")
        for row in new_rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    return {"promoted": sum(1 for r in new_rows if r.get("t") == "node"), "ids": [r["id"] for r in new_rows if r.get("t") == "node"][:5]}


def compact_bus(*, max_events: int = BUS_MAX_EVENTS, max_age_days: int = BUS_MAX_AGE_DAYS) -> dict:
    """Trim bus to max_events / max age, then promote verified learnings into the KG curated layer."""
    rows = _read_all_rows()
    promo = _promote_learnings_to_graph()
    if not rows:
        return {"before": 0, "after": 0, "removed": 0, "graph_promote": promo}
    cutoff = time.time() - max_age_days * 86400
    kept = [
        r for r in rows
        if _parse_ts(r.get("ts", "")) >= cutoff and r.get("type") not in COUNTER_ONLY_TYPES
    ]
    if len(kept) > max_events:
        kept = kept[-max_events:]
    removed = len(rows) - len(kept)
    if removed > 0:
        header = "# Learning bus — append-only; skills read/write via learning_bus.py\n"
        BUS.parent.mkdir(parents=True, exist_ok=True)
        with BUS.open("w", encoding="utf-8") as f:
            f.write(header)
            for row in kept:
                f.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
    return {
        "before": len(rows),
        "after": len(kept) if removed > 0 else len(rows),
        "removed": max(0, removed),
        "graph_promote": promo,
    }


def _maybe_rotate() -> None:
    rows = _read_all_rows()
    if len(rows) <= BUS_MAX_EVENTS:
        return
    compact_bus()


def load_counters() -> dict:
    if COUNTERS.is_file():
        try:
            return json.loads(COUNTERS.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            pass
    return {}


def bump_counter(event_type: str, source: str) -> dict:
    data = load_counters()
    key = f"{event_type}:{source}"
    row = data.get(key) or {"count": 0}
    row["count"] = int(row.get("count") or 0) + 1
    row["last"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    data[key] = row
    COUNTERS.parent.mkdir(parents=True, exist_ok=True)
    COUNTERS.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"counter": True, "type": event_type, "source": source, "count": row["count"]}


def append_event(
    event_type: str,
    *,
    source: str,
    api: str | None = None,
    detail: str | None = None,
    evidence: str | None = None,
    meta: dict[str, Any] | None = None,
    force: bool = False,
) -> dict:
    if event_type not in VALID_TYPES:
        raise ValueError(f"invalid event_type {event_type!r}; allowed: {sorted(VALID_TYPES)}")
    if event_type in COUNTER_ONLY_TYPES:
        return bump_counter(event_type, source)
    if not force and _is_rate_limited(event_type, source, detail):
        return {"skipped": True, "type": event_type, "source": source}
    row = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "type": event_type,
        "source": source,
    }
    if api:
        row["api"] = api
    if detail:
        row["detail"] = detail
    if evidence:
        row["evidence"] = evidence
    if meta:
        row["meta"] = meta
    BUS.parent.mkdir(parents=True, exist_ok=True)
    if not BUS.is_file():
        BUS.write_text("# Learning bus — append-only; skills read/write via learning_bus.py\n", encoding="utf-8")
    with BUS.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
    _maybe_rotate()
    return row


def load_events(limit: int = 50, event_type: str | None = None) -> list[dict]:
    rows = _read_all_rows()
    if event_type:
        rows = [r for r in rows if r.get("type") == event_type]
    return rows[-limit:]


def load_signal_events(limit: int = 10) -> list[dict]:
    rows = [r for r in _read_all_rows() if r.get("type") in SIGNAL_TYPES]
    return rows[-limit:]


def count_by_type() -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in _read_all_rows():
        t = row.get("type", "?")
        counts[t] = counts.get(t, 0) + 1
    return counts


def gotchas_for_api(api: str, limit: int = 20) -> list[dict]:
    return [
        r for r in load_events(limit=500, event_type="gotcha")
        if r.get("api") == api
    ][-limit:]
