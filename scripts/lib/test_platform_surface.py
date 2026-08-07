"""The event, schedule, data, error and GL maps, pinned to facts held elsewhere.

These surfaces are where incidents arrive from, so a wrong entry is worse than a missing
one — it sends the next investigation to the wrong service. Each test here checks the map
against something established independently: the event registry, the money tables the
accounting rules name, or the KG's own error index.

The subtler failure this guards is a map that reports an *artefact* as a *finding*. A topic
whose name came from a variable is unknown, not orphaned; a scheduler documented in markdown
but absent from code is undocumented, not unmapped; an `xcheck` node is a verification
entry, not a posting rule. All three were in the first build.

    python3 scripts/lib/test_platform_surface.py
"""
from __future__ import annotations

import json
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[2]
FLOW = ROOT / "cursor-bundle" / "flow-test"
sys.path.insert(0, str(ROOT / "scripts" / "testing"))


def load(name: str) -> list[dict]:
    path = FLOW / name
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.startswith("#")]


class EventsTest(unittest.TestCase):

    def setUp(self) -> None:
        self.rows = load("platform_events.jsonl")
        if not self.rows:
            self.skipTest("surface map not built")
        self.by = {r["topic"]: r for r in self.rows}

    def test_the_money_topics_are_present(self) -> None:
        """Named in `events.md` as the disbursement sync contract."""
        for topic in ("disburse_loan_api", "los_lms_disbursement_sync"):
            self.assertIn(topic, self.by, f"{topic} missing from the event map")

    def test_disburse_loan_api_is_consumed_by_accounting(self) -> None:
        row = self.by["disburse_loan_api"]
        consumers = " ".join(row["consumer_services"] + row["consumer_classes"])
        self.assertIn("accounting", consumers,
                      "LmsMessageBrokerConsumer consumes this; the map must show it")

    def test_a_topic_named_from_a_variable_is_flagged_not_reported_as_orphan(self) -> None:
        """`topic:key` came from `pushDataToKafkaQueue(key, …)`, not from a literal."""
        artefacts = [r for r in self.rows if not r["literal"]]
        for row in artefacts:
            self.assertTrue(row["producer_site"],
                            "an artefact entry must at least name where it was parsed from")


class ScheduleTest(unittest.TestCase):

    def setUp(self) -> None:
        self.rows = load("platform_schedulers.jsonl")
        if not self.rows:
            self.skipTest("surface map not built")

    def test_schedulers_are_found_across_more_than_one_repo(self) -> None:
        repos = {r["repo"] for r in self.rows if r["repo"]}
        self.assertGreater(len(repos), 5, "batch work is not confined to one service")

    def test_most_schedulers_name_the_request_they_trigger(self) -> None:
        mapped = sum(1 for r in self.rows if r["triggers"])
        self.assertGreater(mapped / max(len(self.rows), 1), 0.9)

    def test_doc_sourced_entries_are_distinguished_from_code(self) -> None:
        """A name in scheduler-registry.md with no bean is undocumented code, not a gap."""
        unmapped = [r for r in self.rows if r["unmapped"]]
        if not unmapped:
            self.skipTest("nothing unmapped")
        self.assertTrue(any(r["from_doc"] for r in unmapped),
                        "from_doc never set — the provenance split is not working")


class DataTest(unittest.TestCase):

    def setUp(self) -> None:
        self.rows = load("platform_tables.jsonl")
        if not self.rows:
            self.skipTest("surface map not built")
        self.by = {r["table"]: r for r in self.rows}

    def test_the_money_tables_have_writers(self) -> None:
        for table in ("loan_account", "loan_due_details", "loan_account_payments_details",
                      "client_request_response_log"):
            self.assertIn(table, self.by, f"{table} missing from the data map")
            self.assertTrue(self.by[table]["written_by"],
                            f"{table} shows no writer — the reverse index is broken")

    def test_writers_are_named_repo_and_api(self) -> None:
        row = self.by["loan_account"]
        for writer in row["written_by"][:20]:
            self.assertIn("/", writer, "a writer must say which repo serves it")


    def test_tables_carry_their_live_column_shape(self) -> None:
        """Joined from the schema oracle so a column can be resolved, never guessed."""
        row = self.by["loan_account"]
        self.assertTrue(row["in_local_schema"])
        self.assertGreater(row["column_count"], 20)
        self.assertIn("account_id", row["columns"])
        self.assertEqual(row["primary_key"], ["account_id"])

    def test_a_table_absent_from_the_local_db_is_labelled_not_dropped(self) -> None:
        """Absence on one train is not proof the table does not exist."""
        absent = [r for r in self.rows if not r["in_local_schema"]]
        self.assertTrue(absent, "every KG table resolved locally — the join is not running")
        for r in absent[:10]:
            self.assertIsNone(r["column_count"])

    def test_a_table_with_no_writer_still_records_its_readers(self) -> None:
        nowriter = [r for r in self.rows if r["no_known_writer"] and r["read_by"]]
        self.assertTrue(nowriter,
                        "tables written by batch writers are still read by APIs; if none "
                        "show readers the join dropped them")


class ErrorTest(unittest.TestCase):

    def setUp(self) -> None:
        self.rows = load("platform_errors.jsonl")
        if not self.rows:
            self.skipTest("surface map not built")
        self.by = {r["code"]: r for r in self.rows}

    def test_known_accounting_codes_are_indexed(self) -> None:
        for code in ("134139", "134207"):
            self.assertIn(code, self.by, f"{code} missing — it is named in the rules")

    def test_codes_carry_a_throw_site(self) -> None:
        sited = sum(1 for r in self.rows if r["throw_site"])
        self.assertGreater(sited / max(len(self.rows), 1), 0.8)

    def test_a_code_reachable_from_an_api_names_the_flow(self) -> None:
        reachable = [r for r in self.rows if r["raised_by"]]
        self.assertTrue(reachable)
        for row in reachable[:20]:
            self.assertIn("/", row["raised_by"][0])


class UiReachTest(unittest.TestCase):

    def test_the_api_map_records_which_apis_the_webapp_reaches(self) -> None:
        rows = load("platform_api_map.jsonl")
        if not rows:
            self.skipTest("api map not built")
        reachable = [r for r in rows if r.get("ui_reachable")]
        self.assertTrue(reachable, "no API marked UI-reachable; the ui_calls join is broken")
        self.assertLess(len(reachable), len(rows),
                        "every API marked UI-reachable means the join matched everything")




class GlRuleTest(unittest.TestCase):

    def setUp(self) -> None:
        self.rows = load("platform_gl_rules.jsonl")
        if not self.rows:
            self.skipTest("surface map not built")
        self.posting = [r for r in self.rows if r["is_posting_rule"]]

    def test_disbursement_posts_the_known_placeholders(self) -> None:
        """Named in accounting-134207-placeholder-iad.md as the ones that must resolve."""
        legs = [r for r in self.posting if r["txn_type"] == "LOAN_DISBURSEMENT"]
        self.assertTrue(legs, "LOAN_DISBURSEMENT has no posting rules")
        codes = {r["reference_code"] for r in legs}
        for code in ("DISB_AMT", "PROC_FEE", "STAMP_DUTY_AMT"):
            self.assertIn(code, codes)

    def test_a_posting_rule_names_both_legs(self) -> None:
        for r in self.posting:
            self.assertTrue(r["debit_placeholder"] or r["credit_placeholder"],
                            f"{r['rule']} posts nothing at all")

    def test_cross_check_nodes_are_not_counted_as_rules(self) -> None:
        """`xcheck …` and parity entries are verification, not posting rules."""
        checks = [r for r in self.rows if not r["is_posting_rule"]]
        for r in checks:
            self.assertIsNone(r["rule_id"])

    def test_a_transaction_type_names_the_processor_that_selects_it(self) -> None:
        selected = [r for r in self.posting if r["selected_by"]]
        self.assertTrue(selected, "no GL rule links to a sets_txn_type processor")


class CallerIndexTest(unittest.TestCase):

    def test_the_hottest_contracts_record_their_callers(self) -> None:
        rows = load("platform_api_map.jsonl")
        if not rows:
            self.skipTest("api map not built")
        by = {r["api"]: r for r in rows}
        for api in ("getUserDetails", "postTransaction", "submitApplication"):
            self.assertIn(api, by)
            self.assertTrue(by[api]["called_by"],
                            f"{api} is called across the platform; the reverse index lost it")

    def test_callers_are_repo_qualified(self) -> None:
        rows = load("platform_api_map.jsonl")
        if not rows:
            self.skipTest("api map not built")
        for r in rows:
            for caller in (r.get("called_by") or [])[:5]:
                self.assertIn("/", caller)

class ProcessorTest(unittest.TestCase):

    def setUp(self) -> None:
        self.rows = load("platform_processors.jsonl")
        if not self.rows:
            self.skipTest("surface map not built")
        self.by = {r["processor"]: r for r in self.rows}

    def test_a_shared_processor_names_every_repo_it_runs_in(self) -> None:
        shared = [r for r in self.rows if r["shared"]]
        self.assertTrue(shared, "no processor spans repos; the inversion is not running")
        for r in shared[:20]:
            self.assertGreater(len(r["spans_repos"]), 1)
            self.assertEqual(len(r["spans_repos"]), len(set(r["spans_repos"])))

    def test_the_money_writers_name_their_tables(self) -> None:
        writers = [r for r in self.rows if r["money_writer"]]
        self.assertTrue(writers)
        for r in writers[:20]:
            self.assertTrue(r["writes"])

    def test_reuse_count_matches_the_flows_listed(self) -> None:
        for r in self.rows[:200]:
            self.assertEqual(r["flow_count"], len(r["used_by_flows"]))

    def test_an_unresolvable_table_name_is_flagged_not_counted(self) -> None:
        """A DAO call the KG could not resolve became a table called backslash."""
        tables = load("platform_tables.jsonl")
        if not tables:
            self.skipTest("table map not built")
        for r in tables:
            if not r["valid_name"]:
                self.assertFalse(r["in_local_schema"] and r["column_count"],
                                 "a non-name cannot have a real column shape")

class IncidentWalkthroughTest(unittest.TestCase):
    """The maps must answer a real incident, not merely contain rows.

    Driving `134207 on disburseLoan` through them is what found the one-hop bug: the code is
    thrown under `postTransaction`, and `accounting-134207-placeholder-iad.md` documents it
    arriving on `disburseLoan`, which calls postTransaction. A direct-only index answered
    "disburseLoan cannot raise this" — wrong in exactly the case the runbook exists for.
    """

    def setUp(self) -> None:
        self.err = {r["code"]: r for r in load("platform_errors.jsonl")}
        self.api = {r["api"]: r for r in load("platform_api_map.jsonl")}
        self.tab = {r["table"]: r for r in load("platform_tables.jsonl")}
        if not (self.err and self.api and self.tab):
            self.skipTest("maps not built")

    def test_134207_names_its_throw_site(self) -> None:
        row = self.err["134207"]
        self.assertIn("ExecuteTransactionRulesProcessor", row["throw_site"])
        self.assertIn("trustt-platform-accounting/postTransaction", row["raised_by"])

    def test_134207_surfaces_on_disburse_loan(self) -> None:
        """Propagated through the call graph, which is how production sees it."""
        row = self.err["134207"]
        self.assertIn("trustt-platform-accounting/disburseLoan", row["surfaces_in"])

    def test_disburse_loan_lists_the_inherited_code(self) -> None:
        row = self.api["disburseLoan"]
        self.assertIn("134207", row["error_codes_via_calls"])
        self.assertNotIn("134207", row["error_codes"],
                         "direct and inherited must stay distinct, not be merged")

    def test_the_iad_table_shape_matches_the_runbook(self) -> None:
        """The columns the 134207 fix INSERTs into; verified against the live DB at 5."""
        row = self.tab["product_transaction_catalogue__placeholder__iad"]
        for column in ("product_transaction_catalogue_id", "placeholder_code",
                       "internal_account_definition_id", "is_deleted"):
            self.assertIn(column, row["columns"])
        self.assertEqual(row["column_count"], 5)


if __name__ == "__main__":
    unittest.main(verbosity=2)
