"""The platform API map, pinned to facts established independently of it.

A map is only worth reading if it is right, and the failure mode is quiet: a field that is
empty everywhere reads as "this API touches nothing", and a field that is empty for *one
repo* reads as "that service is simple". Both are parse bugs wearing the costume of a fact.

Two were caught this way. `tables_written` matched `WRITE|INSERT|UPDATE` while the KG stores
a single `W`. `errorCode="(\\d+)"` dropped every `LOS-0003` / `COL-0112` / `PAY-0007` — 7,690
codes across four services, while accounting looked complete because its codes are numeric.

    python3 scripts/lib/test_platform_api_map.py
"""
from __future__ import annotations

import json
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
MAP = ROOT / "cursor-bundle" / "flow-test" / "platform_api_map.jsonl"
TXN = ROOT / "cursor-bundle" / "flow-test" / "transaction_map.jsonl"
sys.path.insert(0, str(ROOT / "scripts" / "testing"))


def load(path: pathlib.Path) -> list[dict]:
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.startswith("#")]


class ShapeTest(unittest.TestCase):

    def setUp(self) -> None:
        self.rows = load(MAP)
        if not self.rows:
            self.skipTest("platform map not built")
        self.by = {(r["repo"], r["api"]): r for r in self.rows}

    def test_the_map_covers_every_service_repo_that_serves_apis(self) -> None:
        repos = {r["repo"] for r in self.rows}
        for repo in ("trustt-platform-accounting", "trustt-platform-actor",
                     "trustt-platform-los", "trustt-platform-payments",
                     "trustt-platform-task", "trustt-platform-reporting"):
            self.assertIn(repo, repos, f"{repo} contributed no APIs")

    def test_reach_is_the_whole_platform_not_one_repo(self) -> None:
        self.assertGreater(len(self.rows), 1800,
                           "the platform map should cover ~1900 APIs; a collapse to a few "
                           "hundred means a repo glob stopped matching")

    def test_no_field_is_empty_across_every_row(self) -> None:
        for field in ("tables_written", "tables_read", "error_codes", "request_fields",
                      "response_fields", "processors", "cross_service_apis",
                      "mandatory_fields", "headers"):
            populated = sum(1 for r in self.rows if r.get(field))
            self.assertGreater(populated, 0,
                               f"{field} is empty for all {len(self.rows)} rows")

    def test_no_field_is_empty_for_a_whole_large_repo(self) -> None:
        """A per-repo hole is the bug that hides behind a healthy total."""
        big = {}
        for r in self.rows:
            big.setdefault(r["repo"], []).append(r)
        for repo, rows in big.items():
            if len(rows) < 50:
                continue
            for field in ("tables_written", "error_codes", "processors", "request_fields"):
                populated = sum(1 for r in rows if r.get(field))
                self.assertGreater(populated, 0,
                                   f"{field} empty for all {len(rows)} APIs in {repo}")


class KnownFactsTest(unittest.TestCase):
    """Facts established from the source, independently of the extractor."""

    def setUp(self) -> None:
        self.rows = load(MAP)
        if not self.rows:
            self.skipTest("platform map not built")
        self.by = {(r["repo"], r["api"]): r for r in self.rows}

    def test_alphanumeric_error_codes_are_captured(self) -> None:
        """`errorCode="LOS-0003"` is as real as `errorCode="134002"`."""
        prefixes = {c.split("-")[0] for r in self.rows for c in r["error_codes"] if "-" in c}
        for prefix in ("LOS", "COL"):
            self.assertIn(prefix, prefixes,
                          f"no {prefix}-NNNN code in the map — the errorCode pattern is "
                          "numeric-only again, and four services lose their codes silently")

    def test_submit_application_is_owned_by_approval_not_los(self) -> None:
        """Verified by grep: the only `<Request name="submitApplication">` is in approval."""
        self.assertIn(("trustt-platform-approval", "submitApplication"), self.by)
        self.assertNotIn(("trustt-platform-los", "submitApplication"), self.by)

    def test_control_fields_are_headers_not_body(self) -> None:
        with_headers = [r for r in self.rows if r["headers"]]
        self.assertTrue(with_headers)
        for r in with_headers:
            for field in ("function_code", "function_sub_code", "run_mode"):
                self.assertNotIn(field, r["allowed_values"],
                                 f"{r['api']}: control field leaked into the body contract")

    def test_a_cross_service_call_records_its_target_repo(self) -> None:
        crossing = [t for r in self.rows for t in r["cross_service_apis"]]
        self.assertTrue(crossing)
        for target in crossing[:50]:
            self.assertIn("/", target,
                          "a cross-service target must name the repo that serves it")

    def test_orchestration_sites_point_at_a_real_line(self) -> None:
        for r in self.rows[:200]:
            if not r["orchestration"]:
                continue
            path, _, line = r["orchestration"].rpartition(":")
            self.assertTrue((ROOT / path).is_file(), f"{r['api']}: {path} does not exist")
            self.assertTrue(line.isdigit())


class AgreementTest(unittest.TestCase):
    """The platform map must agree with the accounting map built by a separate script."""

    def test_it_agrees_with_the_loan_transaction_map(self) -> None:
        txn, plat = load(TXN), load(MAP)
        if not txn or not plat:
            self.skipTest("maps not built")
        by = {r["api"]: r for r in plat if r["repo"] == "trustt-platform-accounting"}
        for t in txn:
            p = by.get(t["api"])
            self.assertIsNotNone(p, f"{t['api']} missing from the platform map")
            self.assertEqual(set(t["tables_written"]), set(p["tables_written"]),
                             f"{t['api']}: write-set disagrees between the two maps")
            self.assertEqual(len(t["processors"]), len(p["processors"]),
                             f"{t['api']}: processor count disagrees")


class RegistryTest(unittest.TestCase):
    """`platform_master.api_master` is the gateway's routing truth, and it disagrees."""

    def setUp(self) -> None:
        path = ROOT / "cursor-bundle" / "flow-test" / "api_registry_reconciliation.json"
        if not path.is_file():
            self.skipTest("reconciliation not built")
        self.rec = json.loads(path.read_text(encoding="utf-8"))

    def test_most_of_the_registry_is_accounted_for(self) -> None:
        ratio = self.rec["registered_and_served"] / max(self.rec["registered"], 1)
        self.assertGreater(ratio, 0.8,
                           "a collapse here means the repo scan or the registry read broke, "
                           "not that the platform lost 20% of its APIs overnight")

    def test_unserved_apis_are_recorded_with_their_owning_service(self) -> None:
        """They are other product lines, not defects — the service name is what says so."""
        unserved = self.rec["registered_not_served"]
        self.assertTrue(unserved)
        self.assertTrue(any(s in unserved for s in ("PAYMENTS", "INDIA-STACK",
                                                    "BIZ-TRANSACTIONS")))

    def test_internal_child_flows_are_served_without_being_routed(self) -> None:
        """`childLoan*` runs service-to-service, so absence from the registry is correct."""
        served_only = set(self.rec["served_not_registered"])
        self.assertTrue(any(a.startswith("childLoan") for a in served_only))


class RegenerationTest(unittest.TestCase):

    def test_the_builder_is_deterministic_for_one_repo(self) -> None:
        import platform_api_map as pam
        first = pam.parse_repo("trustt-platform-task")
        second = pam.parse_repo("trustt-platform-task")
        self.assertEqual(first, second)

    def test_a_markdown_reference_is_produced(self) -> None:
        doc = ROOT / ".cursor" / "platform-api-map.md"
        self.assertTrue(doc.is_file(), "the human-readable map is the thing anyone reads")
        text = doc.read_text(encoding="utf-8")
        self.assertIn("trustt-platform-los", text)
        self.assertIn("headers", text.lower())


if __name__ == "__main__":
    unittest.main(verbosity=2)
