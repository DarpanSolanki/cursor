#!/usr/bin/env python3
"""build_contracts.py — cross-service HTTP + Kafka contracts for KG."""

import sys
from pathlib import Path

BIN = Path(__file__).resolve().parent
sys.path.insert(0, str(BIN))

from _contract_scan import emit_kg_jsonl, scan_workspace  # noqa: E402
from _paths import WORKSPACE  # noqa: E402


def main() -> None:
    repos = [a for a in sys.argv[1:] if not a.startswith("-")]
    result = scan_workspace(WORKSPACE, repos if repos else None)
    for obj in emit_kg_jsonl(result):
        print(__import__("json").dumps(obj, ensure_ascii=False))


if __name__ == "__main__":
    main()
