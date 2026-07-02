"""Build Novopay request envelopes — no per-API payload files needed."""
from __future__ import annotations

import time
from typing import Any

from .api_client import fresh_stan, substitute_placeholders

# Standard local headers per service (extend here only)
_HEADER_TEMPLATES: dict[str, dict[str, Any]] = {
    "accounting": {
        "tenant_code": "mfi",
        "client_code": "NOVOPAY",
        "channel_code": "WEB",
        "user_id": "{{user_id}}",
        "function_code": "DEFAULT",
        "function_sub_code": "DEFAULT",
        "run_mode": "REAL",
        "stan": "{{$timestamp}}",
        "transmission_datetime": "{{$timestamp}}",
    },
    "actor": {
        "tenant_code": "mfi",
        "client_code": "NOVOPAY",
        "channel_code": "NOVOPAY",
        "end_channel_code": "NOVOPAY",
        "operation_mode": "SELF",
        "run_mode": "REAL",
        "actor_type": "CUSTOMER",
        "function_code": "DEFAULT",
        "function_sub_code": "DEFAULT",
        "stan": "{{$timestamp}}",
        "transmission_datetime": "{{$timestamp}}",
        "user_id": "{{user_id}}",
    },
    "accounting_batch": {
        "tenant_code": "mfi",
        "client_code": "NOVOPAY",
        "channel_code": "WEB",
        "user_id": "{{user_id}}",
        "function_code": "DEFAULT",
        "function_sub_code": "BATCH",
        "run_mode": "REAL",
        "stan": "{{$timestamp}}",
    },
}


def build_envelope(
    service: str,
    request_body: dict[str, Any],
    *,
    stan: str | None = None,
    vars: dict[str, Any] | None = None,
    headers_key: str | None = None,
    batch_job_time: str | None = None,
) -> dict[str, Any]:
    """Assemble {headers, request} for a service API call."""
    vars = dict(vars or {})
    stan = stan or fresh_stan("ntest")
    vars.setdefault("user_id", "3")
    vars.setdefault("$timestamp", stan)

    if batch_job_time is not None:
        hk = "accounting_batch"
        req = {"job_time": str(batch_job_time), "op_code": "START"}
    else:
        hk = headers_key or service
        tpl = _HEADER_TEMPLATES.get(hk) or _HEADER_TEMPLATES["accounting"]
        headers = substitute_placeholders(dict(tpl), stan, vars)
        req = substitute_placeholders(dict(request_body), stan, vars)
        return {"headers": headers, "request": req}

    tpl = _HEADER_TEMPLATES[hk]
    headers = substitute_placeholders(dict(tpl), stan, vars)
    return {"headers": headers, "request": req}


def batch_envelope(api_name: str, job_time: str | None = None, stan: str | None = None) -> dict[str, Any]:
    jt = job_time or str(int(time.time() * 1000))
    s = stan or fresh_stan(api_name)
    h = substitute_placeholders(dict(_HEADER_TEMPLATES["accounting_batch"]), s, {"user_id": "3"})
    h["stan"] = f"{s}_{api_name}"
    return {"headers": h, "request": {"job_time": jt, "op_code": "START"}}
