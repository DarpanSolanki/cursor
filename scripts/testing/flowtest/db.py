"""Shared psql helpers for flowtest + DCF wrappers."""
from __future__ import annotations

import os
import subprocess
import time

PG_ENV = {**os.environ, "PGPASSWORD": os.environ.get("PGPASSWORD", "yugabyte")}
PG = [
    "psql",
    "-h",
    os.environ.get("YB_HOST", "localhost"),
    "-p",
    os.environ.get("YB_PORT", "5433"),
    "-U",
    os.environ.get("YB_USER", "yugabyte"),
    "-d",
    os.environ.get("YB_DB", "yugabyte"),
    "-v",
    "ON_ERROR_STOP=1",
    "-t",
    "-A",
]
SCH = "mfi_accounting"


def psql(sql: str) -> str:
    """Single-row psql with YB timeout retry."""
    last: BaseException | None = None
    for attempt in range(1, 5):
        try:
            out = subprocess.check_output(
                [*PG, "-c", sql], env=PG_ENV, text=True, stderr=subprocess.STDOUT
            )
            return out.strip().split("\n")[0] if out.strip() else ""
        except subprocess.CalledProcessError as exc:
            last = exc
            err = (exc.output or "") if isinstance(getattr(exc, "output", None), str) else ""
            if not err and exc.stderr:
                err = exc.stderr if isinstance(exc.stderr, str) else exc.stderr.decode(
                    "utf-8", "replace"
                )
            transient = any(
                s in err
                for s in (
                    "Timed out waiting",
                    "kProcessingRequest",
                    "Connection refused",
                    "could not connect",
                    "server closed the connection",
                )
            )
            if not transient or attempt == 4:
                raise
            time.sleep(min(2 * attempt, 6))
    raise last or RuntimeError("psql failed")


def psql_multi(sql: str) -> None:
    subprocess.check_call([*PG[:-2], "-v", "ON_ERROR_STOP=1", "-c", sql], env=PG_ENV)


def psql_raw(sql: str) -> str:
    return subprocess.check_output([*PG, "-c", sql], env=PG_ENV, text=True)
