"""Self-learning test knowledge — append-only JSONL, loaded during failure analysis."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .paths import ROOT

LEARNINGS = ROOT / "cursor-bundle/brain/testing/learnings.jsonl"
META = {
    "kinds": ("correlator", "gotcha", "expect", "canned_sql", "error_code", "setup", "batch"),
    "scope": "Generic flow-test knowledge — append via `ntest learn` or test-learn.sh after verified runs.",
}


def _ensure() -> None:
    LEARNINGS.parent.mkdir(parents=True, exist_ok=True)
    if not LEARNINGS.is_file():
        LEARNINGS.write_text(
            json.dumps(
                {
                    "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "api": "*",
                    "kind": "meta",
                    "text": META["scope"],
                }
            )
            + "\n",
            encoding="utf-8",
        )


def append_learning(
    *,
    api: str,
    kind: str,
    text: str,
    error_code: str = "",
    correlator: str = "",
    value: str = "",
    canned: str = "",
) -> dict[str, Any]:
    _ensure()
    rec: dict[str, Any] = {
        "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "api": api or "*",
        "kind": kind,
        "text": text.strip(),
    }
    if error_code:
        rec["error_code"] = error_code
    if correlator:
        rec["correlator"] = correlator
    if value:
        rec["value"] = value
    if canned:
        rec["canned"] = canned
    with LEARNINGS.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
    try:
        import sys
        from pathlib import Path
        root = ROOT
        sys.path.insert(0, str(root / "scripts/testing"))
        from learning_bus import append_event
        append_event(
            "gotcha",
            source="ntest.learn",
            api=api or "*",
            detail=text.strip(),
            meta={"kind": kind, "error_code": error_code or None},
        )
    except Exception:
        pass
    return rec


def load_learnings(api: str = "", *, limit: int = 200) -> list[dict[str, Any]]:
    if not LEARNINGS.is_file():
        return []
    rows: list[dict[str, Any]] = []
    for line in LEARNINGS.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            o = json.loads(line)
        except json.JSONDecodeError:
            continue
        if o.get("kind") == "meta":
            continue
        a = o.get("api") or "*"
        if api and a not in ("*", api) and not api.lower().startswith(a.lower()):
            if a != "*" and api not in a:
                continue
        rows.append(o)
    return rows[-limit:]


def learnings_for_failure(api: str, body: str) -> list[dict[str, Any]]:
    """Match learnings by api name and error codes in response body."""
    rows = load_learnings(api)
    codes = set(re.findall(r"\b(?:1[0-9]{5}|[3-9][0-9]{4})\b", body))
    out: list[dict[str, Any]] = []
    seen: set[str] = set()
    for r in rows:
        ec = r.get("error_code")
        if ec and ec in codes:
            key = f"ec:{ec}:{r.get('text','')[:40]}"
            if key not in seen:
                seen.add(key)
                out.append(r)
    for r in rows:
        if not r.get("error_code"):
            key = f"{r.get('kind')}:{r.get('text','')[:50]}"
            if key not in seen and len(out) < 8:
                seen.add(key)
                out.append(r)
    return out[:8]


def format_learnings_block(api: str, body: str) -> str:
    hits = learnings_for_failure(api, body)
    if not hits:
        return ""
    lines = ["\n### Prior test learnings (brain/testing/learnings.jsonl)"]
    for r in hits:
        tag = r.get("kind", "?")
        t = r.get("text", "")
        extra = ""
        if r.get("correlator"):
            extra += f" `{r['correlator']}`"
        if r.get("canned"):
            extra += f" → canned `{r['canned']}`"
        if r.get("error_code"):
            extra += f" (code {r['error_code']})"
        lines.append(f"- **[{tag}]** {t}{extra}")
    lines.append("- Add: `ntest learn --api ... --kind gotcha --text '...'`")
    return "\n".join(lines)
