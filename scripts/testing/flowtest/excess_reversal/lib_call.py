from __future__ import annotations

import json
import os
import subprocess
import time
import urllib.error
import urllib.request
from pathlib import Path

ACCT_URL = os.environ.get("ACCOUNTING_URL", "http://localhost:8002/accounting/api/v1")
PG = [
    "psql",
    "-h", os.environ.get("YB_HOST", "127.0.0.1"),
    "-p", os.environ.get("YB_PORT", "5433"),
    "-U", os.environ.get("YB_USER", "yugabyte"),
    "-d", os.environ.get("YB_DB", "yugabyte"),
    "-t", "-A", "-v", "ON_ERROR_STOP=1",
]


def psql(sql: str) -> str:
    out = subprocess.check_output(
        PG + ["-c", sql],
        env={**os.environ, "PGPASSWORD": os.environ.get("PGPASSWORD", "yugabyte")},
        text=True,
    )
    return out.strip()


def hdr(stan: str, *, function_code: str = "DEFAULT", function_sub_code: str = "DEFAULT") -> dict:
    return {
        "tenant_code": "mfi",
        "client_code": "NOVOPAY",
        "channel_code": "WEB",
        "end_channel_code": "NOVOPAY",
        "function_code": function_code,
        "function_sub_code": function_sub_code,
        "run_mode": "REAL",
        "operation_mode": "SELF",
        "locale": "en-in",
        "stan": stan,
        "transmission_datetime": str(int(time.time() * 1000)),
        "user_id": os.environ.get("ICF_USER_ID", "103"),
        "actor_type": "EMPLOYEE",
        "user_handle_value": os.environ.get("ICF_USER_ID", "103"),
        "office_id": os.environ.get("ICF_OFFICE_ID", "2"),
    }


def post(api: str, body: dict) -> dict:
    data = json.dumps(body).encode()
    req = urllib.request.Request(
        f"{ACCT_URL}/{api}", data=data, headers={"Content-Type": "application/json"}, method="POST"
    )
    try:
        with urllib.request.urlopen(req, timeout=180) as resp:
            return json.loads(resp.read())
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            return json.loads(raw)
        except Exception:
            return {"response_status": {"status": "HTTP_" + str(e.code), "message": raw[:400].decode(errors="replace")}}


def st(resp: dict) -> tuple[str, str, str]:
    s = resp.get("response_status", {})
    return str(s.get("code")), str(s.get("status")), str(s.get("message", ""))[:200]


def write_sql(sql: str, name: str) -> None:
    root = Path(__file__).resolve().parents[4]
    scratch = root / "scripts" / "scratch" / "excess-reversal"
    scratch.mkdir(parents=True, exist_ok=True)
    path = scratch / f"{name}.sql"
    path.write_text(sql)
    subprocess.check_call(["bash", str(root / "scripts" / "bin" / "db-local-write.sh"), "--file", str(path)])
