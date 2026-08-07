"""The read_inquiry contract extractor, pinned to a case known to pass.

Two wrong turns are encoded here. Reading the orchestration validators alone reported
`getAccountBalances` as requiring no fields, which is plainly false — the request shape lives
in the JTF template, not the validator. And emitting the template literally produced
`account_overview_list.account_overview_list.amount_details.…`, a path that matches nothing:
a JTF container repeats its own name to carry the element shape.

    python3 scripts/lib/test_read_inquiry_worklist.py
"""
from __future__ import annotations

import json
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "testing"))

import read_inquiry_worklist as w  # noqa: E402


class WalkTest(unittest.TestCase):

    def test_a_repeated_container_key_is_not_a_path_segment(self) -> None:
        node = {"rows": {"class": "SMPL", "type": "ARR",
                         "rows": {"leaf": {"class": "SMPL", "type": "String"}}}}
        self.assertEqual(["rows[0].leaf"], [f["path"] for f in w.walk(node)])

    def test_an_array_gets_an_index(self) -> None:
        node = {"items": {"type": "ARR", "items": {"id": {"type": "String"}}}}
        self.assertTrue([f["path"] for f in w.walk(node)][0].startswith("items[0]."))

    def test_a_map_gets_no_index(self) -> None:
        node = {"blk": {"type": "MAP", "blk": {"id": {"type": "String"}}}}
        self.assertEqual(["blk.id"], [f["path"] for f in w.walk(node)])

    def test_a_bare_leaf_is_returned(self) -> None:
        self.assertEqual(["x"], [f["path"] for f in w.walk({"x": {"type": "String"}})])

    def test_metadata_keys_are_never_emitted(self) -> None:
        paths = [f["path"] for f in w.walk({"a": {"class": "SMPL", "type": "String"}})]
        self.assertNotIn("class", " ".join(paths))


class LiveContractTest(unittest.TestCase):
    """Against the shipped templates — the extractor must agree with a passing case."""

    def setUp(self) -> None:
        if not w.TEMPLATES.is_dir():
            self.skipTest("accounting templates not present in this checkout")

    def _resp(self, api: str) -> list[str]:
        idx = w._template_index("response")
        if api not in idx:
            self.skipTest(f"no response template for {api}")
        return [f["path"] for f in w.contract_from_template(idx[api], api)]

    def test_overview_paths_match_the_shape_the_passing_case_asserts(self) -> None:
        paths = self._resp("getLoanAccountOverviewDetails")
        self.assertTrue(
            any(p.startswith("account_overview_list[0].amount_details.") for p in paths),
            "dpic.overview_api passes against account_overview_list[0].amount_details.*")
        self.assertFalse(
            any("account_overview_list.account_overview_list" in p for p in paths),
            "the repeated container key leaked back into the path")

    def test_payment_details_list_is_reached(self) -> None:
        paths = self._resp("getLoanAccountOverviewDetails")
        self.assertTrue(
            any(p.startswith("account_overview_list[0].payment_details.payment_details_list")
                for p in paths))

    def test_request_template_beats_the_validators(self) -> None:
        idx = w._template_index("request")
        if "getAccountBalances" not in idx:
            self.skipTest("no request template")
        fields = w.contract_from_template(idx["getAccountBalances"], "getAccountBalances")
        self.assertTrue(fields,
                        "validators reported no required fields for this API; the template "
                        "is the contract")
        self.assertTrue(any(f["path"].endswith("account_number") for f in fields))

    def test_templates_exist_for_most_uncovered_read_apis(self) -> None:
        rows = w.build()
        if not rows:
            self.skipTest("no uncovered read APIs")
        templated = [r for r in rows if r["request_template"]]
        self.assertGreater(len(templated), len(rows) * 0.8,
                           "if most APIs have no template the worklist cannot be trusted")

    def test_nothing_is_silently_truncated(self) -> None:
        rows = [r for r in w.build() if r["response_template"]]
        if not rows:
            self.skipTest("no response templates")
        api = rows[0]["api"]
        full = w.contract_from_template(w._template_index("response")[api], api)
        self.assertEqual(len(full), len(rows[0]["assertable_paths"]),
                         "a capped path list reads as the whole contract")


if __name__ == "__main__":
    unittest.main(verbosity=2)
