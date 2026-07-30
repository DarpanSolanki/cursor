"""HTTP client for Novopay service APIs (local dev)."""
from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

from .services import SERVICES, api_url, health_url


@dataclass
class ApiResult:
    api_name: str
    url: str
    http_status: int
    body: str
    elapsed_ms: int

    def response_status(self) -> tuple[str, str]:
        try:
            obj = json.loads(self.body or "{}")
        except json.JSONDecodeError:
            return "", ""
        if not isinstance(obj, dict):
            return "", ""
        rs = obj.get("response_status") or obj.get("responseStatus") or {}
        if not isinstance(rs, dict):
            return "", ""
        return str(rs.get("code") or ""), str(rs.get("status") or "")


def accounting_url(api_name: str) -> str:
    return api_url("accounting", api_name)


# transaction_master.stan is varchar(64) — keep harness STANs inside the contract.
_STAN_MAX_LEN = 64


def fresh_stan(prefix: str = "test") -> str:
    ms = int(time.time() * 1000)
    suffix = f"_{ms}"
    head = (prefix or "test")[: max(1, _STAN_MAX_LEN - len(suffix))]
    return f"{head}{suffix}"


def batch_envelope(api_name: str, *, job_time: str, stan: str | None = None) -> dict[str, Any]:
    # Do not append api_name again — fresh_stan already prefixes; double-append blew past varchar(64).
    stan = stan or fresh_stan(api_name)
    if len(stan) > _STAN_MAX_LEN:
        stan = stan[:_STAN_MAX_LEN]
    return {
        "headers": {
            "tenant_code": "mfi",
            "client_code": "NOVOPAY",
            "channel_code": "WEB",
            "user_id": "3",
            "stan": stan,
            "function_code": "DEFAULT",
            "function_sub_code": "BATCH",
            "run_mode": "REAL",
            # Required: workers inherit headers into postTransaction → transaction_master.operation_mode NOT NULL
            "operation_mode": "SELF",
        },
        "request": {"job_time": str(job_time), "op_code": "START"},
    }


def substitute_placeholders(obj: Any, stan: str, vars: dict[str, Any] | None = None) -> Any:
    vars = vars or {}
    if isinstance(obj, dict):
        return {k: substitute_placeholders(v, stan, vars) for k, v in obj.items()}
    if isinstance(obj, list):
        return [substitute_placeholders(v, stan, vars) for v in obj]
    if isinstance(obj, str):
        s = obj.replace("{{$timestamp}}", stan)
        for key, val in vars.items():
            s = s.replace(f"{{{{{key}}}}}", str(val))
        if re.fullmatch(r"\d{10,13}", s):
            return s
        return s
    return obj


def load_payload(path: str, stan: str | None = None, vars: dict[str, Any] | None = None) -> dict[str, Any]:
    stan = stan or fresh_stan("api")
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return substitute_placeholders(data, stan, vars)


def fire_api(
    api_name: str,
    payload: dict[str, Any],
    *,
    service: str = "accounting",
    timeout_s: float = 60.0,
) -> ApiResult:
    url = api_url(service, api_name)
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(url, data=data, method="POST")
    req.add_header("Content-Type", "application/json")
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            body = resp.read().decode("utf-8", errors="replace")
            return ApiResult(api_name, url, resp.status, body, int((time.time() - t0) * 1000))
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace") if e.fp else ""
        return ApiResult(api_name, url, e.code, body, int((time.time() - t0) * 1000))
    except Exception as ex:
        return ApiResult(api_name, url, 0, str(ex), int((time.time() - t0) * 1000))


def health_check(service: str = "accounting", timeout_s: float = 5.0) -> tuple[bool, str]:
    """Reachability check — 2xx/3xx/503 counts as up (API may still work)."""
    url = health_url(service)
    try:
        with urllib.request.urlopen(url, timeout=timeout_s) as resp:
            ok = resp.status < 500
            return ok, f"HTTP {resp.status} ({service}) @ {url}"
    except urllib.error.HTTPError as e:
        ok = e.code < 500 or e.code == 503
        return ok, f"HTTP {e.code} ({service}) @ {url}"
    except Exception as ex:
        return False, f"{service}: {ex}"
