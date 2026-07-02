"""Compact `expect` block → assertion rules (keeps registry JSON small)."""
from __future__ import annotations

from typing import Any


def expand_expect(expect: dict[str, Any]) -> list[dict[str, Any]]:
    if not expect:
        return [{"type": "http_status", "name": "http_2xx"}]
    rules: list[dict[str, Any]] = [{"type": "http_status", "name": "http_2xx"}]
    if expect.get("status"):
        rules.append({
            "type": "response_status",
            "name": "response_status",
            "status": expect["status"],
            **({"code": expect["code"]} if expect.get("code") else {}),
        })
    for p in expect.get("paths") or []:
        rules.append({"type": "path_exists", "name": f"path:{p}", "path": p})
    for p, v in (expect.get("path_eq") or {}).items():
        rules.append({"type": "path_equals", "name": f"eq:{p}", "path": p, "value": v})
    for p, v in (expect.get("path_gt") or {}).items():
        rules.append({"type": "decimal_gt", "name": f"gt:{p}", "path": p, "value": str(v)})
    if expect.get("any_path_gt"):
        ap = expect["any_path_gt"]
        rules.append({
            "type": "any_path_decimal_gt",
            "name": "any_path_gt",
            "paths": ap.get("paths") or [],
            "value": str(ap.get("value", "0")),
        })
    if expect.get("db_eq"):
        d = expect["db_eq"]
        rules.append({
            "type": "db_matches_path",
            "name": "db_eq",
            "path": d["path"],
            "sql": d["sql"],
        })
    return rules
