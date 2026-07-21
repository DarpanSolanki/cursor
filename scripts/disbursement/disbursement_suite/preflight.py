"""Lightweight disburseLoan preflight — accounting + simulator (+ optional Kafka path)."""
from __future__ import annotations

import socket
import subprocess
from dataclasses import dataclass, field
from typing import Any
from urllib.error import URLError
from urllib.request import urlopen


@dataclass
class PreflightResult:
    ok: bool
    blocker: str | None = None
    details: list[dict[str, Any]] = field(default_factory=list)


def _tcp(host: str, port: int, timeout: float = 3.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _kafka_consumer_assigned(
    *,
    bootstrap: str = "127.0.0.1:9092",
    group: str = "disburse_loan_api_consumer_mfi_local",
    kafka_home: str = "/home/darpan/Documents/kafka_2.12-3.7.0",
) -> tuple[bool, str]:
    script = f"{kafka_home}/bin/kafka-consumer-groups.sh"
    try:
        out = subprocess.check_output(
            [script, "--bootstrap-server", bootstrap, "--describe", "--group", group],
            stderr=subprocess.STDOUT,
            text=True,
            timeout=20,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired) as exc:
        return False, str(exc)
    for line in out.splitlines():
        parts = line.split()
        # GROUP TOPIC PARTITION CURRENT-OFFSET LOG-END-OFFSET LAG CONSUMER-ID HOST CLIENT-ID
        if len(parts) >= 7 and parts[0] == group and parts[6] != "-":
            return True, f"member={parts[6]}"
    return False, "no active members"


def run(
    *,
    accounting_base_url: str = "http://localhost:8002",
    accounting_context_path: str = "/accounting",
    simulator_host: str = "localhost",
    simulator_port: int = 8018,
    require_kafka: bool = False,
    los_host: str = "localhost",
    los_port: int = 8013,
    actor_host: str = "localhost",
    actor_port: int = 8003,
    masterdata_host: str = "localhost",
    masterdata_port: int = 8014,
    kafka_bootstrap_host: str = "127.0.0.1",
    kafka_bootstrap_port: int = 9092,
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

    if _tcp(simulator_host, simulator_port):
        details.append(
            {
                "check": "simulator_tcp",
                "ok": True,
                "actual": f"{simulator_host}:{simulator_port}",
            }
        )
    else:
        details.append({"check": "simulator_tcp", "ok": False, "actual": "connection refused"})
        return PreflightResult(
            ok=False,
            blocker=f"bank simulator unavailable at {simulator_host}:{simulator_port}",
            details=details,
        )

    if not require_kafka:
        return PreflightResult(ok=True, details=details)

    if not _tcp(los_host, los_port):
        details.append({"check": "los_tcp", "ok": False, "actual": f"{los_host}:{los_port}"})
        return PreflightResult(
            ok=False,
            blocker=f"LOS unavailable at {los_host}:{los_port} (Kafka producer path)",
            details=details,
        )
    details.append({"check": "los_tcp", "ok": True, "actual": f"{los_host}:{los_port}"})

    if not _tcp(actor_host, actor_port):
        details.append({"check": "actor_tcp", "ok": False, "actual": f"{actor_host}:{actor_port}"})
        return PreflightResult(
            ok=False,
            blocker=f"actor unavailable at {actor_host}:{actor_port} (getCustomerDetails)",
            details=details,
        )
    details.append({"check": "actor_tcp", "ok": True, "actual": f"{actor_host}:{actor_port}"})

    if not _tcp(masterdata_host, masterdata_port):
        details.append(
            {"check": "masterdata_tcp", "ok": False, "actual": f"{masterdata_host}:{masterdata_port}"}
        )
        return PreflightResult(
            ok=False,
            blocker=f"masterdata unavailable at {masterdata_host}:{masterdata_port} (getBulkUniqueMasterData)",
            details=details,
        )
    details.append(
        {"check": "masterdata_tcp", "ok": True, "actual": f"{masterdata_host}:{masterdata_port}"}
    )

    if not _tcp(kafka_bootstrap_host, kafka_bootstrap_port):
        details.append(
            {
                "check": "kafka_tcp",
                "ok": False,
                "actual": f"{kafka_bootstrap_host}:{kafka_bootstrap_port}",
            }
        )
        return PreflightResult(
            ok=False,
            blocker=f"Kafka unavailable at {kafka_bootstrap_host}:{kafka_bootstrap_port}",
            details=details,
        )
    details.append(
        {
            "check": "kafka_tcp",
            "ok": True,
            "actual": f"{kafka_bootstrap_host}:{kafka_bootstrap_port}",
        }
    )

    assigned, actual = _kafka_consumer_assigned()
    details.append({"check": "kafka_consumer_assigned", "ok": assigned, "actual": actual})
    if not assigned:
        return PreflightResult(
            ok=False,
            blocker=(
                "Kafka consumer group disburse_loan_api_consumer_mfi_local has no active members — "
                "ensure accounting with LmsMessageBrokerConsumer"
            ),
            details=details,
        )

    return PreflightResult(ok=True, details=details)
