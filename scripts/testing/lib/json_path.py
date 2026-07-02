"""Dot/bracket JSON path navigation (e.g. account_overview_list[0].amount_details.dpi_overdue_amount)."""
from __future__ import annotations

import re
from typing import Any

_SEGMENT = re.compile(r"([^.\[\]]+)|\[(\d+)\]")


def get_path(obj: Any, path: str) -> Any:
    if not path:
        return obj
    cur = obj
    for m in _SEGMENT.finditer(path):
        key, idx = m.group(1), m.group(2)
        if key is not None:
            if not isinstance(cur, dict):
                raise KeyError(f"not a map at '{key}' in {path}")
            cur = cur[key]
        else:
            if not isinstance(cur, list):
                raise KeyError(f"not a list at [{idx}] in {path}")
            cur = cur[int(idx)]
    return cur


def path_exists(obj: Any, path: str) -> bool:
    try:
        get_path(obj, path)
        return True
    except (KeyError, IndexError, TypeError):
        return False
