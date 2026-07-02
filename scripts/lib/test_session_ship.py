#!/usr/bin/env python3
"""Tests for session-scoped autopilot close."""
from __future__ import annotations

import json
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
        self.touch = ss.SESSION_TOUCH
        self.pending = ss.PENDING
        self.passed = ss.PASSED
        self.queue = ss.PUSH_QUEUE
        self.state = ss.AUTOPILOT_STATE
        self._backup: dict[Path, str | None] = {}
        for p in (self.touch, self.pending, self.passed, self.queue, self.state):
            self._backup[p] = p.read_text(encoding="utf-8") if p.is_file() else None

    def tearDown(self) -> None:
        for p, content in self._backup.items():
            if content is None:
                p.unlink(missing_ok=True)
            else:
                p.write_text(content, encoding="utf-8")

    def test_stale_pending_no_session_touch_skips_close(self) -> None:
        self.pending.parent.mkdir(parents=True, exist_ok=True)
        self.pending.write_text(
            json.dumps({"tier": "money", "files": ["scripts/dpic/foo.sh"]}) + "\n",
            encoding="utf-8",
        )
        self.touch.unlink(missing_ok=True)
        self.assertEqual(ss.auto_close_mode(), "none")
        self.assertIn("stale", ss.auto_close_reason())

    def test_session_touch_money_fix_ship_runs_close(self) -> None:
        self.pending.write_text(
            json.dumps({"tier": "money", "files": ["scripts/dpic/foo.sh"]}) + "\n",
            encoding="utf-8",
        )
        ss.touch_session_ship(source="edit", paths=["scripts/dpic/foo.sh"])
        self.state.write_text(
            json.dumps({"last_classification": "FIX+SHIP"}) + "\n",
            encoding="utf-8",
        )
        self.assertEqual(ss.auto_close_mode(), "full")

    def test_verified_queue_triggers_close(self) -> None:
        self.pending.write_text(
            json.dumps({"tier": "money", "files": ["scripts/dpic/foo.sh"]}) + "\n",
            encoding="utf-8",
        )
        ss.touch_session_ship(source="edit")
        self.queue.write_text(
            json.dumps({"status": "verified", "test_passed_at": time.time()}) + "\n",
            encoding="utf-8",
        )
        self.state.write_text(json.dumps({"last_classification": "BUG"}) + "\n", encoding="utf-8")
        self.assertEqual(ss.auto_close_mode(), "full")

    def test_workspace_tier_close_mode(self) -> None:
        self.pending.write_text(
            json.dumps({"tier": "workspace", "files": [".cursor/changelog.md"]}) + "\n",
            encoding="utf-8",
        )
        ss.touch_session_ship(source="edit")
        self.assertEqual(ss.auto_close_mode(), "workspace")

    @patch.dict("os.environ", {"WORKSPACE_AUTOPILOT_FORCE_CLOSE": "1"})
    def test_force_close_env(self) -> None:
        self.pending.write_text(json.dumps({"tier": "money", "files": []}) + "\n", encoding="utf-8")
        self.assertEqual(ss.auto_close_mode(), "full")


if __name__ == "__main__":
    unittest.main()
