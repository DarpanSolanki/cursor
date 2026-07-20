"""Lightweight disburseLoan preflight — accounting health probe for disburse-quick.sh."""
from __future__ import annotations

import socket
from dataclasses import dataclass, field
from typing import Any
from urllib.error import URLError
from urllib.request import urlopen


@dataclass
class PreflightResult:
    ok: bool
    blocker: str | None = None
    details: list[dict[str, Any]] = field(default_factory=list)


def run(
    *,
    accounting_base_url: str = "http://localhost:8002",
    accounting_context_path: str = "/accounting",
    simulator_host: str = "localhost",
    simulator_port: int = 8018,
) -> PreflightResult:
    details: list[dict[str, Any]] = []
    probe_url = (
        f"{accounting_base_url.rstrip('/')}{accounting_context_path.rstrip('/')}/api/v1/disburseLoan"
    )
    try:
        import json
        from urllib.request import Request

        req = Request(
            probe_url,
            data=json.dumps({}).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urlopen(req, timeout=12) as resp:
            ok = resp.status == 200
        details.append({"check": "accounting_disburse_probe", "ok": ok, "actual": probe_url})
        if not ok:
            return PreflightResult(ok=False, blocker=f"disburseLoan probe not 200: {probe_url}", details=details)
    except (URLError, OSError) as exc:
        details.append({"check": "accounting_disburse_probe", "ok": False, "actual": str(exc)})
        return PreflightResult(ok=False, blocker=str(exc), details=details)

    try:
        with socket.create_connection((simulator_host, simulator_port), timeout=3):
            pass
        details.append(
            {
                "check": "simulator_tcp",
                "ok": True,
                "actual": f"{simulator_host}:{simulator_port}",
            }
        )
    except OSError as exc:
        details.append({"check": "simulator_tcp", "ok": False, "actual": str(exc)})
        return PreflightResult(
            ok=False,
            blocker=f"bank simulator unavailable at {simulator_host}:{simulator_port}: {exc}",
            details=details,
        )
    return PreflightResult(ok=True, details=details)
