#!/usr/bin/env python3
"""Tests for dynamic impact_tests KG blast-radius resolver."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/lib"))

from impact_tests import (  # noqa: E402
    build_plan,
    format_banner,
    impact_ran_satisfied,
    mark_ran,
)


class ImpactTestsDynamic(unittest.TestCase):
    def test_crn_processor_pulls_sibling_flows(self) -> None:
        path = (
            "trustt-platform-accounting/src/main/java/in/novopay/accounting/"
            "transaction/processor/CreateTransactionMasterProcessor.java"
        )
        plan = build_plan(paths=[path], from_pending=False, draft_stubs=False)
        apis = {f["api"] for f in plan["flows"]}
        self.assertIn("postTransaction", apis)
        # sibling via shared write tables
        self.assertTrue(
            {"postManualJournalEntry", "glBalanceZeroisation", "doGLTransfer"} & apis,
            apis,
        )
        whys = "\n".join(plan.get("why_lines") or [])
        self.assertIn("writes", whys.lower())
        self.assertTrue(
            any("sibling" in w.lower() or "writes" in w.lower() for w in plan.get("why_lines") or []),
            plan.get("why_lines"),
        )

    def test_mark_ran_head_sha(self) -> None:
        path = "scripts/lib/impact_tests.py"
        plan = build_plan(paths=[path], from_pending=False, shipped_only=False)
        mark_ran(plan, result="pass")
        ok, msg = impact_ran_satisfied()
        self.assertTrue(ok or "workspace-only" in msg.lower(), msg)


if __name__ == "__main__":
    unittest.main()
