#!/usr/bin/env python3
"""Tests for kg_watermark_gate."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/lib"))

import kg_watermark_gate as g  # noqa: E402


class KgWatermarkGateTest(unittest.TestCase):
    def test_fresh_decide_passes(self) -> None:
        with mock.patch.object(
            g,
            "_kg_decide",
            return_value={"fresh": True, "tier": "skip", "reason": "branch-set current"},
        ):
            self.assertEqual(g.check(hard=True), 0)

    def test_stale_decide_fails(self) -> None:
        with mock.patch.object(
            g,
            "_kg_decide",
            return_value={
                "fresh": False,
                "tier": "full",
                "reason": "trustt-platform-accounting: KG=mfi_integration_v3.4.2.3@abc → now mfi_integration_v3.4.2.4@def",
            },
        ):
            self.assertEqual(g.check(hard=True), 1)

    def test_accounting_mismatch_detected(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            acct = root / "trustt-platform-accounting"
            acct.mkdir()
            (acct / ".git").mkdir()
            kg_data = root / "cursor-bundle/kg/data"
            kg_data.mkdir(parents=True)
            (kg_data / "stats.json").write_text(
                json.dumps(
                    {
                        "watermark": {
                            "repos": {
                                "trustt-platform-accounting": {
                                    "branch": "mfi_integration_v3.4.2.3",
                                    "sha": "aaaaaaaaaa",
                                }
                            }
                        }
                    }
                ),
                encoding="utf-8",
            )

            def fake_run(cmd, **kwargs):
                if "rev-parse" in cmd and "--abbrev-ref" in cmd:
                    return mock.Mock(returncode=0, stdout="mfi_integration_v3.4.2.4\n", stderr="")
                if "rev-parse" in cmd and "--short=10" in cmd:
                    return mock.Mock(returncode=0, stdout="bbbbbbbbbb\n", stderr="")
                return mock.Mock(returncode=1, stdout="", stderr="")

            with mock.patch("subprocess.run", side_effect=fake_run):
                errs = g.accounting_mismatch(root)
            self.assertTrue(errs)
            self.assertIn("mismatch", errs[0])


if __name__ == "__main__":
    unittest.main()
