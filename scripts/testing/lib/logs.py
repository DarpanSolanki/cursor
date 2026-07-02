"""Tail service logs after API calls (local RCA)."""
from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

from .paths import ROOT
from .services import SERVICES

ERROR_LINE = re.compile(
    r"\[ERROR\]|\[FATAL\]|NovopayFatal|NovopayNonFatal|BUILD FAILED|Application run failed|writeSkipCount=[1-9]",
    re.IGNORECASE,
)


def service_log_path(service: str = "accounting") -> Path:
    env_key = f"{service.upper()}_LOG"
    override = os.environ.get(env_key) or os.environ.get("ACCOUNTING_LOG", "")
    if override:
        return Path(override)
    rel = SERVICES.get(service, SERVICES["accounting"])["log_rel"]
    return ROOT / rel


def boot_log_path(service: str = "accounting") -> Path:
    return ROOT / "scripts" / "scratch" / "services" / f"{service}-bootrun.log"


def accounting_log_path() -> Path:
    return service_log_path("accounting")


def log_paths(service: str = "accounting") -> dict[str, Path]:
    return {
        "app": service_log_path(service),
        "boot": boot_log_path(service),
        "archive": service_log_path(service).parent / "archive",
    }


def tail_file_lines(log_path: Path, *, max_lines: int = 40) -> list[str]:
    if not log_path.is_file():
        return [f"(log not found: {log_path})"]
    try:
        lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError as ex:
        return [f"(cannot read log: {ex})"]
    return lines[-max_lines:]


def tail_errors(
    log_path: Path | None = None,
    *,
    service: str = "accounting",
    max_lines: int = 30,
    pattern: re.Pattern[str] | None = None,
) -> list[str]:
    path = log_path or service_log_path(service)
    pat = pattern or ERROR_LINE
    if not path.is_file():
        return [f"(log not found: {path})"]
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError as ex:
        return [f"(cannot read log: {ex})"]
    hits = [ln.rstrip() for ln in lines[-8000:] if pat.search(ln)]
    return hits[-max_lines:] if hits else [f"(no error lines in last 8000 lines of {path})"]


def tail_new_lines(
    log_path: Path,
    *,
    since_epoch: float,
    pattern: re.Pattern[str] | None = None,
    max_lines: int = 40,
) -> list[str]:
    """Best-effort: return recent error lines from log tail (since_epoch reserved for future)."""
    _ = since_epoch
    pat = pattern or ERROR_LINE
    return tail_errors(log_path, max_lines=max_lines, pattern=pat)


def run_log_snap(service: str = "accounting") -> str:
    script = ROOT / "scripts" / "bin" / "novopay-logs.sh"
    if not script.is_file():
        return f"(missing {script})"
    try:
        out = subprocess.check_output(
            ["bash", str(script), "snap", service],
            stderr=subprocess.STDOUT,
            text=True,
            timeout=30,
        )
        return out.strip()
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError) as ex:
        return f"(novopay-logs snap failed: {ex})"


def watch_hint(log_path: Path | None = None, service: str = "accounting") -> str:
    p = log_path or service_log_path(service)
    return (
        f"app errors: bash scripts/bin/novopay-logs.sh errors {service}\n"
        f"boot log:    bash scripts/bin/novopay-logs.sh boot {service}\n"
        f"RCA snap:    bash scripts/bin/novopay-logs.sh snap {service}\n"
        f"live tail:   tail -f {p} | grep -E 'ERROR|FATAL|NovopayFatal|writeSkipCount'"
    )
