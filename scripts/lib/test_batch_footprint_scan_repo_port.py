#!/usr/bin/env python3
"""Guards for porting `batch_footprint_scan.py` past trustt-platform-accounting.

Three defects were fixed while adding `--repo`, and each gets its own regression test here
so none of them come back silently:

  - directory-collapse: payments/los/task lay many jobs' config classes in one shared,
    type-bucketed directory, and the pre-port scanner attributed every sibling job's writes
    to whichever job it scanned first (`RunFinoneJobBatchConfigService` -> 53 tables).
  - facade over-attribution: following a job's wiring into a DAOService/Repository file and
    re-running the DAO-field regex over *that* file's own body attributes every repository a
    shared facade wires (`LoanAppDaoService`, 134 mentions) to whichever one job reached it.
  - typo'd config-class suffixes (`...BatchConfigSevice.java`) must still be found, not
    silently dropped, the same failure class the LOS glob change was fixing in the first
    place.

    python3 scripts/lib/test_batch_footprint_scan_repo_port.py
"""
from __future__ import annotations

import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "testing"))

import batch_footprint_scan as scan  # noqa: E402


def _java_root(repo_key: str) -> pathlib.Path:
    return ROOT / scan.REPO_CONFIGS[repo_key]["dir"] / "src" / "main" / "java"


class AccountingDefaultUnchangedTest(unittest.TestCase):

    def test_accounting_stays_the_fast_path(self) -> None:
        cfg = scan.REPO_CONFIGS["accounting"]
        self.assertEqual(cfg["suffixes"], ("BatchConfigService",))
        self.assertFalse(cfg["fallback"])

    def test_accounting_output_matches_the_tracked_artefact(self) -> None:
        java_root = _java_root("accounting")
        if not java_root.is_dir():
            self.skipTest("trustt-platform-accounting not checked out")
        golden = ROOT / "cursor-bundle" / "flow-test" / "batch_footprint.jsonl"
        if not golden.is_file():
            self.skipTest("batch_footprint.jsonl not built yet")
        cfg = scan.REPO_CONFIGS["accounting"]
        rows, fallback_hits = scan.build(java_root, cfg["suffixes"], cfg["fallback"])
        self.assertEqual(fallback_hits, [],
                         "accounting must never take the fallback path — that changes its "
                         "default output, which this port must not do")
        scanned_jobs = {r["job"] for r in rows}
        golden_jobs = {
            __import__("json").loads(line)["job"]
            for line in golden.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.startswith("#")
        }
        self.assertEqual(scanned_jobs, golden_jobs)


class RepoConfigsDiscoverJobsTest(unittest.TestCase):

    def test_every_configured_repo_finds_more_than_a_handful(self) -> None:
        for repo_key, cfg in scan.REPO_CONFIGS.items():
            java_root = _java_root(repo_key)
            if not java_root.is_dir():
                self.skipTest(f"{cfg['dir']} not checked out")
                continue
            with self.subTest(repo=repo_key):
                jobs, _config_paths, _fallback = scan.job_packages(
                    java_root, cfg["suffixes"], cfg["fallback"])
                self.assertGreater(len(jobs), 3,
                                   f"{repo_key}: a suffix/fallback regression would silently "
                                   "walk almost no files, same as the pre-rename glob bug")

    def test_payments_typo_suffix_is_found_via_fallback_not_dropped(self) -> None:
        java_root = _java_root("payments")
        if not java_root.is_dir():
            self.skipTest("trustt-platform-payments not checked out")
        cfg = scan.REPO_CONFIGS["payments"]
        jobs, _config_paths, fallback_hits = scan.job_packages(
            java_root, cfg["suffixes"], cfg["fallback"])
        self.assertIn("bulkFileToSGFinnoneLoanCorrectionJob", jobs,
                      "BulkFileToSGFinnoneLoanCorrectionJobBatchConfigSevice.java (missing "
                      "the 'r' in Service) must still resolve, via the config-substring "
                      "fallback — a bare suffix glob silently drops it")
        self.assertIn("BulkFileToSGFinnoneLoanCorrectionJobBatchConfigSevice", fallback_hits)


class NoDirectoryCollapseAcrossJobsTest(unittest.TestCase):
    """A shared directory must not merge every sibling job's writes into each job's row."""

    def test_los_ckyc_jobs_are_scoped_to_their_own_tasklet_not_merged(self) -> None:
        java_root = _java_root("los")
        if not java_root.is_dir():
            self.skipTest("trustt-platform-los not checked out")
        cfg = scan.REPO_CONFIGS["los"]
        rows, _fallback = scan.build(java_root, cfg["suffixes"], cfg["fallback"])
        by_job = {r["job"]: r for r in rows}
        ckyc_jobs = {
            "ckycSuccessDataBatch": "CkycSuccessData",
            "ckycInputDataBatch": "CkycInputData",
            "ckycRejectedDataBatch": "CkycRejectedData",
        }
        for job, own_family in ckyc_jobs.items():
            if job not in by_job:
                self.skipTest(f"{job} not present in this checkout")
            with self.subTest(job=job):
                sources = {ev.split(" -> ", 1)[0] for ev in by_job[job]["evidence"].values()}
                self.assertTrue(sources, f"{job}: resolved to no evidence at all")
                self.assertTrue(all(own_family in s for s in sources),
                                f"{job}: writes attributed to {sources}, not its own "
                                f"{own_family}* step — three jobs share ckyc/config/ after "
                                "the config-directory collapse; a merge bug attributes one "
                                "job's sibling's evidence to it")

    def test_payments_confirm_payment_job_does_not_claim_every_sibling_table(self) -> None:
        java_root = _java_root("payments")
        if not java_root.is_dir():
            self.skipTest("trustt-platform-payments not checked out")
        cfg = scan.REPO_CONFIGS["payments"]
        rows, _fallback = scan.build(java_root, cfg["suffixes"], cfg["fallback"])
        by_job = {r["job"]: r for r in rows}
        if "runInboundFinoneJob" not in by_job:
            self.skipTest("runInboundFinoneJob not present in this checkout")
        tables = by_job["runInboundFinoneJob"]["tables_written"]
        self.assertLessEqual(len(tables), 3,
                             "payments/batch/ is one shared directory for ~55 jobs; a "
                             "directory-scoped scan of it previously reported 53 tables for "
                             "every job in the folder")


class NoFacadeDaoOverAttributionTest(unittest.TestCase):

    def test_wiring_hop_only_follows_step_shaped_classes(self) -> None:
        self.assertIsNone(scan._WIRING_REF.match("FooDAOService"))
        self.assertIsNone(scan._WIRING_REF.match("FooRepository"))
        self.assertIsNone(scan._WIRING_REF.match("FooService"))
        self.assertTrue(scan._WIRING_REF.match("FooTasklet"))
        self.assertTrue(scan._WIRING_REF.match("FooItemWriter"))
        self.assertTrue(scan._WIRING_REF.match("FooIReader"))

    def test_payments_finone_job_resolves_to_its_own_table_only(self) -> None:
        java_root = _java_root("payments")
        if not java_root.is_dir():
            self.skipTest("trustt-platform-payments not checked out")
        cfg = scan.REPO_CONFIGS["payments"]
        rows, _fallback = scan.build(java_root, cfg["suffixes"], cfg["fallback"])
        by_job = {r["job"]: r for r in rows}
        if "runInboundFinoneJob" not in by_job:
            self.skipTest("runInboundFinoneJob not present in this checkout")
        self.assertEqual(by_job["runInboundFinoneJob"]["tables_written"], ["collection"],
                         "DeleteAllFinnoneCollectionTasklet only calls "
                         "collectionsDAOService.deleteAllFinnoneCollection() — opening "
                         "CollectionsDAOService's own file would find its other ten "
                         "repositories and misattribute them to this job")


class DaoToEntityOwnStemPreferenceTest(unittest.TestCase):

    def test_interest_setup_dao_resolves_to_its_own_entity(self) -> None:
        java_root = _java_root("accounting")
        if not java_root.is_dir():
            self.skipTest("trustt-platform-accounting not checked out")
        daos = scan.dao_to_entity(java_root)
        if "InterestSetupDAOService" not in daos:
            self.skipTest("InterestSetupDAOService not present in this checkout")
        self.assertEqual(daos["InterestSetupDAOService"], "InterestSetupEntity",
                         "must prefer the entity matching the DAO's own stem, not the "
                         "most-frequently-mentioned one (InterestSetupDateSlabEntity)")


class SharedBeanExclusionTest(unittest.TestCase):

    def test_pick_bean_never_returns_a_shared_bean(self) -> None:
        processors = sorted(scan._SHARED_BEANS) + ["someJobSpecificBatchProcessor"]
        bean = scan.pick_bean("someJob", processors, exists=lambda _node: True)
        self.assertEqual(bean, "someJobSpecificBatchProcessor")

    def test_pick_bean_finds_nothing_when_only_shared_beans_are_offered(self) -> None:
        processors = sorted(scan._SHARED_BEANS)
        bean = scan.pick_bean("someJob", processors, exists=lambda _node: True)
        self.assertIsNone(bean)


if __name__ == "__main__":
    unittest.main(verbosity=2)
