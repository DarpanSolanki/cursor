"""
Ship-loop outbox helpers.

Some workspace variants persist ship-loop results to an outbox for later enrichment.
This repository keeps a minimal implementation so ship-loop tooling remains runnable.
"""

from __future__ import annotations


def record_gate_passed(*, tier: str, apis: list[str], extra: dict | None = None) -> None:
    # Intentionally a no-op for this workspace.
    _ = (tier, apis, extra)


def log_outbox_error(ex: Exception, where: str) -> None:
    # Best-effort; do not break ship loop on outbox errors.
    _ = (ex, where)

