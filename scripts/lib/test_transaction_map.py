"""The loan transaction map, pinned to facts established independently of it.

The map is only useful if it is right, and every field here was wrong once. `tables_written`
matched `WRITE|INSERT|UPDATE` while `kg crud` prints a single `W`, so all 24 transactions
reported touching no tables — an empty field reads as "nothing here", which is worse than a
missing one. Error codes were scraped from a flow dump instead of the orchestration that
declares them.

    python3 scripts/lib/test_transaction_map.py
"""
from __future__ import annotations

import json
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
MAP = ROOT / "cursor-bundle" / "flow-test" / "transaction_map.jsonl"
sys.path.insert(0, str(ROOT / "scripts" / "testing"))


def rows() -> list[dict]:
    if not MAP.is_file():
        return []
    return [json.loads(line) for line in MAP.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.startswith("#")]


class ShapeTest(unittest.TestCase):

    def setUp(self) -> None:
        self.rows = rows()
        if not self.rows:
            self.skipTest("transaction map not built")
        self.by = {r["api"]: r for r in self.rows}

    def test_the_core_money_transactions_are_present(self) -> None:
        for api in ("disburseLoan", "loanRepayment", "loanPrepayment", "postTransaction"):
            self.assertIn(api, self.by, f"{api} missing from the map")

    def test_every_row_names_its_orchestration(self) -> None:
        for r in self.rows:
            self.assertTrue(r["orchestration"], f"{r['api']}: no orchestration site")
            self.assertIn(".xml:", r["orchestration"])

    def test_every_row_lists_processors(self) -> None:
        for r in self.rows:
            self.assertTrue(r["processors"], f"{r['api']}: no processors parsed")

    def test_no_field_is_empty_across_every_row(self) -> None:
        """An always-empty field is a parse bug wearing the costume of a fact."""
        for field in ("tables_written", "tables_read", "error_codes", "request_fields"):
            populated = sum(1 for r in self.rows if r.get(field))
            self.assertGreater(populated, 0, f"{field} is empty for all {len(self.rows)} rows")


class KnownFactsTest(unittest.TestCase):
    """Facts established elsewhere — the map must agree with them."""

    def setUp(self) -> None:
        self.by = {r["api"]: r for r in rows()}
        if not self.by:
            self.skipTest("transaction map not built")

    def test_repayment_writes_the_payments_table(self) -> None:
        self.assertIn("loan_account_payments_details",
                      self.by["loanRepayment"]["tables_written"])

    def test_repayment_declares_its_mandatory_fields(self) -> None:
        for field in ("account_number", "repayment_amount", "value_date"):
            self.assertIn(field, self.by["loanRepayment"]["mandatory_fields"])

    def test_control_fields_are_headers_not_body(self) -> None:
        """Sent in the body the gateway answers 11008 Invalid run_mode."""
        repay = self.by["loanRepayment"]
        self.assertIn("function_code", repay["headers"])
        for field in ("function_code", "function_sub_code", "run_mode"):
            self.assertNotIn(field, repay["mandatory_fields"])

    def test_cancellation_amount_contract_names_its_components(self) -> None:
        cancel = self.by.get("loanDisbursementCancellation")
        if not cancel:
            self.skipTest("cancellation not in the map")
        joined = " ".join(cancel["request_fields"])
        for part in ("principal_outstanding_details", "bpi_details",
                     "cancellation_fee_details"):
            self.assertIn(part, joined,
                          "the amount validator dereferences this section without a null "
                          "check, so a caller must send it")

    def test_a_cross_service_call_is_recorded_where_one_exists(self) -> None:
        crossing = [r["api"] for r in rows() if r["cross_service_apis"]]
        self.assertTrue(crossing, "no transaction records a cross-service call")


class RegenerationTest(unittest.TestCase):

    def test_the_builder_is_deterministic_for_one_api(self) -> None:
        import transaction_map as tm
        first = tm.build("loanRepayment")
        second = tm.build("loanRepayment")
        self.assertEqual(first, second)

    def test_a_markdown_reference_is_produced(self) -> None:
        doc = ROOT / ".cursor" / "loan-transaction-map.md"
        self.assertTrue(doc.is_file(), "the human-readable map is the thing anyone reads")
        text = doc.read_text(encoding="utf-8")
        self.assertIn("loanRepayment", text)
        self.assertIn("headers", text.lower())

    def test_the_default_build_never_carries_another_repo(self) -> None:
        """The pinned accounting artefact must stay accounting-only — `test_platform_api_map
        .AgreementTest` reads every row of `transaction_map.jsonl` and looks it up under
        `repo == trustt-platform-accounting` only; one actor/los row here would fail that
        test with a false "missing from the platform map"."""
        import transaction_map as tm
        for row in tm.build():
            self.assertEqual(row["repo"], "trustt-platform-accounting")


class CrossRepoTest(unittest.TestCase):
    """Facts pulled by hand from each repo's own orchestration XML — the map must agree.

    Not generator output cross-checked against generator output: these mandatory fields and
    header values were read directly out of the `<Validator>` blocks with grep, independently
    of `transaction_map.py`, the same way `test_transaction_map.py`'s accounting facts were
    established for `loanRepayment`.
    """

    def setUp(self) -> None:
        import transaction_map as tm
        self.tm = tm

    def test_los_triggerDisburseLoan_mandatory_fields(self) -> None:
        """`ServiceOrchestrationXML.xml`: two `mandatoryFieldValidator` IParams, both
        errorCode="LOS-0015" — `loan_app_id` and `loan_status`."""
        rows = self.tm.build("triggerDisburseLoan", repo="trustt-platform-los")
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertEqual(set(row["mandatory_fields"]), {"loan_app_id", "loan_status"})
        self.assertIn("LOS-0015", row["error_codes"])

    def test_approval_submitApplication_mandatory_fields(self) -> None:
        """`ServiceOrchestrationXML.xml`: unconditional mandatoryFieldValidator IParams are
        `usecase` (320001), `data` (320002), `identifier` (320011); `function_code` is
        pattern `SUBMIT|RESUBMIT` — a header, not a body field."""
        rows = self.tm.build("submitApplication", repo="trustt-platform-approval")
        self.assertEqual(len(rows), 1)
        row = rows[0]
        for field in ("usecase", "data", "identifier"):
            self.assertIn(field, row["mandatory_fields"])
        self.assertEqual(row["headers"].get("function_code"), "SUBMIT")
        self.assertNotIn("function_code", row["mandatory_fields"])
        for code in ("320001", "320002", "320011"):
            self.assertIn(code, row["error_codes"])

    def test_task_createOrUpdateTask_mandatory_field(self) -> None:
        """`ServiceOrchestrationXML.xml`: `application_id` is a mandatoryFieldValidator
        IParam, errorCode 375504; `function_code` pattern is `DEFAULT|APPROVE|RESUBMIT`."""
        rows = self.tm.build("createOrUpdateTask", repo="trustt-platform-task")
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertIn("application_id", row["mandatory_fields"])
        self.assertEqual(row["headers"].get("function_code"), "DEFAULT")
        self.assertIn("375504", row["error_codes"])

    def test_payments_createOrUpdateBulkCollection_mandatory_field(self) -> None:
        """`orc_collections.xml`: `collection_list` is a mandatoryFieldValidator IParam,
        errorCode COL-011; `function_code` pattern is `DEFAULT|MFI_BULK_COLLECTION`."""
        rows = self.tm.build("createOrUpdateBulkCollection", repo="trustt-platform-payments")
        self.assertEqual(len(rows), 1)
        row = rows[0]
        self.assertIn("collection_list", row["mandatory_fields"])
        self.assertEqual(row["headers"].get("function_code"), "DEFAULT")
        self.assertIn("COL-011", row["error_codes"])

    def test_actor_createMfiCustomer_is_owned_by_actor(self) -> None:
        """`grep -l '<Request name="createMfiCustomer">'` returns exactly one file, inside
        `trustt-platform-actor`."""
        rows = self.tm.build("createMfiCustomer", repo="trustt-platform-actor")
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["repo"], "trustt-platform-actor")
        self.assertIn("orc_mfi.xml", rows[0]["orchestration"])

    def test_every_repo_row_is_tagged_with_its_own_repo(self) -> None:
        for repo in self.tm.REPO_TRANSACTIONS:
            for row in self.tm.build(repo=repo):
                self.assertEqual(row["repo"], repo)

    def test_fuzzy_template_index_recovers_a_misspelled_filename(self) -> None:
        """actor ships `getApplicationToBeReallocated_requesstTemplate.json` — a strict
        `_requestTemplate.json` suffix match (`read_inquiry_worklist._template_index`) misses
        it; the split-on-first-underscore index must not."""
        idx = self.tm.template_index_fuzzy("trustt-platform-actor", "request")
        self.assertIn("getApplicationToBeReallocated", idx)

    def test_orchestration_convention_differs_from_accounting_but_still_resolves(self) -> None:
        """los and payments do not use the `_orc.xml` suffix accounting does — los ships one
        file, `ServiceOrchestrationXML.xml`; `orchestration_sites()` must still find requests
        in it via the `**/orchestration/**/*.xml` fallback."""
        sites = self.tm.orchestration_sites("trustt-platform-los")
        self.assertIn("triggerDisburseLoan", sites)
        path, _, _ = sites["triggerDisburseLoan"]
        self.assertIn("ServiceOrchestrationXML.xml", path)


if __name__ == "__main__":
    unittest.main(verbosity=2)
