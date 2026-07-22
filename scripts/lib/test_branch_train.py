#!/usr/bin/env python3
from __future__ import annotations

import contextlib
import io
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import branch_train


class BranchTrainTest(unittest.TestCase):
    def test_descendants_use_dag_not_version_sort(self) -> None:
        graph = {
            "mfi_integration_v3.4": {"mfi_release_v3.4"},
            "mfi_release_v3.4": {"mfi_integration_v3.5"},
            "mfi_integration_v3.5": set(),
            "mfi_integration_v9.9": set(),
        }
        self.assertEqual(
            branch_train.descendants(graph, "mfi_integration_v3.4"),
            ["mfi_release_v3.4", "mfi_integration_v3.5"],
        )

    def test_live_kg_context_resolves_flow_files(self) -> None:
        context = branch_train.kg_context("loanRecurringPaymentBatchApi")
        self.assertEqual(context.repo, "trustt-platform-accounting")
        self.assertIn(
            "src/main/java/in/novopay/accounting/loan/recurring/batch/"
            "LoanRecurringPaymentBatchProcessor.java",
            context.files,
        )

    def test_branch_graph_is_concise_ancestry_cover(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            self._git(repo, "init", "-q")
            first = self._commit(repo, "one")
            second = self._commit(repo, "two")
            third = self._commit(repo, "three")
            self._git(
                repo, "update-ref", "refs/remotes/upstream/mfi_integration_v3.4", first
            )
            self._git(
                repo, "update-ref", "refs/remotes/upstream/mfi_release_v3.4", second
            )
            self._git(
                repo, "update-ref", "refs/remotes/upstream/mfi_integration_v3.5", third
            )

            graph, _ = branch_train.branch_graph(repo, base="mfi_integration_v3.4")
            self.assertEqual(graph["mfi_integration_v3.4"], {"mfi_release_v3.4"})
            self.assertEqual(graph["mfi_release_v3.4"], {"mfi_integration_v3.5"})

    def test_diverge_reports_target_touch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            self._git(repo, "init", "-q")
            base = self._commit(repo, "base", "value=base\n")
            fix = self._commit(repo, "fix", "value=fix\n")
            self._git(repo, "checkout", "-q", "--detach", base)
            target = self._commit(repo, "target", "value=target\n")
            self._git(
                repo,
                "update-ref",
                "refs/remotes/upstream/mfi_integration_v3.5",
                target,
            )
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                rc = branch_train.diverge(repo, fix, "mfi_integration_v3.5")
            self.assertEqual(rc, 2)
            self.assertIn("DIVERGED", output.getvalue())

    def test_fixed_elsewhere_clean_only_when_no_later_divergence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            self._git(repo, "init", "-q")
            base = self._commit(repo, "base", "value=base\n")
            fix = self._commit(repo, "existing higher fix", "value=fix\n")
            self._git(
                repo, "update-ref", "refs/remotes/upstream/mfi_integration_v3.4", base
            )
            self._git(
                repo, "update-ref", "refs/remotes/upstream/mfi_integration_v3.5", fix
            )
            (repo / ".git/FETCH_HEAD").write_text("unit-test fresh refs\n")

            db = Path(tmp) / "kg.db"
            conn = sqlite3.connect(db)
            conn.executescript(
                """
                CREATE TABLE nodes (
                  id TEXT PRIMARY KEY, kind TEXT, label TEXT, repo TEXT, json TEXT
                );
                CREATE TABLE edges (
                  src_id TEXT, dst_id TEXT, rel TEXT, src TEXT
                );
                """
            )
            conn.execute(
                "INSERT INTO nodes VALUES (?,?,?,?,?)",
                ("request:testApi", "request", "testApi", str(repo), '{"src": null}'),
            )
            conn.execute(
                "INSERT INTO nodes VALUES (?,?,?,?,?)",
                (
                    f"case:{fix[:10]}",
                    "case",
                    "verified existing fix",
                    None,
                    '{"sha": "' + fix + '", "date": "2026-01-01"}',
                ),
            )
            conn.execute(
                "INSERT INTO edges VALUES (?,?,?,?)",
                (f"case:{fix[:10]}", "request:testApi", "touches", "CHANGELOG"),
            )
            conn.commit()
            conn.close()

            old_db = branch_train.KG_DB
            branch_train.KG_DB = db
            output = io.StringIO()
            try:
                with contextlib.redirect_stdout(output):
                    rc = branch_train.fixed_elsewhere(
                        "testApi", base="mfi_integration_v3.4"
                    )
            finally:
                branch_train.KG_DB = old_db
            text = output.getvalue()
            self.assertEqual(rc, 0)
            self.assertIn("VERIFIED_FIXED_CLEAN", text)
            self.assertIn("RESULT: REUSE_ALLOWED", text)
            self.assertNotIn("RESULT: REUSE_FORBIDDEN", text)

    def test_fixed_elsewhere_sha_containment_with_later_touch_is_forbidden(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            self._git(repo, "init", "-q")
            base = self._commit(repo, "base", "value=base\n")
            fix = self._commit(repo, "existing higher fix", "value=fix\n")
            later = self._commit(repo, "later divergence", "value=later\n")
            self._git(
                repo, "update-ref", "refs/remotes/upstream/mfi_integration_v3.4", base
            )
            self._git(
                repo, "update-ref", "refs/remotes/upstream/mfi_integration_v3.5", later
            )
            (repo / ".git/FETCH_HEAD").write_text("unit-test fresh refs\n")

            db = Path(tmp) / "kg.db"
            conn = sqlite3.connect(db)
            conn.executescript(
                """
                CREATE TABLE nodes (
                  id TEXT PRIMARY KEY, kind TEXT, label TEXT, repo TEXT, json TEXT
                );
                CREATE TABLE edges (
                  src_id TEXT, dst_id TEXT, rel TEXT, src TEXT
                );
                """
            )
            conn.execute(
                "INSERT INTO nodes VALUES (?,?,?,?,?)",
                ("request:testApi", "request", "testApi", str(repo), '{"src": null}'),
            )
            conn.execute(
                "INSERT INTO nodes VALUES (?,?,?,?,?)",
                (
                    f"case:{fix[:10]}",
                    "case",
                    "verified existing fix",
                    None,
                    '{"sha": "' + fix + '", "date": "2026-01-01"}',
                ),
            )
            conn.execute(
                "INSERT INTO edges VALUES (?,?,?,?)",
                (f"case:{fix[:10]}", "request:testApi", "touches", "CHANGELOG"),
            )
            conn.commit()
            conn.close()

            old_db = branch_train.KG_DB
            branch_train.KG_DB = db
            output = io.StringIO()
            try:
                with contextlib.redirect_stdout(output):
                    rc = branch_train.fixed_elsewhere(
                        "testApi", base="mfi_integration_v3.4"
                    )
            finally:
                branch_train.KG_DB = old_db
            text = output.getvalue()
            self.assertEqual(rc, 0)
            self.assertIn("VERIFIED_FIXED_DIVERGED", text)
            self.assertIn("RESULT: REUSE_FORBIDDEN", text)
            self.assertNotIn("RESULT: REUSE_ALLOWED", text)

    def test_file_touch_hints_are_reuse_forbidden(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            self._git(repo, "init", "-q")
            base = self._commit(repo, "base", "value=base\n")
            other = self._commit(repo, "unrelated file touch", "value=other\n")
            self._git(
                repo, "update-ref", "refs/remotes/upstream/mfi_integration_v3.4", base
            )
            self._git(
                repo, "update-ref", "refs/remotes/upstream/mfi_integration_v3.5", other
            )
            (repo / ".git/FETCH_HEAD").write_text("unit-test fresh refs\n")
            db = Path(tmp) / "kg.db"
            conn = sqlite3.connect(db)
            conn.executescript(
                """
                CREATE TABLE nodes (
                  id TEXT PRIMARY KEY, kind TEXT, label TEXT, repo TEXT, json TEXT
                );
                CREATE TABLE edges (
                  src_id TEXT, dst_id TEXT, rel TEXT, src TEXT
                );
                """
            )
            conn.execute(
                "INSERT INTO nodes VALUES (?,?,?,?,?)",
                (
                    "request:testApi",
                    "request",
                    "testApi",
                    str(repo),
                    '{"src":"' + str(repo) + '/sample.txt:1"}',
                ),
            )
            # Force file list via KG edge src path style used by strip helper
            conn.execute(
                "INSERT INTO nodes VALUES (?,?,?,?,?)",
                (
                    "processor:sampleProcessor",
                    "processor",
                    "sampleProcessor",
                    str(repo),
                    "{}",
                ),
            )
            conn.execute(
                "INSERT INTO edges VALUES (?,?,?,?)",
                (
                    "request:testApi",
                    "processor:sampleProcessor",
                    "invokes",
                    "orch.xml:1",
                ),
            )
            conn.execute(
                "INSERT INTO edges VALUES (?,?,?,?)",
                (
                    "processor:sampleProcessor",
                    "table:x",
                    "reads",
                    f"{repo.name}/sample.txt:1",
                ),
            )
            conn.commit()
            conn.close()

            # Use query_context path mode instead of fragile kg strip for this repo name
            old_db = branch_train.KG_DB
            branch_train.KG_DB = db
            output = io.StringIO()
            try:
                with contextlib.redirect_stdout(output):
                    rc = branch_train.fixed_elsewhere(
                        "sample.txt",
                        repo_hint=str(repo),
                        base="mfi_integration_v3.4",
                        show_candidates=True,
                    )
            finally:
                branch_train.KG_DB = old_db
            text = output.getvalue()
            self.assertEqual(rc, 0)
            self.assertIn("FILE_TOUCH_HINTS", text)
            self.assertIn("REUSE_FORBIDDEN", text)
            self.assertNotIn("RESULT: REUSE_ALLOWED", text)

    def test_direct_sha_query_can_verify_clean(self) -> None:
        """SHA lookup must seed cases= so VERIFIED_FIXED_CLEAN is reachable."""
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "repo"
            repo.mkdir()
            self._git(repo, "init", "-q")
            base = self._commit(repo, "base", "value=base\n")
            fix = self._commit(repo, "higher fix", "value=fix\n")
            self._git(
                repo, "update-ref", "refs/remotes/upstream/mfi_integration_v3.4", base
            )
            self._git(
                repo, "update-ref", "refs/remotes/upstream/mfi_integration_v3.5", fix
            )
            (repo / ".git/novopay-upstream-fetch.stamp").write_text(
                f"{__import__('time').time():.3f}\n"
            )

            context = branch_train.query_context(fix[:12], repo_hint=str(repo))
            self.assertEqual(len(context.cases), 1)
            self.assertEqual(context.cases[0][0], fix)
            self.assertTrue(context.cases[0][1].startswith("direct-sha:"))

            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                rc = branch_train.fixed_elsewhere(
                    fix[:12],
                    repo_hint=str(repo),
                    base="mfi_integration_v3.4",
                )
            text = output.getvalue()
            self.assertEqual(rc, 0)
            self.assertIn("VERIFIED_FIXED_CLEAN", text)
            self.assertIn("RESULT: REUSE_ALLOWED", text)

    def test_origin_fetch_head_does_not_fake_upstream_fresh(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp)
            self._git(repo, "init", "-q")
            self._commit(repo, "base")
            # Fresh origin-only FETCH_HEAD must not count as upstream freshness.
            (repo / ".git/FETCH_HEAD").write_text(
                "deadbeef\t\tbranch 'main' of https://example.invalid/origin\n"
            )
            age = branch_train.fetch_age_hours(repo)
            self.assertIsNone(age)
            warning = branch_train.fetch_warning(repo)
            self.assertIsNotNone(warning)
            self.assertIn("UNKNOWN", warning or "")

            # Upstream stamp restores freshness even if FETCH_HEAD is origin-only.
            (repo / ".git/novopay-upstream-fetch.stamp").write_text(
                f"{__import__('time').time():.3f}\n"
            )
            self.assertIsNotNone(branch_train.fetch_age_hours(repo))
            self.assertLess(branch_train.fetch_age_hours(repo) or 99, 1.0)
            self.assertIsNone(branch_train.fetch_warning(repo))

    def test_audit_matches_case_repo_without_touches_edge(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            repo = Path(tmp) / "trustt-platform-accounting"
            repo.mkdir()
            self._git(repo, "init", "-q")
            orphan = self._commit(repo, "orphan fix", "value=orphan\n")
            self._git(
                repo,
                "update-ref",
                "refs/remotes/upstream/mfi_integration_v3.5",
                orphan,
            )
            db = Path(tmp) / "kg.db"
            conn = sqlite3.connect(db)
            conn.executescript(
                """
                CREATE TABLE nodes (
                  id TEXT PRIMARY KEY, kind TEXT, label TEXT, repo TEXT, json TEXT
                );
                CREATE TABLE edges (
                  src_id TEXT, dst_id TEXT, rel TEXT, src TEXT
                );
                """
            )
            conn.execute(
                "INSERT INTO nodes VALUES (?,?,?,?,?)",
                (
                    f"case:{orphan[:10]}",
                    "case",
                    "repo-tagged case",
                    "trustt-platform-accounting",
                    json.dumps(
                        {
                            "sha": orphan,
                            "repo": "trustt-platform-accounting",
                            "label": "repo-tagged case",
                        }
                    ),
                ),
            )
            conn.commit()
            conn.close()

            old_db = branch_train.KG_DB
            branch_train.KG_DB = db
            output = io.StringIO()
            try:
                with contextlib.redirect_stdout(output):
                    # SHA is on upstream — audit should report 0 unmerged, but still find the case.
                    rc = branch_train.audit(repo)
            finally:
                branch_train.KG_DB = old_db
            self.assertEqual(rc, 0)
            self.assertIn("AUDIT: 0 KG case(s)", output.getvalue())

            # Move SHA off every train → UNMERGED must still surface via case.repo.
            self._git(repo, "update-ref", "-d", "refs/remotes/upstream/mfi_integration_v3.5")
            branch_train.KG_DB = db
            output = io.StringIO()
            try:
                with contextlib.redirect_stdout(output):
                    rc = branch_train.audit(repo)
            finally:
                branch_train.KG_DB = old_db
            text = output.getvalue()
            self.assertEqual(rc, 0)
            self.assertIn("UNMERGED", text)
            self.assertIn(orphan[:10], text)

    @staticmethod
    def _git(repo: Path, *args: str) -> str:
        env = {
            **os.environ,
            "GIT_AUTHOR_NAME": "Test",
            "GIT_AUTHOR_EMAIL": "test@example.invalid",
            "GIT_COMMITTER_NAME": "Test",
            "GIT_COMMITTER_EMAIL": "test@example.invalid",
        }
        return subprocess.check_output(
            ["git", "-C", str(repo), *args],
            env=env,
            text=True,
        ).strip()

    def _commit(self, repo: Path, message: str, content: str | None = None) -> str:
        path = repo / "sample.txt"
        path.write_text(content if content is not None else message + "\n")
        self._git(repo, "add", "sample.txt")
        self._git(repo, "commit", "-q", "-m", message)
        return self._git(repo, "rev-parse", "HEAD")


if __name__ == "__main__":
    unittest.main()
