#!/usr/bin/env python3
"""Unit tests for acceptance_coverage fail-closed gate."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_self_test_passes() -> None:
    rc = subprocess.call(
        [sys.executable, str(ROOT / "scripts/lib/acceptance_coverage.py"), "self-test"],
        cwd=str(ROOT),
    )
    assert rc == 0


def test_death_foreclosure_enforced() -> None:
    rc = subprocess.call(
        [
            sys.executable,
            str(ROOT / "scripts/lib/acceptance_coverage.py"),
            "check",
            "--domain",
            "death_foreclosure",
        ],
        cwd=str(ROOT),
    )
    assert rc == 0


def test_subset_note_rejected() -> None:
    from acceptance_coverage import note_antipatterns, ui_fields_ok

    hits = note_antipatterns(
        "x",
        {"note": "OK A2 netting is acceptable for QA handoff"},
    )
    assert hits, "subset Pass note must be rejected"
    assert ui_fields_ok(
        {"acceptance": {"dimensions": ["downstream_ui"], "verify_mode": "runtime"}}
    ), "webapp without ui_fields must be rejected"


if __name__ == "__main__":
    # Allow `python3 scripts/lib/test_acceptance_coverage.py`
    sys.path.insert(0, str(ROOT / "scripts/lib"))
    test_self_test_passes()
    test_death_foreclosure_enforced()
    test_subset_note_rejected()
    print("test_acceptance_coverage: PASS")
