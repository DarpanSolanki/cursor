#!/usr/bin/env python3
"""No scanner may look at a repo set that is silently almost empty.

The repos were renamed `novopay-* -> trustt-*` on 2026-07-15. Three scanners in
`platform_map_worker.py` globbed only the legacy name, so from that day they walked one
repo out of twenty-two. Nothing failed: a glob that matches nothing returns `[]`, so the
platform map reported 3 batch jobs and 2 Kafka entries — against the KG's 369 schedulers
and 153 topics — and that summary is what loads into a session's context at start.

    python3 scripts/lib/test_repo_glob_coverage.py
"""
from __future__ import annotations

import pathlib
import re
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "testing"))

LEGACY_ONLY = re.compile(r'glob\(\s*["\']novopay-\*["\']\s*\)')
SCANNED = ("scripts/testing", "scripts/lib", "scripts/bin", "cursor-bundle/kg/bin")


def repo_dirs() -> list[pathlib.Path]:
    return [p for pat in ("trustt-*", "novopay-*")
            for p in ROOT.glob(pat) if (p / ".git").is_dir()]


class RepoSetTest(unittest.TestCase):

    def test_the_workspace_really_has_many_repos(self) -> None:
        self.assertGreater(len(repo_dirs()), 15,
                           "if this drops, every count below is measuring the wrong thing")

    def test_the_shared_helper_sees_all_of_them(self) -> None:
        import platform_map_worker as w
        self.assertEqual(len(repo_dirs()), len(w.service_repos()))

    def test_the_helper_deduplicates_by_name(self) -> None:
        import platform_map_worker as w
        names = [p.name for p in w.service_repos()]
        self.assertEqual(len(names), len(set(names)))


class NoLegacyOnlyGlobTest(unittest.TestCase):

    def test_no_scanner_globs_the_legacy_name_alone(self) -> None:
        offenders: list[str] = []
        for directory in SCANNED:
            base = ROOT / directory
            if not base.is_dir():
                continue
            for path in list(base.rglob("*.py")) + list(base.rglob("*.sh")):
                if path.name == pathlib.Path(__file__).name:
                    continue
                body = path.read_text(encoding="utf-8", errors="ignore")
                if not LEGACY_ONLY.search(body):
                    continue
                if 'glob("trustt-*")' in body or "glob('trustt-*')" in body:
                    continue
                offenders.append(str(path.relative_to(ROOT)))
        self.assertEqual([], offenders,
                         "these walk only the pre-rename repo name, so they scan ~1 repo "
                         "of 22 and report a near-empty result as success")


class PlatformMapIsNotEmptyTest(unittest.TestCase):
    """The counts the hub prints, floored against the KG's own view."""

    def _count(self, name: str) -> int:
        path = ROOT / "cursor-bundle" / "flow-test" / name
        if not path.is_file():
            self.skipTest(f"{name} not built yet")
        return sum(1 for line in path.read_text(encoding="utf-8").splitlines()
                   if line.strip() and not line.startswith("#"))

    def test_batch_jobs_are_not_a_handful(self) -> None:
        self.assertGreater(self._count("batch_jobs.jsonl"), 20,
                           "3 batch jobs across a lending platform was the blind-glob symptom")

    def test_kafka_entries_are_not_a_handful(self) -> None:
        self.assertGreater(self._count("kafka_index.jsonl"), 20,
                           "2 Kafka entries against 146 registered events was the same bug")


if __name__ == "__main__":
    unittest.main(verbosity=2)
