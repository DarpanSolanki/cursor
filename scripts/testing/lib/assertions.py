"""Declarative API response assertions for api-test specs."""
from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from .api_client import ApiResult
from .config import YB_DB, YB_HOST, YB_PORT, YB_SCHEMA, YB_USER
from .json_path import get_path, path_exists


@dataclass
class AssertResult:
    ok: bool
    name: str
    detail: str = ""


@dataclass
class RunResult:
    passed: bool
    results: list[AssertResult] = field(default_factory=list)


def _dec(val: Any) -> Decimal:
    return Decimal(str(val).strip())


def _run_db_scalar(sql: str, env: dict[str, str]) -> str:
    cmd = [
        "psql", "-h", YB_HOST, "-p", str(YB_PORT), "-U", YB_USER, "-d", YB_DB,
        "-v", "ON_ERROR_STOP=1", "-t", "-A", "-c",
        f"SET search_path TO {YB_SCHEMA}; {sql}",
    ]
    e = {"PGPASSWORD": env.get("PGPASSWORD", "yugabyte"), **env}
    raw = subprocess.check_output(cmd, env=e, text=True).strip()
    lines = [ln.strip() for ln in raw.splitlines() if ln.strip() and ln.strip().upper() != "SET"]
    return lines[-1] if lines else ""


def run_assertions(
    body: str,
    result: ApiResult,
    spec: dict[str, Any],
    *,
    env: dict[str, str],
) -> RunResult:
    try:
        obj = json.loads(body or "{}")
    except json.JSONDecodeError as ex:
        return RunResult(False, [AssertResult(False, "json_parse", str(ex))])

    out: list[AssertResult] = []
    for i, rule in enumerate(spec.get("assertions") or []):
        name = rule.get("name") or rule.get("type") or f"assert_{i}"
        t = rule.get("type")
        optional = bool(rule.get("optional"))

        try:
            if t == "http_status":
                lo, hi = rule.get("min", 200), rule.get("max", 299)
                ok = lo <= result.http_status <= hi
                out.append(AssertResult(ok, name, f"HTTP {result.http_status} (expected {lo}-{hi})"))
            elif t == "response_status":
                code, status = result.response_status()
                exp_st = (rule.get("status") or "SUCCESS").upper()
                ok = status.upper() == exp_st
                if rule.get("code"):
                    ok = ok and code == str(rule["code"])
                out.append(AssertResult(ok, name, f"{code}/{status}"))
            elif t == "path_exists":
                ok = path_exists(obj, rule["path"])
                out.append(AssertResult(ok, name, rule["path"]))
            elif t == "path_equals":
                val = get_path(obj, rule["path"])
                exp = str(rule["value"])
                for k, v in env.items():
                    exp = exp.replace(f"${{{k}}}", str(v))
                ok = str(val) == exp
                out.append(AssertResult(ok, name, f"{rule['path']}={val!r} expected {exp!r}"))
            elif t == "decimal_gt":
                val = _dec(get_path(obj, rule["path"]))
                thr = _dec(rule["value"])
                ok = val > thr
                out.append(AssertResult(ok, name, f"{val} > {thr}"))
            elif t == "decimal_gte":
                val = _dec(get_path(obj, rule["path"]))
                thr = _dec(rule["value"])
                ok = val >= thr
                out.append(AssertResult(ok, name, f"{val} >= {thr}"))
            elif t == "any_path_decimal_gt":
                ok = False
                detail = []
                for p in rule.get("paths") or []:
                    if path_exists(obj, p):
                        v = _dec(get_path(obj, p))
                        detail.append(f"{p}={v}")
                        if v > _dec(rule.get("value", "0")):
                            ok = True
                out.append(AssertResult(ok, name, "; ".join(detail) or "no paths"))
            elif t == "db_matches_path":
                sql = rule["sql"]
                for k, v in env.items():
                    sql = sql.replace(f":{k}", str(v))
                db_val = _run_db_scalar(sql, env)
                api_val = str(get_path(obj, rule["path"]))
                ok = _dec(db_val) == _dec(api_val)
                out.append(AssertResult(ok, name, f"db={db_val} api={api_val} @ {rule['path']}"))
            else:
                out.append(AssertResult(False, name, f"unknown assertion type: {t}"))
        except Exception as ex:
            if optional:
                out.append(AssertResult(True, name, f"skipped (optional): {ex}"))
            else:
                out.append(AssertResult(False, name, str(ex)))

    return RunResult(all(r.ok for r in out), out)
