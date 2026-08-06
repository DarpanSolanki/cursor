#!/usr/bin/env python3
"""Workspace-safe HEAD must not re-run sticky money ship-loop on harness push."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/lib"))

from ship_change_scope import (  # noqa: E402
    is_scratch_path,
    is_workspace_push_safe_paths,
)
from ship_push_gate import (  # noqa: E402
    is_workspace_push_safe_head,
    should_skip_auto_close_for_knowledge_head,
)


class WorkspacePushSafeShipRoutingTest(unittest.TestCase):
    def test_harness_paths_are_push_safe(self) -> None:
        paths = [
            "scripts/disburse_loan_sanity.py",
            "scripts/complete_neft_v2_via_callbacks.py",
            "scripts/bin/disburse-indl-quick.sh",
            "scripts/neft_v2_local_prepare.sh",
            ".cursor/changelog.md",
            ".gitignore",
        ]
        self.assertTrue(is_workspace_push_safe_paths(paths))

    def test_accounting_java_not_push_safe(self) -> None:
        paths = [
            "scripts/disburse_loan_sanity.py",
            "trustt-platform-accounting/src/main/java/in/novopay/accounting/Foo.java",
        ]
        self.assertFalse(is_workspace_push_safe_paths(paths))

    def test_scratch_ignored_in_safety(self) -> None:
        self.assertTrue(is_scratch_path("scripts/scratch/indl_int_stitch/run_indl_int.py"))
        # scratch-only → not usable → False
        self.assertFalse(
            is_workspace_push_safe_paths(["scripts/scratch/indl_int_stitch/run_indl_int.py"])
        )

    def test_harness_head_skips_and_gc_drops_pushed_money(self) -> None:
        """Harness push must not money-close; clean+pushed service zombies are GC'd."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            cursor = root / ".cursor"
            cursor.mkdir()
            pending = {
                "tier": "money",
                "files": [
                    "trustt-platform-accounting/src/main/java/Foo.java",
                    "scripts/disburse_loan_sanity.py",
                    "scripts/scratch/shg_int_distribute/run_live_multiwindow.py",
                    "scripts/complete_neft_v2_via_callbacks.py",
                    ".cursor/changelog.md",
                ],
                "apis": ["interestAccrualCalculation"],
                "repos": ["trustt-platform-accounting"],
            }
            (cursor / ".pending-ship-work.json").write_text(
                json.dumps(pending), encoding="utf-8"
            )

            def _unshipped(_root: Path, rel: str) -> tuple[bool, str]:
                # Only a dirty accounting file would stay; Foo is pushed → drop
                if "Foo.java" in rel:
                    return False, "clean-and-pushed"
                if "scratch" in rel:
                    return False, "scratch"
                return False, "clean-and-pushed"

            with mock.patch("ship_push_gate.ROOT", root), mock.patch(
                "ship_push_gate.is_knowledge_only_head", return_value=False
            ), mock.patch(
                "ship_push_gate.is_workspace_push_safe_head", return_value=True
            ), mock.patch(
                "pending_ship_gc.path_unshipped", side_effect=_unshipped
            ), mock.patch(
                "pending_ship_gc.ROOT", root
            ):
                self.assertTrue(should_skip_auto_close_for_knowledge_head(root))
            self.assertFalse((cursor / ".pending-ship-work.json").is_file())

    def test_harness_head_keeps_dirty_unpushed_money(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            cursor = root / ".cursor"
            cursor.mkdir()
            pending = {
                "tier": "money",
                "files": [
                    "trustt-platform-accounting/src/main/java/Foo.java",
                    "scripts/disburse_loan_sanity.py",
                ],
                "apis": ["interestAccrualCalculation"],
                "repos": ["trustt-platform-accounting"],
            }
            (cursor / ".pending-ship-work.json").write_text(
                json.dumps(pending), encoding="utf-8"
            )

            def _unshipped(_root: Path, rel: str) -> tuple[bool, str]:
                if "Foo.java" in rel:
                    return True, "dirty"
                return False, "clean-and-pushed"

            with mock.patch("ship_push_gate.ROOT", root), mock.patch(
                "ship_push_gate.is_knowledge_only_head", return_value=False
            ), mock.patch(
                "ship_push_gate.is_workspace_push_safe_head", return_value=True
            ), mock.patch(
                "pending_ship_gc.path_unshipped", side_effect=_unshipped
            ), mock.patch(
                "pending_ship_gc.ROOT", root
            ), mock.patch(
                "pending_ship_gc.rebuild_pending",
                return_value={
                    "tier": "money",
                    "files": ["trustt-platform-accounting/src/main/java/Foo.java"],
                    "apis": ["interestAccrualCalculation"],
                    "repos": ["trustt-platform-accounting"],
                    "registry_cases": [],
                    "ntest_cases": [],
                    "updated_at": "2026-07-31T00:00:00Z",
                    "source": "gc",
                },
            ):
                self.assertTrue(should_skip_auto_close_for_knowledge_head(root))
            left = json.loads((cursor / ".pending-ship-work.json").read_text(encoding="utf-8"))
            self.assertEqual(
                ["trustt-platform-accounting/src/main/java/Foo.java"],
                left.get("files") or [],
            )


if __name__ == "__main__":
    unittest.main()
