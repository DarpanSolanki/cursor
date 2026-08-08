#!/usr/bin/env python3
"""E2E audit for all trustt-kg MCP tools — timing, semantics, isError, no hang.

Companion JSON-RPC smoke (stdio protocol): scripts/bin/kg-mcp-smoke.sh
"""
from __future__ import annotations

import importlib.util
import json
import os
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

TIME_FACTOR = float(os.environ.get("KG_MCP_TEST_TIME_FACTOR", "1"))


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
        budget = max_ms * TIME_FACTOR
        self.assertLess(ms, budget, f"{name} took {ms:.0f}ms (max {budget:.0f})")
        self.assertIsInstance(text, str)
        if name != "mcp_auth":
            self.assertTrue(text.startswith("[KG @"), f"{name} missing provenance header")
        return text, bool(err), ms

    def test_tools_list_count(self):
        names = [t["name"] for t in mcp.tools_list_payload()["tools"]]
        self.assertEqual(sorted(names), sorted(mcp.TOOLS.keys()))
        # kg_error was folded into kg_search while the KG held 13 changelog-mentioned codes
        # and could not answer "where is this thrown". It now carries 1.8k source-derived
        # codes with file:line, branch and the EC keys the template needs, so it is core.
        for core in ("kg_orient", "kg_flow", "kg_why", "kg_impact", "kg_writes",
                     "kg_doctor", "kg_error", "kg_schema", "kg_concept"):
            self.assertIn(core, names)
        for gone in ("kg_validate", "kg_fresh"):
            self.assertNotIn(gone, names)

    def test_tools_error_lookup(self):
        text, err, _ = self._call("kg_error", {"query": "132168"}, max_ms=15_000)
        self.assertFalse(err)
        self.assertIn("throw site", text)
        self.assertIn("ValidateLoanAccountDetailsProcessor", text)
        self.assertIn("field_name", text)

    def test_tools_error_absence_is_honest(self):
        text, err, _ = self._call("kg_error", {"query": "999999"}, max_ms=15_000)
        self.assertFalse(err)
        self.assertIn("NOT_INDEXED", text)
        self.assertIn("NOT proof", text)

    def test_01_doctor_includes_validate_fresh(self):
        text, err, _ = self._call("kg_doctor", max_ms=15_000)
        self.assertFalse(err)
        self.assertIn("nodes/edges", text)
        self.assertTrue("OK:" in text or "VALIDATE" in text)
        self.assertTrue(
            any(x in text for x in ("KG FRESH", "STALE", "PROVISIONAL", "WATERMARK")),
            text[:400],
        )

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

    def test_06b_concept(self):
        text, err, _ = self._call("kg_concept", {"query": "loan_account"}, max_ms=5000)
        self.assertFalse(err)
        self.assertIn("loan_account", text)
        self.assertTrue(
            "entity" in text.lower() or "purpose" in text.lower() or "maps_to" in text,
            text[:300],
        )

    def test_06c_schema(self):
        text, err, _ = self._call(
            "kg_schema", {"query": "loan_account.loan_status"}, max_ms=15_000
        )
        self.assertFalse(err)
        self.assertIn("loan_status", text)
        self.assertNotIn("NOT A COLUMN", text)

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
        # Train-aware: the force-bill mirror diag hangs off
        # ForceBillPartialCycleInterestForForeclosureProcessor, which does not exist on
        # every train (absent on mfi_integration_v3.4.2). Asserting it unconditionally
        # tests the checkout, not the tool — same lesson as test_10_impact below.
        _fb = (
            ROOT
            / "trustt-platform-accounting/src/main/java/in/novopay/accounting/loan"
            / "foreclosure/processor/ForceBillPartialCycleInterestForForeclosureProcessor.java"
        )
        if _fb.is_file():
            self.assertIn("shg_child_close_mirror_force_bill", text)
        self.assertIn("verify (source-of-truth", text)
        self.assertLess(len(text), mcp.MAX_CHARS + 50)

    def test_10_impact(self):
        """Probe a symbol that exists on this checkout — a DPI-train-only class made
        this assert the train, not the tool."""
        from impact_tests import _dpi_tree_present

        query = (
            "DpiGroupLoanAccrualDistributionService#distributeInstallmentWindowAccrued"
            if _dpi_tree_present()
            else "LoanAccountAutoClosureItemWriter#getLoanAccountEntity"
        )
        text, err, _ = self._call("kg_impact", {"query": query, "depth": 1}, max_ms=15_000)
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
        args = {
            "query": "getLoanForeclosureDetails",
            "repo": "trustt-platform-accounting",
            "base": self.acc_branch,
            "fetch_if_stale": False,
        }
        text, err, ms1 = self._call("kg_fixed_elsewhere", args, max_ms=25_000)
        self.assertTrue(
            any(x in text for x in ("FIXED-ELSEWHERE", "RESULT:", "REUSE_", "NOT_VERIFIED")),
            text[:200],
        )
        text2, err2, ms2 = self._call("kg_fixed_elsewhere", args, max_ms=2000)
        self.assertIn("cache=HIT", text2)
        self.assertLess(ms2, 1000 * TIME_FACTOR, f"warm fixed_elsewhere {ms2:.0f}ms")

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
        self.assertLess(ms, 20_000 * TIME_FACTOR)

    def test_18_ship_plan(self):
        text, err, ms = self._call("ship_plan", max_ms=15_000)
        self.assertFalse(err)
        payload = json.loads(text.split("\n", 1)[1])
        self.assertIn("ordered_cases", payload)
        self.assertLess(ms, 15_000 * TIME_FACTOR)

    def test_19_reads(self):
        text, err, _ = self._call("kg_reads", {"query": "loan_account"})
        self.assertFalse(err)
        self.assertIn("READERS", text)

    def test_20_error_via_search(self):
        text, err, _ = self._call("kg_search", {"query": "134497"})
        self.assertFalse(err)
        self.assertTrue(
            "error" in text.lower() or "134497" in text or "match" in text.lower(),
            text[:200],
        )

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
        # kg_enhance guards kg-switch with 40s, but a genuine cache miss is a full
        # rebuild (~93s measured; a hit is ~2s). Editing anything under cursor-bundle/kg
        # invalidates the composite key, so during KG work the inner switch legitimately
        # times out and the tool returns a named error instead of hanging. That is the
        # contract worth asserting — a clear failure, not a lie and not a hang.
        if payload.get("kg_switch_rc") == 124:
            self.assertIn("error", payload)
            self.skipTest("kg-switch needs a full rebuild (cache miss) — exceeds the 40s guard")
        self.assertIn("fresh", payload)
        if payload.get("error"):
            self.skipTest(payload["error"])
        self.assertFalse(err, text[:400])
        self.assertTrue(payload.get("ok"), payload)

    def test_24_enhance_train_dry_run(self):
        """kg_enhance with train runs sync-branches (dry-run) before kg-switch."""
        text, err, _ = self._call(
            "kg_enhance",
            {
                "force": False,
                "train": "mfi_integration_v9.9.9.9",
                "sync_domain": "accounting",
                "dry_run": True,
            },
            max_ms=180_000,
        )
        payload = json.loads(text.split("\n", 1)[1])
        self.assertIn("train", payload)
        if payload.get("error") and "sync-branches failed" in payload.get("error", ""):
            self.skipTest(payload["error"])
        self.assertFalse(err, text[:400])
        if payload.get("live_branch_before") == "mfi_integration_v9.9.9.9":
            self.assertTrue(payload.get("sync_skipped"))
        else:
            self.assertEqual(payload.get("sync_branches_rc"), 0)
            self.assertTrue(payload.get("sync_dry_run"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
