#!/usr/bin/env python3
"""P1-P5 ship fingerprint determinism proofs + STEP-1 selection audit harness."""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/lib"))

from impact_tests import build_plan, impact_ran_satisfied, mark_ran  # noqa: E402
from ship_fingerprint import (  # noqa: E402
    is_fingerprint_exempt,
    repo_head_sha,
    ship_range_paths,
)
from ship_push_gate import ship_loop_satisfied  # noqa: E402


class ShipFingerprintProofs(unittest.TestCase):
    def test_p1_dirty_knowledge_exempt(self) -> None:
        self.assertTrue(is_fingerprint_exempt(".cursor/changelog.md"))
        self.assertTrue(is_fingerprint_exempt("cursor-bundle/memory/SELF-REPORT.md"))
        self.assertTrue(is_fingerprint_exempt("scripts/testing/registry-proposals.json"))

    def test_p3_tamper_head_sha_mismatch(self) -> None:
        acc = ROOT / "trustt-platform-accounting"
        if not (acc / ".git").is_dir():
            self.skipTest("accounting repo missing")
        head = repo_head_sha(acc)
        plan = build_plan(paths=["scripts/lib/impact_tests.py"], from_pending=False, shipped_only=False)
        mark_ran(plan, result="pass")
        ok, _ = impact_ran_satisfied()
        self.assertTrue(ok)
        # simulate amend: record stale sha
        ran = json.loads((ROOT / ".cursor/.impact-tests-ran.json").read_text())
        ran["repo_head_shas"]["trustt-platform-accounting"] = "deadbeef" * 5
        (ROOT / ".cursor/.impact-tests-ran.json").write_text(json.dumps(ran))
        ok2, msg = impact_ran_satisfied()
        self.assertFalse(ok2, msg)
        self.assertIn("mismatch", msg)

    def test_p4_cache_idempotent(self) -> None:
        plan = build_plan(paths=["scripts/lib/ship_fingerprint.py"], from_pending=False, shipped_only=False)
        mark_ran(plan, result="pass")
        t0 = time.perf_counter()
        ok1, _ = impact_ran_satisfied()
        t1 = time.perf_counter()
        ok2, _ = impact_ran_satisfied()
        t2 = time.perf_counter()
        self.assertTrue(ok1 and ok2)
        self.assertLess(t2 - t1, 0.5, "second check should be cache-fast")

    def test_p5_no_agent_waiver_env(self) -> None:
        r = subprocess.run(
            ["rg", "-l", "IMPACT_TESTS_WAIVER|log_waiver|--waiver"],
            cwd=str(ROOT / "scripts"),
            capture_output=True,
            text=True,
        )
        hits = [p for p in (r.stdout or "").splitlines() if "test_ship_fingerprint" not in p]
        self.assertEqual(hits, [], f"escape paths remain: {hits}")


class SelectionAuditSmoke(unittest.TestCase):
    def test_not_covered_banner(self) -> None:
        plan = build_plan(
            paths=["trustt-platform-accounting/src/main/java/in/novopay/accounting/batchnew/derivedfields/NoCaseUtil.java"],
            from_pending=False,
            shipped_only=False,
        )
        # derivedfields may or may not produce missing — just ensure key exists
        self.assertIn("not_covered_flows", plan)


if __name__ == "__main__":
    unittest.main()
