#!/usr/bin/env python3
"""Fail-closed: empty/corrupt kg.db must never report FRESH via watermark alone."""
from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
KG_BIN = ROOT / "cursor-bundle/kg/bin"
KG_SWITCH = ROOT / "scripts/bin/kg-switch.sh"


class KgEmptyDbFailClosedTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        sys.path.insert(0, str(KG_BIN))
        import kg as kg_mod  # noqa: PLC0415

        cls.kg = kg_mod

    def test_db_usable_true_on_live(self):
        self.assertTrue(self.kg._db_usable(), "live kg.db should be usable")

    def test_db_usable_rejects_empty_file(self):
        with tempfile.TemporaryDirectory() as td:
            fake = Path(td) / "kg.db"
            fake.write_bytes(b"")
            with mock.patch.object(self.kg, "DB", str(fake)):
                self.assertFalse(self.kg._db_usable())

    def test_db_usable_rejects_missing(self):
        with mock.patch.object(self.kg, "DB", "/tmp/no-such-kg-db-failclosed.db"):
            self.assertFalse(self.kg._db_usable())

    def test_cmd_fresh_refuses_when_unusable(self):
        with mock.patch.object(self.kg, "_db_usable", return_value=False):
            with self.assertRaises(SystemExit) as cm:
                self.kg.cmd_fresh(None, [])
            self.assertEqual(cm.exception.code, 1)

    def test_quiet_kg_switch_skips_when_lock_held(self):
        """Anti-stampede: --quiet must exit 0 without waiting when .build.lock is held."""
        data = ROOT / "cursor-bundle/kg/data"
        lock = data / ".build.lock"
        data.mkdir(parents=True, exist_ok=True)
        # Hold exclusive flock in a child; quiet switch should skip.
        holder = subprocess.Popen(
            ["bash", "-c", f"exec 9>'{lock}'; flock -n 9 || exit 3; sleep 8"],
            cwd=str(ROOT),
        )
        try:
            # Wait until holder has the lock
            for _ in range(20):
                if holder.poll() is not None:
                    self.fail(f"lock holder exited early rc={holder.returncode}")
                # try non-blocking acquire — if we fail, holder owns it
                probe = subprocess.run(
                    ["bash", "-c", f"exec 9>'{lock}'; flock -n 9; echo $?"],
                    capture_output=True,
                    text=True,
                    timeout=2,
                )
                if probe.stdout.strip() != "0":
                    break
            else:
                self.fail("could not confirm lock held")
            p = subprocess.run(
                ["bash", str(KG_SWITCH), "--quiet"],
                cwd=str(ROOT),
                capture_output=True,
                text=True,
                timeout=5,
            )
            self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        finally:
            holder.terminate()
            holder.wait(timeout=5)


if __name__ == "__main__":
    unittest.main()
