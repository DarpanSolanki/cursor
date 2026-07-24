"""Thin flow runner: restore → fire Request → wait → selected asserts → evidence."""
from __future__ import annotations

import os
import subprocess
import sys
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]

from . import asserts as A
from .db import psql
from .fixture import ensure_snapshot_or_restore
from .lock import acquire_flowtest_lock, mark_lock_held
from .profiles import FixtureProfile


@dataclass
class Scenario:
    """Simple per-flow scenario — dict/module friendly, no YAML DSL."""

    name: str
    api: str  # Request / batch apiName
    profile: FixtureProfile
    parent_lan: str
    # When True, fire via api-fire --batch --job-time
    batch: bool = True
    job_name: str | None = None  # batch_job_instance.job_name (defaults to api)
    setup: Callable[[], dict[str, Any]] | None = None
    asserts: Sequence[Callable[[dict[str, Any]], None]] = field(default_factory=tuple)
    stack_ensure: Callable[[], None] | None = None
    restore: bool = True
    notes: str = ""


def fire_batch(api: str, job_time: str | None = None) -> str:
    jt = job_time or str(int(time.time() * 1000))
    cmd = [
        "python3",
        str(ROOT / "scripts/testing/api-fire.py"),
        api,
        "--batch",
        "--job-time",
        jt,
    ]
    rc = subprocess.call(cmd, cwd=str(ROOT))
    if rc != 0:
        raise RuntimeError(f"batch {api} HTTP fire failed rc={rc}")
    return jt


def max_batch_execution_id(job_name: str) -> int:
    # Prefer shared CLB harness implementation
    sys.path.insert(0, str(ROOT / "scripts/dcf_sanity"))
    from clb_queue_harness import max_batch_execution_id as _max  # noqa: WPS433

    return _max(job_name)


def wait_batch(job_name: str, min_execution_id: int, timeout_s: int = 180) -> str:
    sys.path.insert(0, str(ROOT / "scripts/dcf_sanity"))
    from clb_queue_harness import wait_batch_after  # noqa: WPS433

    status = wait_batch_after(job_name, min_execution_id, timeout_s=timeout_s)
    print(f"  batch {job_name} COMPLETED")
    return status


def run_scenario(scenario: Scenario) -> int:
    """Execute one scenario; returns 0 on PASS."""
    acquire_flowtest_lock()
    print(f"=== flowtest scenario={scenario.name} api={scenario.api} ===")
    print(f"  parent={scenario.parent_lan} profile={scenario.profile.name} batch={scenario.batch}")
    if scenario.notes:
        print(f"  notes: {scenario.notes}")

    if scenario.stack_ensure:
        scenario.stack_ensure()

    if scenario.restore:
        ensure_snapshot_or_restore(scenario.parent_lan, scenario.profile, force_restore=True)

    ctx: dict[str, Any] = {
        "parent_lan": scenario.parent_lan,
        "api": scenario.api,
        "profile": scenario.profile.name,
    }
    if scenario.setup:
        ctx.update(scenario.setup() or {})

    job_name = scenario.job_name or scenario.api
    if scenario.batch:
        before = max_batch_execution_id(job_name)
        jt = fire_batch(scenario.api)
        ctx["job_time"] = jt
        try:
            wait_batch(job_name, before, timeout_s=int(os.environ.get("FLOWTEST_BATCH_TIMEOUT", "180")))
        except RuntimeError as exc:
            print(f"  WARN: batch wait: {exc} (continuing to asserts if setup polled)")
            ctx["batch_warn"] = str(exc)

    for fn in scenario.asserts:
        fn(ctx)

    print(f"=== PASS: flowtest scenario={scenario.name} ===")
    return 0
