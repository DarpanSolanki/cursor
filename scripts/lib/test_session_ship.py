#!/usr/bin/env python3
"""Tests for session-scoped autopilot close."""
from __future__ import annotations

import json
import os
import tempfile
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts/lib"))

import session_ship as ss  # noqa: E402


class SessionShipTests(unittest.TestCase):
    def setUp(self) -> None:
        # Every session_ship entry point takes an injectable `root`, so these tests run
        # against a temp workspace. The previous version deleted the REAL
        # .ship-loop-passed.json / .pending-ship-work.json and restored them in tearDown
        # — which is not isolation: any hook, gate or concurrently-running test that read
        # those files inside the window saw a workspace mid-surgery, and the suite flaked.
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name)
        (self.root / ".cursor").mkdir(parents=True, exist_ok=True)
        self.touch = self.root / ".cursor/.session-ship-touched.json"
        self.pending = self.root / ".cursor/.pending-ship-work.json"
        self.passed = self.root / ".cursor/.ship-loop-passed.json"
        self.queue = self.root / ".cursor/.ship-push-queue.json"
        self.state = self.root / ".cursor/.autopilot-state.json"
        self.fixture = self.root / "fixture.tmp"
        self.fixture.write_text("fixture\n", encoding="utf-8")
        self.fixture_rel = str(self.fixture.relative_to(self.root))

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def test_stale_pending_no_session_touch_skips_close(self) -> None:
        self.pending.parent.mkdir(parents=True, exist_ok=True)
        self.pending.write_text(
            json.dumps({"tier": "money", "files": [self.fixture_rel]}) + "\n",
            encoding="utf-8",
        )
        self.touch.unlink(missing_ok=True)
        self.assertEqual(ss.auto_close_mode(self.root), "none")
        self.assertIn("stale", ss.auto_close_reason(self.root))

    def test_session_touch_money_fix_ship_runs_close(self) -> None:
        self.pending.write_text(
            json.dumps({"tier": "money", "files": [self.fixture_rel]}) + "\n",
            encoding="utf-8",
        )
        ss.touch_session_ship(self.root, source="edit", paths=[self.fixture_rel])
        self.state.write_text(
            json.dumps({"last_classification": "FIX+SHIP"}) + "\n",
            encoding="utf-8",
        )
        self.assertEqual(ss.auto_close_mode(self.root), "full")

    def test_verified_queue_triggers_close(self) -> None:
        self.pending.write_text(
            json.dumps({"tier": "money", "files": [self.fixture_rel]}) + "\n",
            encoding="utf-8",
        )
        ss.touch_session_ship(self.root, source="edit")
        self.queue.write_text(
            json.dumps({"status": "verified", "test_passed_at": time.time()}) + "\n",
            encoding="utf-8",
        )
        self.state.write_text(json.dumps({"last_classification": "BUG"}) + "\n", encoding="utf-8")
        self.assertEqual(ss.auto_close_mode(self.root), "full")

    def test_workspace_tier_close_mode(self) -> None:
        self.pending.write_text(
            json.dumps({"tier": "workspace", "files": [self.fixture_rel]}) + "\n",
            encoding="utf-8",
        )
        self.passed.unlink(missing_ok=True)
        ss.touch_session_ship(self.root, source="edit")
        self.assertEqual(ss.auto_close_mode(self.root), "workspace")

    @patch.dict("os.environ", {"WORKSPACE_AUTOPILOT_FORCE_CLOSE": "1"})
    def test_force_close_env(self) -> None:
        self.pending.write_text(json.dumps({"tier": "money", "files": []}) + "\n", encoding="utf-8")
        self.assertEqual(ss.auto_close_mode(self.root), "full")


if __name__ == "__main__":
    unittest.main()
