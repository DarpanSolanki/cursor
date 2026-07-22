#!/usr/bin/env python3
"""Unit tests for changelog → case metadata parsing (cross-branch audit)."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

KG_BIN = Path(__file__).resolve().parents[2] / "cursor-bundle" / "kg" / "bin"
sys.path.insert(0, str(KG_BIN))
import build_cases  # noqa: E402


class BuildCasesHeaderTest(unittest.TestCase):
    def test_parse_header_maps_accounting_service_to_repo(self) -> None:
        meta = build_cases.parse_header_fields(
            "2026-07-21 | acct `ac8f185bbc` | accounting-v2 | mfi_integration_v3.7.1 | "
            "TDPFR-547 dpi amountMap"
        )
        self.assertEqual(meta["service"], "accounting-v2")
        self.assertEqual(meta["branch"], "mfi_integration_v3.7.1")
        self.assertEqual(meta["repo"], "trustt-platform-accounting")

    def test_parse_header_finds_branch_anywhere_in_header(self) -> None:
        meta = build_cases.parse_header_fields(
            "2026-07-21 | kg-flow | payments | hotfix | mfi_integration_v3.4.2.5 note"
        )
        self.assertEqual(meta["repo"], "trustt-platform-payments")
        self.assertEqual(meta["branch"], "mfi_integration_v3.4.2.5")


if __name__ == "__main__":
    unittest.main()
