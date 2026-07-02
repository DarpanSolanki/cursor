"""KG orientation before test/fix (brain-first)."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
KG = ROOT / "cursor-bundle" / "kg" / "bin" / "kg.py"


def kg_query(cmd: str, *args: str, timeout: int = 30) -> str:
    if not KG.is_file():
        return "(kg.py not found)"
    try:
        p = subprocess.run(
            [sys.executable, str(KG), "--no-drift-check", cmd, *args],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        return (p.stdout or p.stderr or "").strip() or f"(empty, rc={p.returncode})"
    except Exception as ex:
        return f"(kg error: {ex})"


def orient_api(api_name: str) -> str:
    try:
        sys.path.insert(0, str(ROOT / "scripts/testing"))
        from cross_learn import unified_orient
        return unified_orient(api_name)
    except Exception:
        pass
    parts = [
        f"## KG orient: {api_name}\n",
        "### Flow\n```\n" + kg_query("flow", api_name) + "\n```\n",
        "### DB footprint\n```\n" + kg_query("crud", api_name)[:2000] + "\n```\n",
        "### Cases (precedents)\n```\n" + kg_query("cases", api_name)[:1200] + "\n```\n",
    ]
    return "\n".join(parts)
