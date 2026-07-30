#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import train_sync  # noqa: E402


class TrainSyncTest(unittest.TestCase):
    def test_parse_full_branch(self) -> None:
        self.assertEqual(
            train_sync.parse_train_from_text("work on mfi_integration_v3.4.2.4 INT"),
            "mfi_integration_v3.4.2.4",
        )

    def test_parse_version_only(self) -> None:
        self.assertEqual(
            train_sync.parse_train_from_text("±1 on branch 3.4.2.4 exclude DPI"),
            "mfi_integration_v3.4.2.4",
        )

    def test_infer_domain_interest(self) -> None:
        self.assertEqual(
            train_sync.infer_sync_domain("parent-child INT component"),
            "accounting",
        )

    def test_infer_domain_dpi(self) -> None:
        self.assertEqual(
            train_sync.infer_sync_domain("dpiAccrualCalculation batch"),
            "dpi",
        )

    def test_sync_plan_needs_sync_when_mismatch(self) -> None:
        with mock.patch.object(train_sync, "live_branch", return_value="mfi_integration_v3.7.1"):
            plan = train_sync.sync_plan("INT on branch 3.4.2.4")
        self.assertTrue(plan["needs_sync"])
        self.assertEqual(plan["train"], "mfi_integration_v3.4.2.4")
        self.assertEqual(plan["domain"], "accounting")

    def test_sync_plan_aligned(self) -> None:
        with mock.patch.object(
            train_sync, "live_branch", return_value="mfi_integration_v3.4.2.4"
        ):
            plan = train_sync.sync_plan("on branch 3.4.2.4")
        self.assertFalse(plan["needs_sync"])
        self.assertTrue(plan["aligned"])

    def test_apply_skips_when_aligned(self) -> None:
        with mock.patch.object(
            train_sync, "live_branch", return_value="mfi_integration_v3.4.2.4"
        ):
            rc = train_sync.cmd_apply(
                argparse_ns(train="mfi_integration_v3.4.2.4", domain="accounting", dry_run=False)
            )
        self.assertEqual(rc, 0)


def argparse_ns(**kwargs):
    class NS:
        pass

    ns = NS()
    for k, v in kwargs.items():
        setattr(ns, k, v)
    return ns


if __name__ == "__main__":
    unittest.main()
