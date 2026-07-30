#!/usr/bin/env python3
"""E2E audit for all trustt-kg MCP tools — timing, semantics, isError, no hang."""
from __future__ import annotations

import importlib.util
import json
import sys
import time
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MCP = ROOT / "cursor-bundle/kg/mcp/kg_mcp_server.py"

spec = importlib.util.spec_from_file_location("kg_mcp", MCP)
mcp = importlib.util.module_from_spec(spec)
assert spec.loader
sys.path.insert(0, str(ROOT / "cursor-bundle/kg/bin"))
sys.path.insert(0, str(ROOT / "scripts/lib"))
spec.loader.exec_module(mcp)


def _wm_accounting_branch() -> str:
    wm = mcp.kg_mod._load_watermark() or {}
    acc = (wm.get("repos") or {}).get("trustt-platform-accounting") or {}
    return str(acc.get("branch") or "mfi_integration_v3.4.2.4")


class McpE2ETests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.acc_branch = _wm_accounting_branch()

    def _call(self, name: str, args: dict | None = None, *, max_ms: float = 30_000):
        t0 = time.perf_counter()
        text, err = mcp._dispatch_tool(name, args or {})
        ms = (time.perf_counter() - t0) * 1000
        self.assertLess(ms, max_ms, f"{name} took {ms:.0f}ms (max {max_ms:.0f})")
        self.assertIsInstance(text, str)
        self.assertTrue(text.startswith("[KG @"), f"{name} missing provenance header")
        return text, bool(err), ms

    def test_tools_list_count(self):
        names = [t["name"] for t in mcp.tools_list_payload()["tools"]]
        self.assertEqual(len(names), 22)
        self.assertEqual(sorted(names), sorted(mcp.TOOLS.keys()))

    def test_01_validate(self):
        text, err, _ = self._call("kg_validate", max_ms=5000)
        self.assertFalse(err)
        self.assertIn("OK:", text)

    def test_02_fresh(self):
        text, err, _ = self._call("kg_fresh", max_ms=5000)
        self.assertFalse(err)
        self.assertTrue("KG FRESH" in text or "STALE" in text or "PROVISIONAL" in text)

    def test_03_watermark(self):
        text, err, _ = self._call("kg_watermark", max_ms=5000)
        self.assertFalse(err)
        self.assertIn("KG built", text)
        self.assertIn(self.acc_branch, text)

    def test_04_align_ok(self):
        text, err, _ = self._call(
            "kg_align",
            {"repo": "trustt-platform-accounting", "branch": self.acc_branch},
            max_ms=8000,
        )
        self.assertFalse(err, text[:300])
        self.assertIn("ALIGNED", text)

    def test_05_align_misalign(self):
        text, err, _ = self._call(
            "kg_align",
            {"repo": "trustt-platform-accounting", "branch": "mfi_integration_v9.9.9.9"},
            max_ms=8000,
        )
        self.assertTrue(err)
        self.assertIn("MISALIGNED", text)

    def test_06_search(self):
        text, err, _ = self._call("kg_search", {"query": "interestAccrualCalculation"})
        self.assertFalse(err)
        self.assertIn("interestAccrualCalculation", text)

    def test_07_flow(self):
        text, err, _ = self._call("kg_flow", {"query": "interestAccrualCalculation"})
        self.assertFalse(err)
        self.assertIn("FLOW", text)
        self.assertIn("interestAccrualCalculationProcessor", text)

    def test_08_why_curated(self):
        text, err, _ = self._call(
            "kg_why",
            {"query": "interestAccrualCalculation", "auto_cap": 0},
            max_ms=15_000,
        )
        self.assertFalse(err)
        self.assertIn("WHY", text)
        self.assertIn("shg_parent_child_interest_accrued_rupee", text)

    def test_09_orient_brief_nested(self):
        text, err, ms = self._call(
            "kg_orient",
            {"query": "childLoanForeclosure", "brief": True},
            max_ms=20_000,
        )
        self.assertFalse(err, text[:400])
        self.assertIn("ORIENT", text)
        self.assertIn("individualChildLoanForeclosure", text)
        self.assertIn("shg_child_close_mirror_force_bill", text)
        self.assertIn("verify (source-of-truth", text)
        self.assertLess(len(text), mcp.MAX_CHARS + 50)

    def test_10_impact(self):
        text, err, _ = self._call(
            "kg_impact",
            {"query": "InterestAccrualBookingService#adjustChildLoanAccountsInterestAccrual", "depth": 1},
            max_ms=15_000,
        )
        self.assertFalse(err)
        self.assertIn("IMPACT", text)

    def test_11_crud(self):
        text, err, _ = self._call("kg_crud", {"query": "childLoanForeclosure"})
        self.assertFalse(err)
        self.assertIn("FOOTPRINT", text)

    def test_12_writes(self):
        text, err, _ = self._call("kg_writes", {"query": "interest_accrual_details"})
        self.assertFalse(err)
        self.assertIn("WRITERS", text)

    def test_13_cases(self):
        text, err, _ = self._call("kg_cases", {"query": "disburseLoan"})
        self.assertFalse(err)
        self.assertIn("PRECEDENT", text)

    def test_14_fixed_elsewhere(self):
        text, err, _ = self._call(
            "kg_fixed_elsewhere",
            {
                "query": "getLoanForeclosureDetails",
                "repo": "trustt-platform-accounting",
                "base": self.acc_branch,
            },
            max_ms=25_000,
        )
        # exit 3 advisory is not MCP error — output may be REUSE_FORBIDDEN when upstream stale
        self.assertTrue(
            any(x in text for x in ("FIXED-ELSEWHERE", "RESULT:", "REUSE_", "NOT_VERIFIED")),
            text[:200],
        )

    def test_15_map_audit(self):
        text, err, _ = self._call("kg_map_audit", {"fail_on_mismatch": False}, max_ms=30_000)
        payload = json.loads(text.split("\n", 1)[1])
        self.assertIn("verdict", payload)

    def test_16_mcp_auth(self):
        text, err, _ = self._call("mcp_auth", max_ms=2000)
        self.assertFalse(err)
        self.assertIn("auth_required", text)

    def test_17_workspace_status(self):
        text, err, ms = self._call("workspace_status", max_ms=20_000)
        self.assertFalse(err)
        payload = json.loads(text.split("\n", 1)[1])
        self.assertIn("kg", payload)
        self.assertIn("fresh", payload["kg"])
        self.assertLess(ms, 20_000)

    def test_18_ship_plan(self):
        text, err, ms = self._call("ship_plan", max_ms=15_000)
        self.assertFalse(err)
        payload = json.loads(text.split("\n", 1)[1])
        self.assertIn("ordered_cases", payload)
        self.assertLess(ms, 15_000)

    def test_19_reads(self):
        text, err, _ = self._call("kg_reads", {"query": "loan_account"})
        self.assertFalse(err)
        self.assertIn("READERS", text)

    def test_20_error(self):
        text, err, _ = self._call("kg_error", {"query": "ACCT"})
        self.assertFalse(err)
        self.assertTrue("error" in text.lower() or "seen in" in text.lower() or "not seen" in text.lower())

    def test_21_doctor(self):
        text, err, _ = self._call("kg_doctor", max_ms=15_000)
        self.assertFalse(err)
        self.assertIn("nodes/edges", text)

    def test_22_node(self):
        text, err, _ = self._call("kg_node", {"query": "request:trustt-platform-accounting/disburseLoan"})
        self.assertFalse(err)
        self.assertIn("OUT", text)

    def test_23_enhance(self):
        text, err, ms = self._call("kg_enhance", {"force": False}, max_ms=180_000)
        payload = json.loads(text.split("\n", 1)[1])
        self.assertIn("kg_switch_rc", payload)
        self.assertIn("fresh", payload)
        if payload.get("error"):
            self.skipTest(payload["error"])
        self.assertFalse(err, text[:400])
        self.assertTrue(payload.get("ok"), payload)


if __name__ == "__main__":
    unittest.main(verbosity=2)
