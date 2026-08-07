#!/usr/bin/env python3
"""Log a service-tree shell grep and answer it from knowledge we already have.

Reads the hook payload on stdin. One process for both jobs — the previous shell version
spawned four (parse, log, index query, emit) and cost 191ms on the qualifying path.
"""
from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path

ROOT = Path(os.environ.get("CURSOR_PROJECT_DIR") or Path(__file__).resolve().parents[2])
GREP = re.compile(r"(^|[;|&\s])(rg|grep)(\s|$)", re.I)
SERVICE = re.compile(
    r"trustt-platform-|novopay-platform-|novopay-mfi-|orchestration|_orc\.xml|Processor\.java",
    re.I,
)


def main() -> int:
    try:
        cmd = (json.load(sys.stdin).get("command") or "")[:500]
    except Exception:
        return 0
    if not cmd or not GREP.search(cmd) or not SERVICE.search(cmd):
        return 0

    log = ROOT / ".cursor" / "kg-grep-leak.jsonl"
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({
            "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "cmd": cmd,
            "note": "shell_rg_grep_service_tree",
        }, ensure_ascii=False) + "\n")

    report = ROOT / "cursor-bundle" / "memory" / "SELF-REPORT.md"
    if report.is_file():
        n = sum(1 for _ in log.open(encoding="utf-8", errors="replace"))
        line = (f"- grep-leak shell counter (cumulative jsonl lines): **{n}** "
                "(baseline sessions 172 grep / 50 kg — 2026-07-27)\n")
        txt = report.read_text(encoding="utf-8")
        if "grep-leak shell counter" in txt:
            txt = re.sub(r"- grep-leak shell counter.*\n", line, txt, count=1)
        elif "## KG" in txt:
            txt = txt.replace("## KG\n", "## KG\n" + line, 1)
        else:
            txt = txt.rstrip() + "\n\n## KG\n" + line
        report.write_text(txt, encoding="utf-8")

    sys.path.insert(0, str(ROOT / "scripts" / "lib"))
    try:
        import knowledge_index as ki
        hits = ki.ask(ki.terms_from_command(cmd))
    except Exception:
        return 0
    if not hits:
        return 0

    body = "\n".join(f"{term}: {', '.join(refs)}" for term, refs in hits)
    print(json.dumps({"additional_context":
        "KNOWN ALREADY - the workspace documents these terms. "
        "Read these before grepping source:\n" + body +
        "\n(grep-leak hook; index: scripts/lib/knowledge_index.py)"}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
