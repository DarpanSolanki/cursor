#!/usr/bin/env python3
"""TDPFR-547 — PROCESSOR_MIRROR_SIM for DPI Kafka fields on recurring payment.

Full E2E needs loanRecurringPaymentBatchApi chunk with LAN-A (has DPI) then
LAN-B (no DPI) + Kafka/payments assert. This case proves the write-path fix
on disk:

1. dpi_due / dpi_overdue are built from fresh per-LAN amountMap.getOrDefault
2. Those payload puts no longer read DPI_* from shared ExecutionContext
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
JAVA = (
    ROOT
    / "trustt-platform-accounting"
    / "src/main/java/in/novopay/accounting/loan/recurring/batch"
    / "LoanRecurringPaymentBatchProcessor.java"
)


def _require(cond: bool, msg: str) -> None:
    if not cond:
        print(f"FAIL: {msg}", file=sys.stderr)
        raise SystemExit(1)


def main() -> int:
    print("Verify mode: PROCESSOR_MIRROR_SIM")
    print(
        "Blocker (full E2E): needs recurring-payment chunk order "
        "[hasDPI, noDPI] + Kafka/collection dpi_overdue assert"
    )
    text = JAVA.read_text(encoding="utf-8")
    _require(JAVA.is_file(), f"missing {JAVA}")

    dpi_due = re.search(
        r'dueDetails\.put\(\s*"dpi_due"\s*,\s*String\.valueOf\(\s*'
        r"amountMap\.getOrDefault\(\s*AccountingConstants\.DPI_DUE_AMOUNT\s*,\s*"
        r"BigDecimal\.ZERO\s*\)\s*\)\s*\)\s*;",
        text,
    )
    dpi_od = re.search(
        r'dueDetails\.put\(\s*"dpi_overdue"\s*,\s*String\.valueOf\(\s*'
        r"amountMap\.getOrDefault\(\s*AccountingConstants\.DPI_OVERDUE_AMOUNT\s*,\s*"
        r"BigDecimal\.ZERO\s*\)\s*\)\s*\)\s*;",
        text,
    )
    _require(bool(dpi_due), "dpi_due must use amountMap.getOrDefault(DPI_DUE_AMOUNT, ZERO)")
    _require(
        bool(dpi_od),
        "dpi_overdue must use amountMap.getOrDefault(DPI_OVERDUE_AMOUNT, ZERO)",
    )

    stale_due = re.search(
        r'dueDetails\.put\(\s*"dpi_due"\s*,\s*String\.valueOf\(\s*'
        r"executionContext\.getValue\(\s*AccountingConstants\.DPI_DUE_AMOUNT",
        text,
    )
    stale_od = re.search(
        r'dueDetails\.put\(\s*"dpi_overdue"\s*,[\s\S]{0,200}?'
        r"executionContext\.getValue\(\s*AccountingConstants\.DPI_OVERDUE_AMOUNT",
        text,
    )
    _require(stale_due is None, "dpi_due must not read DPI_DUE_AMOUNT from ExecutionContext")
    _require(
        stale_od is None,
        "dpi_overdue must not read DPI_OVERDUE_AMOUNT from ExecutionContext",
    )

    _require(
        "Map<String, BigDecimal> amountMap = new HashMap<>()" in text,
        "amountMap must be created fresh per LAN in processEachAccountWithPrefetchedData",
    )

    print("PROCESSOR_MIRROR_SIM PASS: dpi_due/dpi_overdue from amountMap zero-default")
    print("PASS: collections.tdpfr547_dpi_amountmap_sim (TDPFR-547)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
